# -*- coding: utf-8 -*-

from odoo import api, fields, models


class EmsAbsencePendingLeaveWizard(models.TransientModel):
    """"Create absence" on detected absences (issue #707): the absence type, chosen once for
    every selected entry, of the requests prepared for the teachers to send."""
    _name = "ems.absence_pending.leave_wizard"
    _description = "Create absence from detected absences"

    absence_ids = fields.Many2many(string="Detected absences", comodel_name="ems.absence_pending")
    holiday_status_id = fields.Many2one(
        string="Absence type", comodel_name="hr.leave.type", required=True,
        domain="[('company_id', 'in', [company_id, False]), ('requires_allocation', '=', 'no')]")
    company_id = fields.Many2one(comodel_name="res.company", default=lambda self: self.env.company)

    @api.model
    def default_get(self, fields_list):
        """From the list's selection (active_ids) when it was not opened from a form."""
        values = super().default_get(fields_list)
        if 'absence_ids' in fields_list and not values.get('absence_ids') \
                and self.env.context.get('active_model') == 'ems.absence_pending':
            values['absence_ids'] = [(6, 0, self.env.context.get('active_ids', []))]
        return values

    def action_confirm(self):
        """Closing the dialog reloads whatever opened it; a notice of what was skipped, if any,
        is shown on the way."""
        self.ensure_one()
        return self.absence_ids._ems_close_dialog(self.absence_ids._ems_prepare_absences(self.holiday_status_id))
