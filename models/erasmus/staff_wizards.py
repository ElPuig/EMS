# -*- coding: utf-8 -*-
"""The dialogs a staff member fills in from the backend (see staff_backend.py): each one collects
what the portal's form did and calls the same model method, once the record is checked to be the
user's own (`_ems_staff_check`)."""

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.http import request

from .application import ANSWER_FIELDS, CENTRE_PROJECTS_HELP, FIRST_MOBILITY_HELP
from .mobility import PROPOSAL_FIELDS, STAFF_ACTIVITIES

REOPEN = {'type': 'ir.actions.client', 'tag': 'soft_reload'}


def wizard_files(attachments):
    """The files uploaded in a wizard, as [(name, bytes)], and the temporary attachments removed."""
    files = [(attachment.name, attachment.raw) for attachment in attachments]
    attachments.sudo().unlink()
    return files


class EmsErasmusStaffApplicationWizard(models.TransientModel):
    """The answers of a staff application (ANSWER_FIELDS['staff']), while the call accepts them."""
    _name = 'ems.erasmus.staff.application.wizard'
    _description = 'Erasmus+ staff application form'

    application_id = fields.Many2one(string="Application", comodel_name='ems.erasmus.application', required=True,
                                     ondelete='cascade')
    proposal_a = fields.Text(string="Proposal A",
                             help="The main proposal, in your own words: the activity (job shadowing, a course or "
                                  "teaching), the host entity or course, where, when and what you want to learn. It "
                                  "must be a specific entity or course.")
    proposal_b = fields.Text(string="Proposal B (backup)",
                             help="In case proposal A can't be done, in the same way: the activity, the host entity "
                                  "or course, where, when and what you want to learn.")
    declared_never_staff_mobility = fields.Boolean(
        string="I have not done any Erasmus+ mobility at the Institut Puig Castellar", help=FIRST_MOBILITY_HELP)
    declared_centre_start_date = fields.Date(string="At the centre since",
                                             help="Since when you work at the centre without interruption (the month "
                                                  "counts).")
    centre_projects = fields.Text(string="Centre projects", help=CENTRE_PROJECTS_HELP)
    declared_language_level = fields.Selection(string="Language certificate", selection=[
        ('none', "None"), ('b2', "B2"), ('c1', "C1"), ('c2', "C2")],
        help="Your highest official foreign-language certificate (B2 or higher).")
    support_needs = fields.Text(string="Support needs")
    image_consent = fields.Boolean(string="Image consent")
    applicant_notes = fields.Text(string="Notes")
    open_application = fields.Boolean(string="Open the application after saving",
                                      help="Opened from the call: saving opens the application.")

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        application_id = values.get('application_id') or self.env.context.get('default_application_id')
        if application_id:
            own = self.env['ems.erasmus.application'].browse(application_id)._ems_staff_check()
            values.update({name: own[name] for name in ANSWER_FIELDS['staff'] if name in fields_list})
        return values

    def _ems_save(self):
        self.ensure_one()
        own = self.application_id._ems_staff_check()
        answers = {name: self[name] for name in ANSWER_FIELDS['staff']}
        if answers['declared_centre_start_date']:
            # The month counts (criterion 5), as on the form's month field.
            answers['declared_centre_start_date'] = answers['declared_centre_start_date'].replace(day=1)
        own._ems_portal_save(answers, {})
        return own

    def action_save(self):
        self._ems_save()
        return self.application_id._ems_staff_form() if self.open_application else REOPEN

    def action_save_submit(self):
        self._ems_save().action_submit()
        return self.application_id._ems_staff_reload(
            _("Application submitted. You will receive a receipt by email."),
            self.application_id._ems_staff_form() if self.open_application else None)


