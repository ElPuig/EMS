# -*- coding: utf-8 -*-

from odoo import api, fields, models

from ..employees.non_teaching_type import LEVEL_DECLARATION_CODES

# Issue #723: seeded once (post_init_hook and migrations/18.0.0.43.0), then configured by the centre.
LEVEL_DECLARATION_SEED = {
	'ESO': 'eso', 'BTX': 'bat', 'CFGB': 'cfgb', 'CFGM': 'cfgm', 'CFGS': 'cfgs', 'EFPS': 'cefp', 'PFI': 'pfi',
}

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

	declaration_code = fields.Selection(selection=LEVEL_DECLARATION_CODES, string="Schedule declaration code",
		help="Row of the summary table of the official schedule declaration this level's teaching hours are "
			"added to. Empty: they go to 'Altres'.")

	notes = fields.Text(string="Notes")

	@api.depends('acronym', 'name')
	def _compute_display_name(self):
		for level in self:
			acronym = level.acronym or ''
			name = level.name or ''
			level.display_name = f"{acronym}: {name}".strip(': ')

	@api.model
	def _ems_seed_declaration_codes(self):
		"""Issue #723: the official code of the catalog's levels, by their acronym."""
		for level in self.search([('acronym', 'in', list(LEVEL_DECLARATION_SEED))]):
			level.declaration_code = LEVEL_DECLARATION_SEED[level.acronym]
