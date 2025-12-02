# -*- coding: utf-8 -*-

from odoo import models, fields, api

class ems_space(models.Model):
	_name = "ems.space"
	_description = "Space: where each student group are assigned to."
	_rec_name = 'display_name'
	_sql_constraints = [
		('unique_code', 'unique (work_location_id, code)', 'duplicated code!')
    ]
	
	code = fields.Char(string="Code", required=True)
	name = fields.Char(string="Name", required=True)
	space_type_id = fields.Many2one(string="Type", comodel_name="ems.space_type", required=True)
	work_location_id = fields.Many2one(string="Work location", comodel_name="hr.work.location", required=True)
	display_name = fields.Char(string="Display Name", compute="_compute_display_name", store=False) #calculated field combining name and code

	@api.depends('name', 'code') #Recalculate the display_name field each time name or code changes.
	def _compute_display_name(self):
		for rec in self:
			rec.display_name = f"{rec.name} ({rec.code})" if rec.code else rec.name

	@api.model #Allows you to search by name or by code.
	def name_search(self, name='', args=None, operator='ilike', limit=100):
		if args is None:
			args = []
		name = name or ''
		operator = operator or 'ilike'
		limit = limit or 100

		domain = []
		if name:
			domain = ['|', ('name', operator, name), ('code', operator, name)]

		records = self.search(domain + args, limit=limit)
		return records.name_get()

	def name_get(self): 
		result = []
		for record in self:
			display_name = record.name
			if record.code:
				display_name = f"{record.name} ({record.code})"
			result.append((record.id, display_name))
		return result