class EmsErasmusStaffDocumentWizard(models.TransientModel):
    """Hand in one document of the staff member's application or mobility: files, or a link when
    the call asks for one."""
    _name = 'ems.erasmus.staff.document.wizard'
    _description = 'Erasmus+ staff document upload'

    line_id = fields.Many2one(string="Document", comodel_name='ems.erasmus.application.document', required=True,
                              ondelete='cascade')
    description = fields.Text(string="Instructions", compute='_compute_line')
    upload_kind = fields.Char(string="Handed in as", compute='_compute_line')
    attachment_ids = fields.Many2many(string="Files", comodel_name='ir.attachment')
    link = fields.Char(string="Link", help="The whole link, starting with https://.")

    @api.depends('line_id')
    def _compute_line(self):
        for wizard in self:
            line = wizard.line_id.sudo()
            wizard.description = line.description
            wizard.upload_kind = line.call_document_id.upload_kind

    def action_confirm(self):
        self.ensure_one()
        line = self.line_id._ems_staff_check()
        files = wizard_files(self.attachment_ids)
        if not files and not self.link:
            raise UserError(_("Add a file first."))
        document_id = line.call_document_id.id
        if line.mobility_id:
            line.mobility_id._ems_portal_upload({document_id: files})
        else:
            line.application_id._ems_portal_save({}, {document_id: files} if files else {},
                                                 {document_id: self.link} if self.link else {})
        return REOPEN


class EmsErasmusStaffClaimWizard(models.TransientModel):
    """A claim against the provisional resolution (art. 14), with its files."""
    _name = 'ems.erasmus.staff.claim.wizard'
    _description = 'Erasmus+ staff claim'

    application_id = fields.Many2one(string="Application", comodel_name='ems.erasmus.application', required=True,
                                     ondelete='cascade')
    description = fields.Text(string="What you claim", required=True)
    attachment_ids = fields.Many2many(string="Files", comodel_name='ir.attachment')

    def action_confirm(self):
        self.ensure_one()
        self.application_id._ems_staff_check()._ems_portal_claim(self.description, wizard_files(self.attachment_ids))
        return self.application_id._ems_staff_reload(_("Claim sent. You will receive a receipt by email."))


class EmsErasmusStaffRenounceWizard(models.TransientModel):
    """Renounce the place offered (`application_id`) or the mobility already accepted (`mobility_id`)."""
    _name = 'ems.erasmus.staff.renounce.wizard'
    _description = 'Erasmus+ staff renouncement'

    application_id = fields.Many2one(string="Application", comodel_name='ems.erasmus.application', ondelete='cascade')
    mobility_id = fields.Many2one(string="Mobility", comodel_name='ems.erasmus.mobility', ondelete='cascade')
    reason = fields.Text(string="Reason", help="Optional.")

    def action_confirm(self):
        self.ensure_one()
        reason = (self.reason or '').strip()[:2000] or False
        if self.mobility_id:
            self.mobility_id._ems_staff_check().action_renounce(reason)
        else:
            self.application_id._ems_staff_pending_offer().action_renounce(reason)
        return self.env['ems.erasmus.application']._ems_staff_reload(_("You have renounced the place."))


class EmsErasmusStaffProposalWizard(models.TransientModel):
    """The activity of a selected staff member, with its exact dates, for the Direction to
    validate (issue #697): sent again after a rejection, or to change a validated one before it starts."""
    _name = 'ems.erasmus.staff.proposal.wizard'
    _description = 'Erasmus+ staff activity proposal'

    mobility_id = fields.Many2one(string="Mobility", comodel_name='ems.erasmus.mobility', required=True,
                                  ondelete='cascade')
    proposal_activity = fields.Selection(string="Activity", selection=STAFF_ACTIVITIES, required=True)
    proposal_host = fields.Char(string="Host entity or course", required=True)
    proposal_contact = fields.Char(string="Contact at the host")
    proposal_country_id = fields.Many2one(string="Country", comodel_name='res.country', required=True)
    proposal_city = fields.Char(string="City")
    proposal_date_start = fields.Date(string="From", required=True)
    proposal_date_end = fields.Date(string="To", required=True)
    proposal_notes = fields.Text(string="Notes")
    attachment_ids = fields.Many2many(string="Files", comodel_name='ir.attachment',
                                      help="E.g. the course's programme or the host's invitation.")
    leave_declaration = fields.Boolean(
        string="I declare, under my own responsibility, that the details and the reason given for this absence are true.",
        help="When the Direction validates the dates, EMS requests your absence for training for them with this "
             "declaration.")

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        mobility_id = values.get('mobility_id') or self.env.context.get('default_mobility_id')
        if mobility_id:
            own = self.env['ems.erasmus.mobility'].browse(mobility_id)._ems_staff_check()
            values.update({name: own[name].id if name == 'proposal_country_id' else own[name]
                           for name in PROPOSAL_FIELDS if name in fields_list and own[name]})
        return values

    def action_confirm(self):
        self.ensure_one()
        values = {name: self[name].id if name == 'proposal_country_id' else self[name] for name in PROPOSAL_FIELDS}
        self.mobility_id._ems_staff_check()._ems_portal_propose(
            values, wizard_files(self.attachment_ids), declaration=self.leave_declaration)
        return self.env['ems.erasmus.application']._ems_staff_reload(
            _("Proposal sent. The Direction will validate it."))


