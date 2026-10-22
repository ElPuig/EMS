# -*- coding: utf-8 -*-

import base64

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

CHECK_STATES = [('pending', "Pending"), ('met', "Met"), ('not_met', "Not met")]
# What a Head of Studies who is not in the Erasmus team may write: the check reserved to them.
SANCTION_FIELDS = {'sanction_check', 'sanction_check_note'}
# Answers of the portal form, editable by the applicant while the call accepts applications.
ANSWER_FIELDS = ('previous_mobility', 'previous_mobility_details', 'availability', 'fewer_opportunities',
                 'image_consent', 'applicant_notes')


class EmsErasmusApplication(models.Model):
    """Issue #683 - a student's application to an Erasmus+ call. Filed from the portal
    (controllers/portal_erasmus.py, with sudo), reviewed by the Erasmus team. The state only moves
    through the actions below. See docs/en/developers/erasmus/erasmus.md."""
    _name = 'ems.erasmus.application'
    _description = 'Erasmus+ application'
    _inherit = ['ems.base']
    _order = 'submit_date desc, id desc'
    _sql_constraints = [
        ('call_partner_unique', 'unique(call_id, partner_id)', "A person can only apply once to each call."),
    ]

    call_id = fields.Many2one(string="Call", comodel_name='ems.erasmus.call', required=True, ondelete='restrict',
                              index=True)
    partner_id = fields.Many2one(string="Applicant", comodel_name='res.partner', required=True, ondelete='restrict',
                                 index=True)
    modality_id = fields.Many2one(string="Modality", comodel_name='ems.erasmus.call.modality', ondelete='restrict',
                                  domain="[('call_id', '=', call_id)]", tracking=True)
    state = fields.Selection(string="State", required=True, default='draft', tracking=True, copy=False, index=True,
                             selection=[
                                 ('draft', "Draft"), ('submitted', "Submitted"), ('subsanation', "Corrections requested"),
                                 ('admitted', "Admitted"), ('excluded', "Excluded"), ('not_submitted', "Not submitted"),
                             ])
    submit_date = fields.Datetime(string="Submitted on", readonly=True, copy=False)
    is_minor = fields.Boolean(string="Minor", compute='_compute_is_minor')

    previous_mobility = fields.Boolean(string="Previous Erasmus+ mobility")
    previous_mobility_details = fields.Text(string="Previous mobility details")
    availability = fields.Text(string="Availability")
    fewer_opportunities = fields.Boolean(string="Declares fewer opportunities")
    image_consent = fields.Boolean(string="Image consent")
    applicant_notes = fields.Text(string="Applicant's notes")

    document_ids = fields.One2many(string="Documents", comodel_name='ems.erasmus.application.document',
                                   inverse_name='application_id')

    requirements_check = fields.Selection(string="Requirements", selection=CHECK_STATES, default='pending',
                                          required=True, tracking=True, copy=False)
    requirements_check_note = fields.Text(string="Requirements note", copy=False)
    requirements_check_user_id = fields.Many2one(string="Requirements checked by", comodel_name='res.users',
                                                 readonly=True, copy=False)
    requirements_check_date = fields.Datetime(string="Requirements checked on", readonly=True, copy=False)
    sanction_check = fields.Selection(string="No serious sanction", selection=CHECK_STATES, default='pending',
                                      required=True, tracking=True, copy=False)
    sanction_check_note = fields.Text(string="Sanction check note", copy=False)
    sanction_check_user_id = fields.Many2one(string="Sanction checked by", comodel_name='res.users',
                                             readonly=True, copy=False)
    sanction_check_date = fields.Datetime(string="Sanction checked on", readonly=True, copy=False)
    can_check_sanction = fields.Boolean(string="Can check sanctions", compute='_compute_permissions')
    can_manage = fields.Boolean(string="Can manage", compute='_compute_permissions',
                                help="Erasmus team or administrator: everything but the sanction check.")
    exclusion_reason = fields.Text(string="Exclusion reason", tracking=True, copy=False)

    @api.depends('partner_id.birth_date')
    def _compute_is_minor(self):
        for application in self:
            application.is_minor = not application.partner_id.is_adult

    @api.depends_context('uid')
    def _compute_permissions(self):
        can_check_sanction = self._ems_can_check_sanction()
        can_manage = self._ems_can_manage()
        for application in self:
            application.can_check_sanction = can_check_sanction
            application.can_manage = can_manage

    def _compute_display_name(self):
        for application in self:
            application.display_name = f"{application.partner_id.name} - {application.call_id.name}"

    @api.model_create_multi
    def create(self, vals_list):
        """One document line per document the call asks for."""
        Call = self.env['ems.erasmus.call']
        for vals in vals_list:
            if vals.get('call_id') and 'document_ids' not in vals:
                vals['document_ids'] = [(0, 0, {'call_document_id': document.id})
                                        for document in Call.browse(vals['call_id']).document_ids]
        return super().create(vals_list)

    def write(self, vals):
        if 'state' in vals and not self.env.context.get('ems_erasmus_state'):
            raise UserError(_("The state of an application only changes through its actions."))
        if not self.env.su:
            touched = set(vals)
            if touched & SANCTION_FIELDS and not self._ems_can_check_sanction():
                raise AccessError(_("Only the Head of Studies or the Director record the serious sanction check."))
            if touched - SANCTION_FIELDS and not self._ems_can_manage():
                raise AccessError(_("Only the Erasmus team changes an application."))
        now = fields.Datetime.now()
        for check in ('requirements_check', 'sanction_check'):
            if check in vals:
                vals.update({f'{check}_user_id': self.env.uid, f'{check}_date': now})
        return super().write(vals)

    # --- team actions ----------------------------------------------------------------------

    def action_request_subsanation(self):
        """Ask the applicant to correct or complete the documents marked as needing changes or
        missing, and email them the list and the deadline."""
        for application in self:
            application._ems_check_state(('submitted',))
            to_correct = application._ems_documents_to_correct()
            if not to_correct:
                raise UserError(_("Mark which documents need changes before asking for corrections."))
            to_correct.sudo().correction_requested = True
        self._ems_set_state('subsanation')
        self._ems_send('ems.email_template_erasmus_application_subsanation')

    def action_admit(self):
        for application in self:
            application._ems_check_state(('submitted',))
            if application.requirements_check != 'met' or application.sanction_check != 'met':
                raise UserError(_("Both admission checks must be met to admit %s.", application.partner_id.name))
            if application.document_ids.filtered(lambda line: line.is_required and line.review_state != 'valid'):
                raise UserError(_("Every required document of %s must be valid to admit the application.",
                                  application.partner_id.name))
        self._ems_set_state('admitted')

    def action_exclude(self):
        for application in self:
            application._ems_check_state(('submitted', 'subsanation'))
            if not (application.exclusion_reason or '').strip():
                raise UserError(_("Write the exclusion reason first."))
        self._ems_set_state('excluded')

    def action_back_to_review(self):
        for application in self:
            application._ems_check_state(('admitted', 'excluded'))
        self._ems_set_state('submitted')

    # --- portal ----------------------------------------------------------------------------

    @api.model
    def _ems_portal_get_or_create(self, call, partner):
        """`partner`'s application to `call`, created (as a draft) on the first visit while the
        call accepts applications."""
        application = self.search([('call_id', '=', call.id), ('partner_id', '=', partner.id)])
        if application:
            return application
        modality = call._ems_modality_for(partner)
        if not modality:
            raise UserError(_("You cannot apply to this call."))
        if not call.is_accepting:
            raise UserError(_("This call is not accepting applications."))
        return self.create({'call_id': call.id, 'partner_id': partner.id, 'modality_id': modality.id})

    def _ems_portal_save(self, answers, uploads):
        """Save what the applicant sent from the portal. `answers`: values of ANSWER_FIELDS, only
        while the call accepts applications. `uploads`: {call document id: [(file name, bytes)]},
        also during subsanation, until its deadline, for the documents asked for."""
        self.ensure_one()
        answers = {key: value for key, value in answers.items() if key in ANSWER_FIELDS}
        if answers:
            if not self._ems_portal_editable():
                raise UserError(_("The application can no longer be changed."))
            self.write(answers)
        lines = {line.call_document_id.id: line for line in self.document_ids}
        editable = self._ems_portal_editable()
        correctable = self._ems_portal_correctable()
        for document_id, files in uploads.items():
            line = lines.get(document_id)
            if not files or not line:
                continue
            if not (editable or line in correctable):
                raise UserError(_("The document %s can no longer be changed.", line.name))
            line._ems_add_files(files)

    def _ems_portal_editable(self):
        """The applicant can change answers and every document: before the closing date."""
        self.ensure_one()
        return self.state in ('draft', 'submitted') and self.call_id.is_accepting

    def _ems_subsanation_open(self):
        """Corrections requested and their deadline (if any) not passed yet."""
        self.ensure_one()
        deadline = self.call_id.subsanation_deadline
        return self.state == 'subsanation' and not (deadline and deadline <= self.call_id._ems_now())

    def _ems_portal_correctable(self):
        """The document lines the applicant can still upload to during subsanation: those the
        team asked to correct."""
        self.ensure_one()
        if not self._ems_subsanation_open():
            return self.env['ems.erasmus.application.document']
        return self.document_ids.filtered('correction_requested')

    def action_submit(self):
        """Submit (or submit again) the application: every required document needs a file. Emails
        the applicant a receipt with the files received."""
        for application in self:
            if not (application._ems_portal_editable() or application._ems_subsanation_open()):
                raise UserError(_("The application can no longer be submitted."))
            missing = application.document_ids.filtered(lambda line: line.is_required and not line.attachment_ids)
            if missing:
                raise UserError(_("Upload the required documents first: %s", ", ".join(missing.mapped('name'))))
        self._ems_set_state('submitted')
        self.sudo().write({'submit_date': fields.Datetime.now()})
        self.document_ids.sudo().correction_requested = False
        self._ems_send('ems.email_template_erasmus_application_submitted')

    # --- helpers -----------------------------------------------------------------------------

    def _ems_documents_to_correct(self):
        self.ensure_one()
        return self.document_ids.filtered(
            lambda line: line.review_state == 'needs_change' or (line.is_required and not line.attachment_ids))

    def _ems_check_state(self, states):
        self.ensure_one()
        if self.state not in states:
            raise UserError(_("The application of %s is not in the right state for this action.",
                              self.partner_id.name))

    def _ems_set_state(self, state):
        self.with_context(ems_erasmus_state=True).sudo().write({'state': state})

    def _ems_can_check_sanction(self):
        return self.env.su or self.env.user.has_group('ems.group_head_of_studies')

    def _ems_can_manage(self):
        user = self.env.user
        return self.env.su or user.has_group('ems.group_erasmus') or user.has_group('ems.group_academic_admin')

    def _ems_send(self, xmlid):
        """Email `xmlid` to the applicant's own address; note it in the chatter when there is none."""
        template = self.env.ref(xmlid, raise_if_not_found=False)
        if not template:
            return
        for application in self:
            partner = application.partner_id
            if partner.email:
                template.with_context(lang=partner.lang).sudo().send_mail(
                    application.id, force_send=False, email_values={'email_to': partner.email})
            else:
                application.sudo().chatter(_("No email sent: the applicant has no email address."))

    def _ems_mail_document_list(self, lines):
        """The files of `lines` as an HTML list, for the emails."""
        return self.env['ems.base'].build_html_list([
            Markup("{}: {}").format(line.name, ", ".join(line.attachment_ids.mapped('name')) or "-")
            if line.attachment_ids else line.name
            for line in lines
        ])


