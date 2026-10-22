# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError


class EmsErasmusEvaluation(models.AbstractModel):
    """Issue #686 - what an interview (students, #684) and a mobility plan rating (staff) share:
    one evaluator scores a rubric (`_ems_criteria`), submits it, and can reopen it until the
    call's review deadline or the provisional resolution; afterwards only the Erasmus team
    reopens it, with a rectification note. Whoever has one assigned is in
    ems.group_erasmus_evaluator (*Erasmus+ > My evaluations*)."""
    _name = 'ems.erasmus.evaluation'
    _description = 'Erasmus+ evaluation'
    _inherit = ['ems.base']

    # The rubric fields, required to submit, and what an evaluator may write besides them.
    _ems_criteria = ()
    _ems_evaluator_extra_fields = {'notes'}

    application_id = fields.Many2one(string="Application", comodel_name='ems.erasmus.application', required=True,
                                     ondelete='cascade', index=True)
    evaluator_id = fields.Many2one(string="Evaluator", comodel_name='res.users', ondelete='restrict',
                                   index=True, tracking=True, domain="[('share', '=', False)]")
    partner_id = fields.Many2one(string="Applicant", related='application_id.partner_id', store=True)
    call_name = fields.Char(string="Call", related='application_id.call_id.name')
    state = fields.Selection(string="State", required=True, default='draft', tracking=True, copy=False,
                             selection=[('draft', "To score"), ('submitted', "Submitted")])
    submit_date = fields.Datetime(string="Submitted on", readonly=True, copy=False)
    is_locked = fields.Boolean(string="Locked", compute='_compute_is_locked', compute_sudo=True,
                               help="The call's review deadline has passed, or the provisional resolution is "
                                    "published: only the Erasmus team can reopen it, with a rectification note.")
    notes = fields.Text(string="Evaluator's notes")
    rectification_note = fields.Text(string="Rectification note",
                                     help="Why the Erasmus team reopens the evaluation after the review deadline.")

    @api.depends('application_id.call_id.interview_deadline', 'application_id.call_id.resolution_ids.state')
    def _compute_is_locked(self):
        """Locked at the review deadline, or when the provisional resolution is published if that
        comes first (issue #685)."""
        for evaluation in self:
            call = evaluation.application_id.call_id
            deadline = call.interview_deadline
            evaluation.is_locked = (bool(deadline) and deadline <= call._ems_now()) or bool(
                call.resolution_ids.filtered(lambda resolution: resolution.state == 'published'
                                             and resolution.kind != 'admission'))

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su and not self._ems_can_manage():
            raise AccessError(_("Only the Erasmus team assigns evaluations."))
        evaluations = super().create(vals_list)
        for evaluation in evaluations.filtered('evaluator_id'):
            evaluation._ems_schedule_activity()
        evaluations.evaluator_id._ems_sync_erasmus_evaluator_group()
        return evaluations

    def write(self, vals):
        if not self.env.su and not self._ems_can_manage():
            if set(vals) - set(self._ems_criteria) - self._ems_evaluator_extra_fields:
                raise AccessError(_("An evaluator only scores the rubric of their evaluations."))
            for evaluation in self:
                evaluation._ems_check_evaluator_can_change()
        if set(vals) & set(self._ems_criteria) and self.filtered(lambda evaluation: evaluation.state == 'submitted'):
            raise UserError(_("Reopen the evaluation before changing its scores."))
        previous_evaluators = self.evaluator_id if 'evaluator_id' in vals else self.env['res.users']
        result = super().write(vals)
        if 'evaluator_id' in vals:
            self.activity_ids.sudo().unlink()
            for evaluation in self.filtered(lambda evaluation: evaluation.evaluator_id and evaluation.state == 'draft'):
                evaluation._ems_schedule_activity()
            (previous_evaluators | self.evaluator_id)._ems_sync_erasmus_evaluator_group()
        return result

    def unlink(self):
        evaluators = self.evaluator_id
        result = super().unlink()
        evaluators._ems_sync_erasmus_evaluator_group()
        return result

    def action_submit(self):
        for evaluation in self:
            evaluation._ems_check_evaluator_can_change()
            if not evaluation.evaluator_id:
                raise UserError(_("Assign who evaluates first."))
            missing = [evaluation._fields[name].string for name in self._ems_criteria if not evaluation[name]]
            if missing:
                raise UserError(_("Score every criterion first: %s", ", ".join(missing)))
        self.sudo().write({'state': 'submitted', 'submit_date': fields.Datetime.now()})
        self.sudo().activity_feedback(['mail.mail_activity_data_todo'])

    def action_reopen(self):
        """The evaluator reopens their own evaluation until the review deadline; afterwards only
        the Erasmus team can, writing why (a rectification)."""
        for evaluation in self:
            if evaluation.state != 'submitted':
                raise UserError(_("The evaluation is not submitted."))
            if not evaluation.is_locked:
                evaluation._ems_check_evaluator_can_change()
                continue
            if not self._ems_can_manage():
                raise UserError(_("The review deadline has passed: only the Erasmus team can reopen it."))
            if not (evaluation.rectification_note or '').strip():
                raise UserError(_("Write the rectification note before reopening after the review deadline."))
            evaluation.chatter(_("Reopened after the review deadline: %s", evaluation.rectification_note))
        self.sudo().write({'state': 'draft', 'rectification_note': False})

    def _ems_check_evaluator_can_change(self):
        """An evaluator changes only their own evaluation, before the review deadline; the
        Erasmus team any of them."""
        self.ensure_one()
        if self.env.su or self._ems_can_manage():
            return
        if self.evaluator_id != self.env.user:
            raise AccessError(_("This evaluation is assigned to someone else."))
        if self.is_locked:
            raise UserError(_("The review deadline has passed: the evaluation can no longer be changed."))

    def _ems_schedule_activity(self):
        self.ensure_one()
        deadline = self._ems_activity_deadline()
        self.sudo().activity_schedule(
            'mail.mail_activity_data_todo', user_id=self.evaluator_id.id,
            date_deadline=deadline and fields.Date.to_date(deadline) or fields.Date.context_today(self),
            summary=self._ems_activity_summary())

    def _ems_activity_deadline(self):
        return self.application_id.call_id.interview_deadline

    def _ems_activity_summary(self):
        raise NotImplementedError()

    def _ems_can_manage(self):
        return self.env['ems.erasmus.application']._ems_can_manage()


class ResUsers(models.Model):
    _inherit = 'res.users'

    def _ems_sync_erasmus_evaluator_group(self):
        """*Erasmus+ > My evaluations* is for whoever has an interview (issue #684) or a mobility
        plan (issue #686) to rate."""
        group = self.env.ref('ems.group_erasmus_evaluator')
        assigned = self.env['res.users']
        for model in ('ems.erasmus.interview', 'ems.erasmus.plan_rating'):
            assigned |= self.env[model].sudo().search([('evaluator_id', 'in', self.ids)]).evaluator_id
        (self & (assigned - group.users)).sudo().write({'groups_id': [(4, group.id)]})
        ((self - assigned) & group.users).sudo().write({'groups_id': [(3, group.id)]})
