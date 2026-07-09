# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime

class ems_course(models.Model):
	_name = "ems.course"
	_description = "Course: defines a range of time when a course is running (for example: 2024-2025)."
	_sql_constraints = [
		('unique_course_name', 'unique (name)', 'duplicated course!')
    ]
	
	name = fields.Char(string="Name", compute="_compute_name", store=True)
	start = fields.Integer(string="Start", default=lambda self: datetime.now().year, required=True)
	end = fields.Integer(string="End", default=lambda self: datetime.now().year+1, required=True)	

	# 1. Operational Course: For day-to-day operations (Attendance, Grades, Incidents)
	is_current = fields.Boolean(
		string="Current (Operational)", 
		help="Check this box if this course is currently active for daily academic management."
	)

	# 2. Enrollment default Course: For enrollments and new registrations
	is_enrollment_default = fields.Boolean(
		string="Enrollment Default", 
		help="Check this box if this is the default course for new enrollments (usually the upcoming academic year)."
	)

	@api.depends("start", "end")
	def _compute_name(self):			
		for rec in self:						
			rec.name = "%s-%s" % (rec.start, rec.end)

	# CONSTRAINTS (Only one active per type) ---
	@api.constrains('is_current')
	def _check_unique_current(self):
		for rec in self:
			if rec.is_current:
				# Search if another record is already marked as Current excluding the current one
				others = self.search([
					('is_current', '=', True), 
					('id', '!=', rec.id)
				])
				if others:
					raise ValidationError(_("Configuration Error! There can be only one Course marked as 'Current (Operational)' at a time."))

	@api.constrains('is_enrollment_default')
	def _check_unique_enrollment_default(self):
		for rec in self:
			if rec.is_enrollment_default:
				# Search if another record is already marked as Enrollment Default excluding the current one
				others = self.search([
					('is_enrollment_default', '=', True), 
					('id', '!=', rec.id)
				])
				if others:
					raise ValidationError(_("Configuration Error! There can be only one Course marked as 'Enrollment Default' at a time."))
