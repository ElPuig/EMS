# -*- coding: utf-8 -*-

from odoo import models, fields, api

survey_recipient_selection = [("students", "Students"), ("teachers", "Teachers"), ("asp", "ASP")]

class ems_limesurvey_header(models.Model):
	_name = "ems.limesurvey_header"
	_description = "LimeSurvey header: contains the survey's header and its content."
	_inherit = ['ems.base']
	
	name = fields.Char(string="Name", required=True)
	recipient = fields.Selection(string="Recipient", selection=survey_recipient_selection)
	level = fields.Many2many(string="Level", comodel_name="ems.level")
	tsv_raw_text = fields.Text(string="Header's content (tab separated)", required=True)
	limesurvey_block_ids = fields.One2many(string="Blocks", comodel_name="ems.limesurvey_block", inverse_name="limesurvey_header_id")
	notes = fields.Text(string="Notes")

	@api.depends("name", "recipient", "level")
	def _compute_display_name(self):			
		for rec in self:				
			recipient = dict(survey_recipient_selection).get(rec.recipient)		
			if not rec.level and not rec.recipient:
				rec.display_name = "" if not rec.name else rec.name
			elif not rec.level:
				rec.display_name = "%s: %s" % (rec.name, recipient)
			else:
				levels = []
				for l in rec.level:
					levels.append(l.acronym)
				level_str = str.join(", ", levels)
				
				rec.display_name = "%s: %s (%s)" % (rec.name, recipient, level_str) if rec.recipient else "%s (%s)" % (rec.name, level_str)

class ems_limesurvey_block(models.Model):
	_name = "ems.limesurvey_block"
	_description = "LimeSurvey block: contains the main data about a LimeSurvey's session block."
	_order = 'sort, id'
	_inherit = ['ems.base']
	
	name = fields.Char(string="Name", required=True)
	tsv_raw_text = fields.Text(string="Block's content (tab separated)", required=True)
	limesurvey_header_id = fields.Many2one(string="Survey", comodel_name="ems.limesurvey_header")
	sort = fields.Integer(string="Sort", default=1)
	special = fields.Boolean(string="Special behaviour", default=False)
	special_course = fields.Integer(string="Course", default=1)
	special_wpi_enrolled = fields.Boolean(string="WorkPlace Intership (if enrolled)", default=False)
	special_subject_enrolled = fields.Boolean(string="Subject (all enrolled)", default=False)
	notes = fields.Text(string="Notes")	

