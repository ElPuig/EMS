# -*- coding: utf-8 -*-

from odoo import fields, models


class EmsAbsencePendingDiscardWizard(models.TransientModel):
    """Discard on detected absences, from their form or their list (issue #818): the reason,
    chosen once for every selected entry, and optional details. Both open it through
    ems.absence_pending.action_discard(), which passes the entries. Who may discard each entry is
    checked when it runs (ems.absence_pending._ems_review)."""
    _name = "ems.absence_pending.discard_wizard"
    _description = "Discard detected absences"

    absence_ids = fields.Many2many(string="Detected absences", comodel_name="ems.absence_pending")
    reason_id = fields.Many2one(
        string="Reason", comodel_name="ems.absence_pending.discard_reason", required=True,
        default=lambda self: self.env['ems.absence_pending.discard_reason'].default_reason())
    details = fields.Text(string="Details")


    def action_confirm(self):
        """Closing the dialog reloads whatever opened it; a notice of what was skipped, if any,
        is shown on the way."""
        self.ensure_one()
        absences = self.absence_ids
        return absences._ems_close_dialog(absences._ems_discard(self.reason_id, self.details))
