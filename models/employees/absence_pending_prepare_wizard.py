# -*- coding: utf-8 -*-

from odoo import fields, models


class EmsAbsencePendingPrepareWizard(models.TransientModel):
    """"Create absence" on one or several detected absences (issue #707): the absence type the
    teachers' requests are prepared with. See ems.absence_pending._ems_prepare_absence()."""
    _name = "ems.absence_pending.prepare_wizard"
    _description = "Prepare the absence of detected absences"

    absence_ids = fields.Many2many(
        string="Detected absences", comodel_name="ems.absence_pending", required=True)
    leave_type_id = fields.Many2one(
        string="Absence type", comodel_name="hr.leave.type", required=True,
        # The types an absence request can use: the centre's own, none needing an allocation.
        domain=[('requires_allocation', '=', 'no')],
        help="Each teacher's absence request opens with this type. They can still change it before "
             "sending it, since they are the ones declaring it.")

    def action_confirm(self):
        self.ensure_one()
        return self.absence_ids.with_context(ems_review_wizard=True)._ems_prepare_absence(self.leave_type_id)
