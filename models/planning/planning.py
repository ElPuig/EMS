# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError

class ems_planning(models.Model):
	_name = "ems.planning"
	_description = "Planning: Curriculum deployment in the classroom (in development: just for grading ponderation at the moment)."
	_sql_constraints = [
		('unique_subject_id', 'unique (subject_id)', 'duplicated subject!')
    ]

	#TODO: For now, only for grading ponderation. 
	#TODO:	Multiple teachers as planning redactors.
	#		Needed a review and approval system (like minutes will do).
	# teacher_id = fields.Many2one(string="Teacher", comodel_name="hr.employee", required=True, domain="[('employee_type', '=', 'teacher')]")
	name = fields.Char(string="Name", compute="_compute_name", store=True)
	study_id = fields.Many2one(string="Study", comodel_name="ems.study", required=True)	
	subject_id = fields.Many2one(string="Subject", comodel_name="ems.subject", required=True)	
	allowed_subject_ids = fields.Many2many(related="study_id.subject_ids", store=False) 
	planning_outcome_ids = fields.One2many(string="Outcome ponderation", comodel_name="ems.planning_outcome", inverse_name="planning_id")
	internal_ponderation = fields.Float(string="Internal grading ponderation (%)", default=90.0, required=True)
	external_ponderation = fields.Float(string="External grading ponderation (%)", default=10.0, required=True)

	@api.constrains("planning_outcome_ids", "internal_ponderation", "external_ponderation")
	def check_ponderation(self):
		for rec in self:
			total = 0
			for pc in rec.planning_outcome_ids:
				total += pc.ponderation			
			if round(total,2) != 100:
				raise ValidationError("The outcome ponderation values must sum 100.")
			if round(rec.internal_ponderation + rec.external_ponderation, 2) != 100:
				raise ValidationError("The main ponderation values must sum 100.")
	
	@api.onchange('subject_id')
	def _onchange_planning_outcome_ids(self):
		for rec in self:
			if rec.subject_id.id != False:			
				rec.planning_outcome_ids = False				
				
				count = len(rec.subject_id.outcome_ids)
				pond = round(100 / count, 2)								
				last = round(100 - pond * (count - 1), 2)

				for i, oc in enumerate(rec.subject_id.outcome_ids):
					rec.write({
						'planning_outcome_ids': [(0, 0, {
							"planning_id": rec.id, 
							"outcome_id": oc.id,
							"ponderation": pond if i < count - 1 else last
						})]
					})

	@api.depends("study_id", "subject_id")
	def _compute_name(self):			
		for rec in self:						
			rec.name = "%s  %s" % (rec.study_id.acronym, rec.subject_id.display_name)
