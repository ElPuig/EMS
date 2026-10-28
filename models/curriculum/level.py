# -*- coding: utf-8 -*-

from odoo import api, fields, models

# Dark enough for white text, and far apart from each other so two levels are never mixed up.
CARD_COLORS = {
	'ESO': '#1565C0',
	'BTX': '#6A1B9A',
	'CFGB': '#EF6C00',
	'CFGM': '#2E7D32',
	'CFGS': '#C62828',
	'EFPS': '#00838F',
	'PFI': '#795548',
}
DEFAULT_CARD_COLOR = '#546E7A'


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

	# The level band's colour on the student card (issue #524), which the teacher at the door reads
	# to let a student out at break time. Computed from the acronym only when the level is created,
	# then the centre's to change: not in data/cat/ems.level.csv, so an upgrade never reverts it.
	card_color = fields.Char(string="Student card colour", compute="_compute_card_color", store=True,
		readonly=False, help="Colour of this level's band on the student card.")

	notes = fields.Text(string="Notes")

	@api.depends('acronym')
	def _compute_card_color(self):
		for level in self:
			if not level.card_color:
				level.card_color = CARD_COLORS.get(level.acronym, DEFAULT_CARD_COLOR)

	@api.depends('acronym', 'name')
	def _compute_display_name(self):
		for level in self:
			acronym = level.acronym or ''
			name = level.name or ''
			level.display_name = f"{acronym}: {name}".strip(': ')