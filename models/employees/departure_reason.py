# -*- coding: utf-8 -*-

from odoo import api, fields, models


class HrDepartureReason(models.Model):
    _name = "hr.departure.reason"
    _inherit = ["hr.departure.reason", "ems.hex_color_mixin"]

    color = fields.Char(string="Color", help="Feeds the 'Archived' ribbon shown on the "
        "employee's kanban card and form (see the shared 'ems_archived_reason_ribbon' "
        "field widget) - leave empty to fall back to the widget's own default red.")

    @api.constrains("color")
    def _check_color_format(self):
        self._check_hex_color("color")
