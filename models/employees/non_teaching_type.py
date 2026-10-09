# -*- coding: utf-8 -*-

from odoo import fields, models


class EmsNonTeachingType(models.Model):
    _name = "ems.non_teaching_type"
    _description = "Non-teaching activity type: a working schedule period that isn't a subject (guard duty, break, coordination meeting...)."
    _order = "name"
    _sql_constraints = [
        ('unique_code', 'unique(code)', 'The code must be unique.'),
    ]

    code = fields.Char(string="Code", required=True)
    name = fields.Char(string="Name", translate=True, required=True)
    is_break = fields.Boolean(string="Is a break", help="Dropped from both hours-summary columns on the working schedule (e.g. lunch/patio break).")
    is_fixed = fields.Boolean(string="Fixed schedule", help="Counted in the 'Other fixed-schedule hours' column every day (e.g. guard duties).")
    is_guard = fields.Boolean(string="Is guard duty", help="Counted as guard duty on the guard duty schedule board (Employee Attendances > Guard duty schedule).")
    is_regular_guard = fields.Boolean(
        string="Regular guard",
        help="A teacher on this guard duty can be sent to cover a class, or a guard duty that is not regular "
             "(WC, break...), left without its teacher. A guard duty that is not regular has to be covered "
             "itself when its teacher is away.")
    active = fields.Boolean(string="Active", default=True)
