# -*- coding: utf-8 -*-

from odoo import fields, models


class EmsNonTeachingType(models.Model):
    _name = "ems.non_teaching_type"
    _description = "Non-teaching activity type: a working schedule period that isn't a subject (guard duty, break, coordination meeting...)."
    _order = "sequence, name"
    _sql_constraints = [
        ('unique_code', 'unique(code)', 'The code must be unique.'),
    ]

    code = fields.Char(string="Code", required=True)
    name = fields.Char(string="Name", translate=True, required=True)
    sequence = fields.Integer(string="Sequence", default=10)
    is_break = fields.Boolean(string="Is a break", help="Dropped from both hours-summary columns on the working schedule (e.g. lunch/patio break).")
    is_fixed = fields.Boolean(string="Always a fixed-schedule commitment", help="Counted in the 'Other fixed-schedule hours' column every day (e.g. guard duties).")
    is_guard = fields.Boolean(string="Is guard duty", help="Counted as guard duty on the guard duty schedule board (Employee Attendances > Guard duty schedule).")
    active = fields.Boolean(string="Active", default=True)
