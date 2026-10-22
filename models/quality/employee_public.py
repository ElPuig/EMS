# -*- coding: utf-8 -*-

from odoo import models


class HrEmployeePublic(models.Model):
    """With 'ems_first_ids' in the context, those people come first in a dropdown (see
    ems.mine_first_mixin). Used to choose who approves a minute."""
    _name = "hr.employee.public"
    _inherit = ["hr.employee.public", "ems.mine_first_mixin"]
