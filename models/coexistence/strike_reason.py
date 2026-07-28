# -*- coding: utf-8 -*-

from odoo import fields, models


class EmsStrikeReason(models.Model):
    _name = "ems.strike.reason"
    _description = "Strike reason: predefined reasons a teacher can pick when issuing a strike."
    _order = "sequence, name"

    name = fields.Char(string="Name", translate=True, required=True)
    sequence = fields.Integer(string="Sequence", default=10)
    active = fields.Boolean(string="Active", default=True)
