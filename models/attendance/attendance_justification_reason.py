# -*- coding: utf-8 -*-

from odoo import fields, models


class EmsAttendanceJustificationReason(models.Model):
    """Why absences are justified (health, strike, an authorised activity...): the catalog a tutor
    picks from. The first one, by sequence, is the default."""
    _name = "ems.attendance_justification_reason"
    _description = "Justification reason: predefined reasons why absences are justified."
    _order = "sequence, name"

    name = fields.Char(string="Name", translate=True, required=True)
    sequence = fields.Integer(string="Sequence", default=10)
    active = fields.Boolean(string="Active", default=True)
    requires_details = fields.Boolean(
        string="Requires details",
        help="The tutor must describe the reason in a details field (e.g. 'Other').")
    full_day = fields.Boolean(
        string="Full day",
        help="The tutor picks a single day instead of a period, and the justification covers the "
             "student's whole day (e.g. a strike).")
