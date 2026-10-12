# -*- coding: utf-8 -*-

from odoo import api, fields, models


class ems_attendance_status(models.Model):
    _name = "ems.attendance_status"
    _description = "Attendance status: a possible value for a student's attendance status within a session."
    _order = "sequence, name"
    _inherit = ["ems.hex_color_mixin"]

    name = fields.Char(string="Name", translate=True, required=True)
    sequence = fields.Integer(string="Sequence", default=10)
    active = fields.Boolean(string="Active", default=True)
    category = fields.Selection(
        string="Category",
        selection=[("assistance", "Assistance"), ("absence", "Absence")],
        required=True,
    )
    notifiable = fields.Boolean(
        string="Notify family/tutor", default=False,
        help="If marked, a student marked with this status triggers the attendance-issue notification workflow to the family/tutor.",
    )
    color = fields.Char(string="Color", default="#3A8DDE")
    # Whether a teacher can pick this status by hand when taking the roll-call (issue #587).
    roll_call_selectable = fields.Boolean(string="Selectable in the roll-call", compute="_compute_roll_call_selectable")

    @api.depends_context("company")
    def _compute_roll_call_selectable(self):
        manual_justified = self.env.company.attendance_manual_justified
        justified = self.env.ref("ems.attendance_status_justified")
        for status in self:
            status.roll_call_selectable = manual_justified or status != justified

    @api.constrains("color")
    def _check_color_format(self):
        self._check_hex_color("color")
