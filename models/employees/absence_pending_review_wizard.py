# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class EmsAbsencePendingReviewWizard(models.TransientModel):
    """The reviewer's decision on a detected absence, from its form (issues #731, #735): Request
    action, Prepare justification or Correct check-in, on the hours chosen, the whole entry by
    default. The rest stays to review (ems.absence_pending._ems_review_range)."""
    _name = "ems.absence_pending.review_wizard"
    _description = "Review decision on part of a detected absence"

    absence_id = fields.Many2one(
        string="Detected absence", comodel_name="ems.absence_pending", required=True, ondelete="cascade")
    decision = fields.Selection(
        string="Decision", required=True,
        selection=[('request', 'Request action'), ('prepare', 'Prepare justification'), ('correct', 'Correct check-in')])
    date_from = fields.Datetime(string="From", required=True)
    date_to = fields.Datetime(string="To", required=True)
    holiday_status_id = fields.Many2one(
        string="Absence type", comodel_name="hr.leave.type",
        domain="[('company_id', 'in', [company_id, False]), ('requires_allocation', '=', 'no')]")
    company_id = fields.Many2one(comodel_name="res.company", default=lambda self: self.env.company)

    @api.constrains('date_from', 'date_to', 'absence_id')
    def _check_within_absence(self):
        for wizard in self:
            absence = wizard.absence_id
            if not (absence.date_from <= wizard.date_from < wizard.date_to <= absence.date_to):
                raise ValidationError(_("The hours must fall within the detected absence."))

    @api.constrains('decision', 'holiday_status_id')
    def _check_absence_type(self):
        for wizard in self:
            if wizard.decision == 'prepare' and not wizard.holiday_status_id:
                raise ValidationError(_("Choose the absence type to prepare."))

    def action_confirm(self):
        """Closing the dialog reloads the form; a notice of why nothing was done, if so."""
        self.ensure_one()
        absence = self.absence_id
        return absence._ems_close_dialog(absence._ems_review_range(
            self.decision, self.date_from, self.date_to, self.holiday_status_id))