class EmsErasmusStaffCommitmentWizard(models.TransientModel):
    """The commitment letter, accepted and signed in EMS (the IP address is recorded)."""
    _name = 'ems.erasmus.staff.commitment.wizard'
    _description = 'Erasmus+ staff commitment letter'

    mobility_id = fields.Many2one(string="Mobility", comodel_name='ems.erasmus.mobility', required=True,
                                  ondelete='cascade')
    commitment_text = fields.Html(string="Commitment letter", compute='_compute_commitment_text', sanitize=True)
    accepted = fields.Boolean(string="I have read the commitments and accept them")

    @api.depends('mobility_id')
    def _compute_commitment_text(self):
        for wizard in self:
            wizard.commitment_text = wizard.mobility_id and wizard.mobility_id.sudo()._ems_commitment_text()

    def action_confirm(self):
        self.ensure_one()
        address = request.httprequest.remote_addr if request else False
        self.mobility_id._ems_staff_check().action_sign_commitment(self.accepted, address)
        return self.env['ems.erasmus.application']._ems_staff_reload(_("Commitment letter signed."))


class EmsErasmusStaffSelfAssessmentWizard(models.TransientModel):
    """A week's self-assessment during the stay: every question of the call, answered once."""
    _name = 'ems.erasmus.staff.self_assessment.wizard'
    _description = 'Erasmus+ staff self-assessment'

    mobility_id = fields.Many2one(string="Mobility", comodel_name='ems.erasmus.mobility', required=True,
                                  ondelete='cascade')
    week = fields.Selection(string="Week", selection='_selection_week', required=True)
    line_ids = fields.One2many(string="Questions", comodel_name='ems.erasmus.staff.self_assessment.wizard.line',
                               inverse_name='wizard_id')

    def _selection_week(self):
        mobility_id = self.env.context.get('default_mobility_id')
        if not mobility_id:
            return []
        own = self.env['ems.erasmus.mobility'].browse(mobility_id)._ems_staff_check()
        return [(str(week), _("Week %(week)s (%(start)s - %(end)s)", week=week, start=start.strftime('%d/%m/%Y'),
                                end=end.strftime('%d/%m/%Y')))
                for week, start, end in own._ems_self_assessments_open()]

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        mobility_id = values.get('mobility_id') or self.env.context.get('default_mobility_id')
        if mobility_id:
            own = self.env['ems.erasmus.mobility'].browse(mobility_id)._ems_staff_check()
            weeks = own._ems_self_assessments_open()
            values['week'] = weeks and str(weeks[0][0])
            values['line_ids'] = [(0, 0, {'question_id': question.id})
                                  for question in own.call_id.self_assessment_question_ids]
        return values

    def action_confirm(self):
        self.ensure_one()
        answers = {line.question_id: line.rating or '' if line.kind == 'rating' else line.text or ''
                   for line in self.line_ids}
        self.mobility_id._ems_staff_check()._ems_portal_self_assessment(int(self.week), answers)
        return self.env['ems.erasmus.application']._ems_staff_reload(_("Self-assessment sent."))


class EmsErasmusStaffSelfAssessmentWizardLine(models.TransientModel):
    _name = 'ems.erasmus.staff.self_assessment.wizard.line'
    _description = 'Erasmus+ staff self-assessment answer'

    wizard_id = fields.Many2one(string="Self-assessment", comodel_name='ems.erasmus.staff.self_assessment.wizard',
                                required=True, ondelete='cascade')
    # The question's id, not a many2one: its text is read here as superuser, staff have no access to the call's questions.
    question_id = fields.Integer(string="Question id", required=True)
    question = fields.Char(string="Question", compute='_compute_question')
    kind = fields.Char(string="Answer type", compute='_compute_question')
    rating = fields.Selection(string="Rating", selection=[(str(value), str(value)) for value in range(1, 6)])
    text = fields.Text(string="Answer")

    @api.depends('question_id')
    def _compute_question(self):
        for line in self:
            question = self.env['ems.erasmus.call.question'].sudo().browse(line.question_id)
            line.question = question.name
            line.kind = question.kind
