# -*- coding: utf-8 -*-

from odoo import models


class ems_groups(models.Model):
    _inherit = "res.groups"

    def _get_hidden_extra_categories(self):
        # These native selectors are already granted implicitly through EMS's own categories
        # (Academic/Secretary); hide them to avoid a blank/out-of-sync value being mistaken
        # for "no access".
        return super()._get_hidden_extra_categories() + [
            'base.module_category_human_resources_attendances',  # Attendances -> Head of Studies/Director/Administrator
            'base.module_category_sales_sales',                  # Sales -> Secretary
            'base.module_category_accounting_accounting',        # Invoicing -> Secretary
            'account.module_category_accounting_bank',           # Bank -> Secretary
            'base.module_category_human_resources_employees',    # Employees -> Academic/Secretary Administrator
        ]
