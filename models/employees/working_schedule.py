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

	attachment_id = fields.Many2one(string="Attachment", comodel_name="ir.attachment", domain="[('res_model', '=', 'ims.working_schedules_import_wizard')]")
	file = fields.Binary(string="Planner file (XML)", related="attachment_id.datas")

	def import_planner_data(self):	
		raise ValidationError("HOLA")
