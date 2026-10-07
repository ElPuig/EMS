# -*- coding: utf-8 -*-

from odoo import fields, models


class EmsConvalidationInfoReason(models.Model):
    _name = "ems.convalidation.info_reason"
    _description = "Documentation request reason: predefined reasons to ask a convalidation applicant for more documentation."
    _order = "sequence, name"

    name = fields.Char(string="Name", translate=True, required=True)
    sequence = fields.Integer(string="Sequence", default=10)
    active = fields.Boolean(string="Active", default=True)
