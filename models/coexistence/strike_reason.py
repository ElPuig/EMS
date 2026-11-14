# -*- coding: utf-8 -*-

from odoo import models


class EmsStrikeReason(models.Model):
    _name = "ems.strike.reason"
    _inherit = "ems.reason.catalog"
    _description = "Strike reason: predefined reasons a teacher can pick when issuing a strike."

