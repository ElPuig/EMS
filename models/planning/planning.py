# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError

class ims_planning(models.Model):
	_name = "ims.planning"
	_description = "Planning: Curriculum deployment in the classroom (in development: just for grading ponderation at the moment)."

	#TODO: For now, only for grading ponderation. 
	
	#TODO:	Multiple teachers as planning redactors.
	#		Needed a review and approval system (like minutes will do).
	# teacher_id = fields.Many2one(string="Teacher", comodel_name="hr.employee", required=True, domain="[('employee_type', '=', 'teacher')]")
	name = fields.Char(string="Name", related='subject_id.display_name', store=True)
	subject_id = fields.Many2one(string="Subject", comodel_name="ims.subject", required=True)
	planning_outcome_ids = fields.One2many(string="Outcome ponderation", comodel_name="ims.planning_outcome", inverse_name="planning_id")		

	@api.constrains("planning_outcome_ids")
	def check_ponderation(self):
		for rec in self:
			total = 0
			for pc in rec.planning_outcome_ids:
				total += pc.ponderation
			if total != 100:
				raise ValidationError("The ponderation values must sum 100.")
	
	@api.onchange('subject_id')
	def _onchange_planning_outcome_ids(self):
		for rec in self:			
			rec.planning_outcome_ids = False

	# TODO: delete cascade (planning_outcome_ids)