# -*- coding: utf-8 -*-

import math, pytz
from datetime import datetime, time
from odoo import models, fields, api
from odoo.exceptions import UserError

class ems_attendance_schedule(models.Model):
	_name = "ems.attendance_schedule"
	_description = "Attendance schedule: concretes the weekdays data."
	_order = 'name asc'
	_inherit = ['ems.utils']
	
	# Note: today.weekday() returns this values, do not alter!
	weekdays_selection=[
		("0", "Monday"),
        ("1", "Tuesday"),
        ("2", "Wednesday"),
        ("3", "Thursday"),
        ("4", "Friday"),
		("5", "Saturday"),
		("6", "Sunday")
    ]

	name = fields.Char(string="Name", compute="_compute_name", store=True) #Used to sort the dropdown within the session form
	weekday = fields.Selection(string="Weekday", selection=weekdays_selection, default="1", required=True)

	start_time = fields.Float(string="Start Time", required=True)
	end_time = fields.Float(string="End Time", required=True)

	#Storing as dates is required due to timezones (required is not true because it fails on saving, but I don't know why...).
	start_date = fields.Datetime(compute="_compute_start_date", store=True)	
	end_date = fields.Datetime(compute="_compute_end_date", store=True)
	
	space_id = fields.Many2one(string="Space", comodel_name="ems.space", required=True)
	attendance_template_id = fields.Many2one(string="Template", comodel_name="ems.attendance_template", ondelete='cascade', required=True)	
	attendance_session_ids = fields.One2many(string="Sessions", comodel_name="ems.attendance_session", inverse_name="attendance_schedule_id")	
	
	# The teacher_id is used just for permission filtering pruposes.
	teacher_id = fields.Many2one(string='Teacher', related="attendance_template_id.teacher_id", store=False) 
	
	notes = fields.Text(string="Notes")

	@api.depends("attendance_template_id", "weekday", "start_time", "end_time")
	def _compute_name(self):			
		for rec in self:			
			end_time = math.modf(rec.end_time)	
			start_time = math.modf(rec.start_time)				
			weekday_str = rec._fields['weekday'].convert_to_export(rec.weekday, rec)
			rec.name = "%s | %s | %02d:%02d - %02d:%02d" % (rec.attendance_template_id.display_name, weekday_str, int(start_time[1]), round(start_time[0]*60), int(end_time[1]), round(end_time[0]*60))

	@api.depends("start_time", "attendance_template_id.start_date")
	def _compute_start_date(self):			
		for rec in self:
			rec.start_date = rec.time_float_to_datetime(rec.attendance_template_id.start_date, rec.start_time)
	
	@api.depends("end_time", "attendance_template_id.end_date")
	def _compute_end_date(self):			
		for rec in self:
			rec.end_date = rec.time_float_to_datetime(rec.attendance_template_id.end_date, rec.end_time)