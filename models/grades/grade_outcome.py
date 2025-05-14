# -*- coding: utf-8 -*-

from odoo import models, fields, api

class ims_grade_outcome(models.Model):
	_name = "ims.grade_outcome"
	_description = "Grade (outcome): ternary relation between student-teacher-outcome."	

	student_id = fields.Many2one(string="Student", comodel_name="res.partner", required=True, domain="[('contact_type', '=', 'student')]")				
	teacher_id = fields.Many2one(string="Teacher", comodel_name="hr.employee", required=True, domain="[('employee_type', '=', 'teacher')]")
	outcome_id = fields.Many2one(string="Outcome", comodel_name="ims.outcome", required=True)
	round = fields.Selection(string="Round", default="1", required=True, selection=[("1", "1st round"), ("2", "2nd round"), ("3", "3rd round"), ("4", "4th round")])
	score = fields.Integer(string="Score", required=True)