class EmsErasmusApplicationDocument(models.Model):
    """The files an applicant uploaded for one document of the call, with the team's review.
    Every upload is kept: a new file never replaces the earlier ones."""
    _name = 'ems.erasmus.application.document'
    _description = 'Erasmus+ application document'
    _order = 'application_id, sequence, id'

    application_id = fields.Many2one(string="Application", comodel_name='ems.erasmus.application', required=True,
                                     ondelete='cascade', index=True)
    call_document_id = fields.Many2one(string="Call document", comodel_name='ems.erasmus.call.document',
                                       required=True, ondelete='restrict')
    name = fields.Char(string="Document", related='call_document_id.name')
    sequence = fields.Integer(string="Sequence", related='call_document_id.sequence', store=True)
    confidential = fields.Boolean(string="Confidential", related='call_document_id.confidential', store=True)
    is_required = fields.Boolean(string="Required", compute='_compute_is_required')
    attachment_ids = fields.Many2many(string="Files", comodel_name='ir.attachment',
                                      relation='ems_erasmus_application_document_attachment_rel')
    review_state = fields.Selection(string="Review", required=True, default='pending', selection=[
        ('pending', "Pending review"), ('valid', "Valid"), ('needs_change', "Needs changes")])
    review_comment = fields.Char(string="Comment for the applicant")
    correction_requested = fields.Boolean(string="Correction requested", readonly=True, copy=False,
                                          help="Asked to the applicant in the current corrections request.")

    @api.depends('call_document_id.requirement', 'application_id.is_minor')
    def _compute_is_required(self):
        for line in self:
            requirement = line.call_document_id.requirement
            line.is_required = requirement == 'required' or (requirement == 'minor' and line.application_id.is_minor)

    def action_mark_valid(self):
        self.write({'review_state': 'valid'})

    def action_mark_needs_change(self):
        self.write({'review_state': 'needs_change'})

    def _ems_add_files(self, files):
        """Attach `files` ([(name, bytes)]) to this line and put it back to review."""
        self.ensure_one()
        attachments = self.env['ir.attachment'].sudo().create([{
            'name': name,
            'datas': base64.b64encode(content),
            'res_model': self._name,
            'res_id': self.id,
        } for name, content in files])
        self.sudo().write({'attachment_ids': [(4, attachment.id) for attachment in attachments],
                           'review_state': 'pending'})
