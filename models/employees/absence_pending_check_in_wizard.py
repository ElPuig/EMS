# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class EmsAbsencePendingCheckInWizard(models.TransientModel):
    """"Correct check-in" on a detected absence's form (issue #731): the hours the teacher was at
    the centre, the whole entry by default. The rest stays to review (_ems_correct_check_in)."""
    _name = "ems.absence_pending.check_in_wizard"
    _description = "Correct check-in of a detected absence"

    absence_id = fields.Many2one(
        string="Detected absence", comodel_name="ems.absence_pending", required=True, ondelete="cascade")
    date_from = fields.Datetime(string="From", required=True)
    date_to = fields.Datetime(string="To", required=True)

    @api.constrains('date_from', 'date_to', 'absence_id')
    def _check_within_absence(self):
        for wizard in self:
            absence = wizard.absence_id
            if not (absence.date_from <= wizard.date_from < wizard.date_to <= absence.date_to):
                raise ValidationError(_("The hours to correct must fall within the detected absence."))

    def action_confirm(self):
        """Closing the dialog reloads the form; a notice of why nothing was done, if so."""
        self.ensure_one()
        return self.absence_id._ems_close_dialog(self.absence_id._ems_correct_check_in(self.date_from, self.date_to))
