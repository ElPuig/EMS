# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import datetime

class ems_company(models.Model):
    _inherit = 'res.company'

	# NOTE: If created within settings, setting up a zero value erases the entry and the default value is used. 
    #		Using this approach, the delay can be zero (useful for testing purposes on a devel environment).
    attendance_issue_delay = fields.Integer(string="Attendance notification delay (in minutes)", default=15)
