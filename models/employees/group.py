# -*- coding: utf-8 -*-

from odoo import models

from .user import log_group_changes


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

    def write(self, vals):
        """Logs the users this write adds to or removes from each group, the same way
        res.users.write() does from the user's side (issue #535)."""
        if 'users' not in vals:
            return super().write(vals)
        users = self.sudo().with_context(active_test=False).users | self._ems_users_in_commands(vals['users'])
        before = {user: user.groups_id for user in users}
        res = super().write(vals)
        log_group_changes(self.env, before, {user: user.groups_id for user in users})
        return res

    def _ems_users_in_commands(self, commands):
        user_ids = set()
        for command in commands or []:
            if command[0] in (3, 4):
                user_ids.add(command[1])
            elif command[0] == 6:
                user_ids.update(command[2])
        return self.env['res.users'].sudo().with_context(active_test=False).browse(user_ids)
