# -*- coding: utf-8 -*-

from odoo import fields, models


class EmsConvalidationRejectionReason(models.Model):
    _name = "ems.convalidation.rejection_reason"
    _description = "Convalidation refusal reason: predefined reasons why a subject is not convalidated."
    _order = "sequence, name"

    name = fields.Char(string="Name", translate=True, required=True)
    sequence = fields.Integer(string="Sequence", default=10)
    active = fields.Boolean(string="Active", default=True)
