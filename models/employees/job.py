# -*- coding: utf-8 -*-

from odoo import models, fields
from . import employee

class ems_job(models.Model):
    _inherit = "hr.job"

    employee_type = fields.Selection(string="Employee Type", selection=employee.employee_types)
    group_id = fields.Many2one(string="Security Group", comodel_name="res.groups", help="If set, employees with this job position will be automatically added to this security group.")		