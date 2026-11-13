# -*- coding: utf-8 -*-

from odoo import fields, models


class EmsAbsencePendingDiscardReason(models.Model):
    """Why a reviewer discards a detected absence (issue #818), picked from this catalog like the
    convalidation refusal reasons. Maintained by the Heads of Studies and the administrator, who
    archive a reason rather than delete it."""
    _name = "ems.absence_pending.discard_reason"
    _description = "Detected absence discard reason"
    _order = "sequence, name"

    name = fields.Char(string="Name", translate=True, required=True)
    sequence = fields.Integer(string="Sequence", default=10)
    active = fields.Boolean(string="Active", default=True)
