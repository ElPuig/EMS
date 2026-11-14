# -*- coding: utf-8 -*-

from odoo import models


class EmsConvalidationRejectionReason(models.Model):
    _name = "ems.convalidation.rejection_reason"
    _inherit = "ems.reason.catalog"
    _description = "Convalidation refusal reason: predefined reasons why a subject is not convalidated."

