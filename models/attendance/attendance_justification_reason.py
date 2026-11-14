# -*- coding: utf-8 -*-

from odoo import fields, models


class EmsAttendanceJustificationReason(models.Model):
    """Why absences are justified (health, strike, an authorised activity...): the catalog a tutor
    picks from. The first one, by sequence, is the default."""
    _name = "ems.attendance_justification_reason"
    _inherit = "ems.reason.catalog"
    _description = "Justification reason: predefined reasons why absences are justified."

    requires_details = fields.Boolean(
        string="Requires details",
        help="The tutor must describe the reason in a details field (e.g. 'Other').")
    full_day = fields.Boolean(
        string="Full day",
        help="The tutor picks a single day instead of a period, and the justification covers the "
             "student's whole day (e.g. a strike).")
