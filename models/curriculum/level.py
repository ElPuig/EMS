# -*- coding: utf-8 -*-

from odoo import api, fields, models

# The student card's level colours: pastel, so the card is not garish, and never red or green, which
# the card keeps for "may / may not leave the centre". A closed palette, so no level can pick them.
CARD_PALETTE = {
	'blue': '#BBDEFB',
	'lavender': '#D1C4E9',
	'peach': '#FFE0B2',
	'yellow': '#FFF3B0',
	'cyan': '#B2EBF2',
	'sand': '#E6D5C3',
	'orchid': '#E1BEE7',
	'grey': '#CFD8DC',
}
CARD_COLORS = {
	'ESO': 'blue',
	'BTX': 'lavender',
	'CFGB': 'peach',
	'CFGM': 'yellow',
	'CFGS': 'cyan',
	'EFPS': 'sand',
	'PFI': 'orchid',
}
DEFAULT_CARD_COLOR = 'grey'


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

	# The level's colour on the student card (issue #524). Computed from the acronym only when the
	# level is created, then the centre's to change: not in data/cat/ems.level.csv, so an upgrade
	# never reverts it.
	card_color = fields.Selection([
		('blue', "Blue"),
		('lavender', "Lavender"),
		('peach', "Peach"),
		('yellow', "Yellow"),
		('cyan', "Cyan"),
		('sand', "Sand"),
		('orchid', "Orchid"),
		('grey', "Grey"),
	], string="Student card colour", compute="_compute_card_color", store=True, readonly=False,
		help="Colour of this level on the student card. Red and green are not offered: the card "
		     "uses them to say whether the student may leave the centre.")

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