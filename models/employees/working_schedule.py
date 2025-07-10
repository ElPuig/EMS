# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError

class ims_working_schedule(models.Model):
	_inherit = 'resource.calendar'

	def action_import_planner_data(self):
		raise ValidationError("HOLA")

