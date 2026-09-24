# -*- coding: utf-8 -*-

from odoo import api, fields, models

class EmsLevel(models.Model):
	_name = "ems.level"
	_description = "Study level (Secondary Education, VET, Baccalaureate, etc.)"
	_order = "acronym asc"

	_sql_constraints = [
		('acronym_unique', 'UNIQUE(acronym)', 'The acronym must be unique.'),
	]

	acronym = fields.Char(string="Acronym", required=True)
	name = fields.Char(string="Name", required=True)
	study_ids = fields.One2many(string="Studies", comodel_name="ems.study", inverse_name="level_id")
	# Whether students of this level's studies can ask for subject convalidations
	# (ems.convalidation), from the portal or through the secretariat.
	allows_convalidation = fields.Boolean(string="Allows convalidations", default=False,
		help="Students of this level's studies can request subject convalidations.")

	notes = fields.Text(string="Notes")

	@api.depends('acronym', 'name')
	def _compute_display_name(self):
		for level in self:
			acronym = level.acronym or ''
			name = level.name or ''
			level.display_name = f"{acronym}: {name}".strip(': ')