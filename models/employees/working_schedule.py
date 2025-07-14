# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError

class ims_working_schedule(models.Model):
	_inherit = 'resource.calendar'

	def action_import_planner_data(self):
		raise ValidationError("HOLA")

class ims_working_schedules_import_wizard(models.TransientModel):
	_name = "ims.working_schedules_import_wizard"
	_description = "Working schedules: import wizard."