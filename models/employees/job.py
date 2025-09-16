# -*- coding: utf-8 -*-

from odoo import models, fields, api
from . import employee

class ems_job(models.Model):
    _inherit = "hr.job"
    
    employee_type = fields.Selection(string="Employee Type", selection=employee.employee_types)		