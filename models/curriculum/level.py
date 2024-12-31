# -*- coding: utf-8 -*-

from odoo import models, fields, api

class ems_level(models.Model):
	_name = "ems.level"
	_description = "Level: Defines the studies level (University, VET, etc.)."
	
	acronym = fields.Char(string="Acronym", required=True)
	name = fields.Char(string="Name", required=True)
	study_ids = fields.One2many(string="Studies", comodel_name="ems.study", inverse_name="level_id")

	notes = fields.Text(string="Notes")

	@api.depends('acronym', 'name')
	def _compute_display_name(self):              
		for rec in self:
			rec.display_name = "%s: %s" % (rec.acronym, rec.name)