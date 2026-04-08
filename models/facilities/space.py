# -*- coding: utf-8 -*-

from odoo import models, fields, api

class ems_space(models.Model):
	_name = "ems.space"
	_description = "Space: where each student group are assigned to."
	_rec_names_search = ['name', 'code']
	_sql_constraints = [
		('unique_code', 'unique (work_location_id, code)', 'duplicated code!')
    ]
	
	code = fields.Char(string="Code", required=True)
	name = fields.Char(string="Name", required=True)
	space_type_id = fields.Many2one(string="Type", comodel_name="ems.space_type", required=True)
	work_location_id = fields.Many2one(string="Work location", comodel_name="hr.work.location", required=True)	

	@api.depends('name', 'code') #Recalculate the display_name field each time name or code changes.
	def _compute_display_name(self):
		for rec in self:
			rec.display_name = f"{rec.name} ({rec.code})" if rec.code else rec.name
