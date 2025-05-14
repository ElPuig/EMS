# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError

class ims_planning(models.Model):
	_name = "ims.planning"
	_description = "Planning: Curriculum deployment in the classroom (in development: just for grading ponderation at the moment)."
	_sql_constraints = [
		('unique_subject_id', 'unique (subject_id)', 'duplicated subject!')
    ]

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
			if round(total,2) != 100:
				raise ValidationError("The ponderation values must sum 100.")
	
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