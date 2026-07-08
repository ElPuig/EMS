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
            'base.module_category_marketing_surveys',            # Odoo's native Surveys app; EMS has its own (Quality)
            # Unused apps: not granted to anyone (not even admin), so hidden rather than
            # left as a permanently-blank, confusing selector.
            'base.module_category_services_project',             # Project
            'base.module_category_marketing_email_marketing',    # Email Marketing
            'base.module_category_productivity_dashboard',       # Dashboard
            'base.module_category_administration_administration',  # Administration -> Settings
            'mail.module_category_canned_response',                # Canned Responses -> Settings
            'queue_job.module_category_queue_job',                 # Job Queue -> Settings
        ]
