# -*- coding: utf-8 -*-
from odoo import models, fields

class AccountPaymentTerm(models.Model):
    _inherit = 'account.payment.term'

    ems_portal_visible = fields.Boolean(
        string='Visible in Enrollment Portal',
        default=False,
        help="If enabled, this payment plan will be shown to students in the enrollment portal."
    )

    ems_requires_fees = fields.Boolean(
        string='Only for fee-based enrollments',
        default=False,
        help="If enabled, this payment plan will only be shown when the enrollment contains fee products (ems_is_enrollment_fee)."
    )