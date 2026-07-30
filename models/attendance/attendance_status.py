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

    @api.constrains("color")
    def _check_color_format(self):
        self._check_hex_color("color")
