# -*- coding: utf-8 -*-
from odoo import models, fields

class ems_PaymentTerm(models.Model):
    _inherit = 'account.payment.term'

    ems_portal_visible = fields.Boolean(
        string='Visible in Enrollment Portal',
        default=False,
        help="If enabled, this payment plan will be shown to students in the enrollment portal."
    )