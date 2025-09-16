# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import datetime

class ems_course(models.Model):
	_name = "ems.course"
	_description = "Course: defines a range of time when a course is running (for example: 2024-2025)."
	_sql_constraints = [
		('unique_course_name', 'unique (name)', 'duplicated course!')
    ]
	
	name = fields.Char(string="Name", compute="_compute_name", store=True)
	start = fields.Integer(string="Start", default=datetime.now().year, required=True)
	end = fields.Integer(string="End", default=datetime.now().year+1, required=True)	

	@api.depends("start", "end")
	def _compute_name(self):			
		for rec in self:						
			rec.name = "%s-%s" % (rec.start, rec.end)
