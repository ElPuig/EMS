# -*- coding: utf-8 -*-

import math, pytz
from datetime import datetime, time
from odoo import models, fields, api
from odoo.exceptions import UserError

class ims_attendance_schedule(models.Model):
	_name = "ims.attendance_schedule"
	_description = "Attendance schedule: concretes the weekdays data."
	_order = 'name asc'
	
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

	#Storing as dates is required due to timezones
	start_date = fields.Datetime(required=True)	
	end_date = fields.Datetime(required=True)
	
	space_id = fields.Many2one(string="Space", comodel_name="ims.space", required=True)
	attendance_template_id = fields.Many2one(string="Template", comodel_name="ims.attendance_template")	
	attendance_session_ids = fields.One2many(string="Sessions", comodel_name="ims.attendance_session", inverse_name="attendance_schedule_id")	
		
	notes = fields.Text(string="Notes")

	@api.depends("attendance_template_id", "weekday", "start_time", "end_time")
	def _compute_name(self):			
		for rec in self:			
			end_time = math.modf(rec.end_time)	
			start_time = math.modf(rec.start_time)				
			weekday_str = rec._fields['weekday'].convert_to_export(rec.weekday, rec)
			rec.name = "%s | %s | %02d:%02d - %02d:%02d" % (rec.attendance_template_id.name_get()[0][1], weekday_str, int(start_time[1]), round(start_time[0]*60), int(end_time[1]), round(end_time[0]*60))

	@api.onchange("start_time")
	def _onchange_start_time(self):			
		for rec in self:
			rec.start_date = rec._time_float_to_utc_datetime(rec.attendance_template_id.start_date, rec.start_time)
	
	@api.onchange("end_time")
	def _onchange_end_time(self):			
		for rec in self:
			rec.end_date = rec._time_float_to_utc_datetime(rec.attendance_template_id.end_date, rec.end_time)	

	def _time_float_to_utc_datetime(self, template_date, schedule_time):
		split_time = math.modf(schedule_time)				
		return self._convert_to_utc_date(datetime(template_date.year, template_date.month, template_date.day, int(split_time[1]), round(split_time[0]*60), 0))

	def _convert_to_utc_date(self, local_date):
		user_time_zone = self.env.context["tz"] # can be fetched form logged in user if it is set 
		local = pytz.timezone(user_time_zone) 
		start_date = local.localize(local_date, is_dst=None) # start_date is a naive datetime 
		start_date = start_date.astimezone(pytz.utc) 		
		return datetime(start_date.year, start_date.month, start_date.day, start_date.hour, start_date.minute, 0, tzinfo=None)	
