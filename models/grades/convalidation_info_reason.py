# -*- coding: utf-8 -*-

from odoo import models


class EmsConvalidationInfoReason(models.Model):
    _name = "ems.convalidation.info_reason"
    _inherit = "ems.reason.catalog"
    _description = "Documentation request reason: predefined reasons to ask a convalidation applicant for more documentation."

