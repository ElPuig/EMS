# -*- coding: utf-8 -*-

from odoo import api, fields, models

from ..employees.non_teaching_type import LEVEL_DECLARATION_CODES

# The educational stage a level belongs to, as the regulation sets it (issue #726): EMS decides with
# it what applies to the level's students (e.g. the ex officio withdrawal protocol).
EDUCATION_STAGES = [
	('compulsory', 'Compulsory education'),
	('post_compulsory', 'Post-compulsory education'),
]

# Seeded once on a new installation (post_init_hook), then configured by the centre in Settings.
CONVALIDATION_LEVEL_SEED = ['CFGM', 'CFGS']

# The student card's level colours: pastel, so the card is not garish, and never red or green, which
# the card keeps for "may / may not leave the centre". A closed palette, so no level can pick them.
CARD_PALETTE = {  # key: (label, colour)
	'blue': ("Blue", '#BBDEFB'),
	'lavender': ("Lavender", '#D1C4E9'),
	'peach': ("Peach", '#FFE0B2'),
	'yellow': ("Yellow", '#FFF3B0'),
	'cyan': ("Cyan", '#B2EBF2'),
	'sand': ("Sand", '#E6D5C3'),
	'orchid': ("Orchid", '#E1BEE7'),
	'grey': ("Grey", '#CFD8DC'),
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

	# Set by the Departament (issue #751), so part of EMS's catalog (data/cat/ems.level.csv) and read-only
	# on the form, like education_stage.
	declaration_code = fields.Selection(selection=LEVEL_DECLARATION_CODES, string="Schedule declaration code",
		help="Row of the summary table of the official schedule declaration this level's teaching hours are "
			"added to. Empty: they go to 'Altres'.")

	# Set by the regulation, so part of EMS's catalog (data/cat/ems.level.csv) and read-only on the form.
	education_stage = fields.Selection(selection=EDUCATION_STAGES, string="Educational stage",
		help="Compulsory or post-compulsory education, as the regulation sets it.")

	# The level's colour on the student card (issue #524). Computed from the acronym only when the
	# level is created, then the centre's to change: not in data/cat/ems.level.csv, so an upgrade
	# never reverts it.
	card_color = fields.Selection(
		[(key, label) for key, (label, _colour) in CARD_PALETTE.items()], string="Student card colour",
		compute="_compute_card_color", store=True, readonly=False,
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

	@api.model
	def _ems_seed_convalidation_levels(self):
		"""A new installation starts with the vocational training cycles allowing convalidations;
		from then on the centre sets the list in Settings > Convalidations."""
		self.search([('acronym', 'in', CONVALIDATION_LEVEL_SEED)]).allows_convalidation = True
