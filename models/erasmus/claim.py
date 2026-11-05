# -*- coding: utf-8 -*-

import base64

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from .records import check_upload
from .workflow import check_workflow_create, check_workflow_write


class EmsErasmusClaim(models.Model):
    """Issue #685 - a claim against the provisional resolution or an appeal against the definitive
    one (art. 14 of the call). The applicant sends a claim from the portal (the issue-#682 review),
    or by email and the Erasmus team records it. The team answers the claims; the applicant's own
    Head or Deputy Head of Studies answers the appeals (`_ems_appeal_approvers`). The applicant gets
    an email when it is received and another one with the answer."""
    _name = 'ems.erasmus.claim'
    _description = 'Erasmus+ claim'
    _inherit = ['ems.base']
    _order = 'received_date desc, id desc'

    application_id = fields.Many2one(string="Application", comodel_name='ems.erasmus.application', required=True,
                                     ondelete='restrict', index=True)
    call_id = fields.Many2one(string="Call", related='application_id.call_id', store=True)
    partner_id = fields.Many2one(string="Applicant", comodel_name='res.partner', compute='_compute_partner_id',
                                 store=True, index=True)
    resolution_id = fields.Many2one(string="Against", comodel_name='ems.erasmus.resolution', ondelete='restrict',
                                    domain="[('call_id', '=', call_id), ('state', '=', 'published')]")
    kind = fields.Selection(string="Kind", required=True, default='claim', tracking=True, selection=[
        ('claim', "Claim"), ('appeal', "Appeal before the Head of Studies")])
    received_date = fields.Date(string="Received on", required=True, tracking=True,
                                default=lambda self: self.env['ems.datetime_utils'].get_local_today())
    description = fields.Text(string="What is claimed", required=True)
    attachment_ids = fields.Many2many(string="Files", comodel_name='ir.attachment',
                                      relation='ems_erasmus_claim_attachment_rel')
    response = fields.Text(string="Response", tracking=True)
    resolved_date = fields.Date(string="Resolved on", readonly=True, copy=False)
    state = fields.Selection(string="State", required=True, default='open', readonly=True, tracking=True,
                             selection=[('open', "Open"), ('resolved', "Resolved")])
    can_resolve = fields.Boolean(string="Can answer", compute='_compute_can_resolve')
    can_edit = fields.Boolean(string="Can edit", compute='_compute_can_resolve',
                              help="The Erasmus team records the claims; whoever answers an appeal only writes the response.")

    @api.depends('application_id.partner_id')
    def _compute_partner_id(self):
        for claim in self:
            claim.partner_id = claim.application_id.partner_id

    def _compute_display_name(self):
        kinds = dict(self._fields['kind']._description_selection(self.env))
        for claim in self:
            claim.display_name = f"{kinds.get(claim.kind, '')} - {claim.partner_id.name}"

    @api.depends('kind', 'application_id')
    @api.depends_context('uid')
    def _compute_can_resolve(self):
        can_edit = self.env['ems.erasmus.application']._ems_can_manage()
        for claim in self:
            claim.can_resolve = claim._ems_can_resolve()
            claim.can_edit = can_edit

    @api.model_create_multi
    def create(self, vals_list):
        check_workflow_create(self, vals_list)
        claims = super().create(vals_list)
        claims.filtered(lambda claim: claim.kind == 'appeal')._ems_ask_answer()
        self.env['ems.erasmus.application']._ems_mail(claims, 'ems.email_template_erasmus_claim_received')
        return claims

    def write(self, vals):
        """Resolved, and when, only through the actions (audit R-25). Whoever answers an appeal
        writes only its response."""
        check_workflow_write(self, vals)
        if not self.env.su:
            if not self.env['ems.erasmus.application']._ems_can_manage() and set(vals) - {'response'}:
                raise AccessError(_("Only the Erasmus team records a claim."))
            if 'response' in vals:
                self._ems_check_can_resolve()
        result = super().write(vals)
        if 'kind' in vals:
            self.sudo().activity_ids.unlink()
            self.filtered(lambda claim: claim.state == 'open' and claim.kind == 'appeal')._ems_ask_answer()
        return result

    def action_resolve(self):
        self._ems_check_can_resolve()
        if self.filtered(lambda claim: not (claim.response or '').strip()):
            raise UserError(_("Write the response first."))
        self.sudo().write({'state': 'resolved', 'resolved_date': self.env['ems.datetime_utils'].get_local_today()})
        self.sudo().activity_ids.action_feedback()
        self.env['ems.erasmus.application']._ems_mail(self, 'ems.email_template_erasmus_claim_resolved')

    def action_reopen(self):
        self._ems_check_can_resolve()
        self.sudo().write({'state': 'open', 'resolved_date': False})

    def _ems_ask_answer(self):
        """A task to answer the claim, marked done when it is resolved: for each member of the
        Erasmus team (a claim sent from the portal), or for whoever answers an appeal."""
        activity_type = self.env.ref('mail.mail_activity_data_todo')
        team = self.env['ems.erasmus.call']._ems_erasmus_team()
        for claim in self.sudo():
            if claim.kind == 'appeal':
                users, summary = claim._ems_appeal_approvers(), self.env['ems.base'].ems_elide(_("Erasmus+: answer the appeal of %s", claim.partner_id.name))
            else:
                users, summary = team, self.env['ems.base'].ems_elide(_("Erasmus+: answer the claim of %s", claim.partner_id.name))
            for user in users:
                claim.with_context(mail_activity_quick_update=True).activity_schedule(activity_type_id=activity_type.id, user_id=user.id, summary=summary)

    def _ems_appeal_approvers(self):
        """Who answers an appeal (art. 14 of the call): the applicant's own Head or Deputy Head of
        Studies, found up the chain of command from a student's group tutor or from a teacher
        themself (hr.employee.find_head_of_studies); the Director when the applicant is that Head
        of Studies or there is none; the administrators when the applicant is the Director."""
        self.ensure_one()
        employee, applicant = self._ems_appeal_chain()
        head = employee.find_head_of_studies() if employee else employee
        if not head or head == applicant:
            head = self.env.company.sudo().director_id
        users = head.user_id - applicant.user_id
        return users or self.env.ref('ems.group_academic_admin').sudo().users.filtered(lambda user: not user.share)

    def _ems_appeal_chain(self):
        """The employee whose chain of command answers the appeal (a teacher themself, a student's
        group tutor), and the applicant's own employee (a teacher, never answering their own)."""
        application = self.application_id.sudo()
        if application.audience == 'staff':
            return application.employee_id, application.employee_id
        return application.partner_id.main_group_id.tutor_id, application.employee_id

    @api.model
    def _ems_portal_create(self, vals, description, files=()):
        """A claim sent from the portal (`vals`: who and against which list), recorded with the
        moment it arrived and its files, and a task for the Erasmus team to answer it."""
        description = (description or '').strip()
        if not vals.get('resolution_id') or not description:
            raise UserError(_("You cannot claim now."))
        claim = self.sudo().create(dict(vals, description=description[:5000]))
        if files:
            claim.attachment_ids = self.env['ir.attachment'].sudo().create([{
                'name': check_upload(name), 'datas': base64.b64encode(content),
                'res_model': claim._name, 'res_id': claim.id} for name, content in files])
        claim._ems_ask_answer()
        return claim

    def _ems_can_resolve(self):
        """The Erasmus team answers the claims, whoever `_ems_appeal_approvers` names the appeals,
        and the administrator any of them."""
        self.ensure_one()
        user = self.env.user
        if self.env.su or user.has_group('ems.group_academic_admin') or user.has_group('base.group_system'):
            return True
        if self.kind == 'appeal':
            return user in self._ems_appeal_approvers()
        return user.has_group('ems.group_erasmus')

    def _ems_check_can_resolve(self):
        for claim in self:
            if not claim._ems_can_resolve():
                raise AccessError(_("The Erasmus team answers the claims, and the Head of Studies the appeals."))
