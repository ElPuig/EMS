# -*- coding: utf-8 -*-

from odoo import models


class ems_groups(models.Model):
    _inherit = "res.groups"

    def _get_hidden_extra_categories(self):
        # Attendance permissions are managed through the EMS category (Academic/Secretary);
        # hide Odoo's native "Attendances" selector to avoid it being mistaken for "no access".
        return super()._get_hidden_extra_categories() + ['base.module_category_human_resources_attendances']
