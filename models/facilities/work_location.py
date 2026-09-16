# -*- coding: utf-8 -*-

from odoo import fields, models


class HrWorkLocation(models.Model):
    _inherit = 'hr.work.location'

    # Native Odoo (hr module) declares this as a plain, non-translatable Char - every centre's
    # own work locations (e.g. "Main building", seeded by data/main/hr.work.location.csv) would
    # otherwise always show in English regardless of the UI language, same gap ems.space_type.name
    # had before it got translate=True (see models/facilities/space_type.py).
    name = fields.Char(string="Work Location", translate=True, required=True)
