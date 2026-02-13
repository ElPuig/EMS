# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class ems_attendance_schedule(models.Model):
	_name = "ems.attendance_schedule"
	_description = "Attendance schedule: concretes the weekdays data."
	_order = 'name asc'
	_inherit = ['ems.base', 'ems.datetime_utils']
	
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

	name = fields.Char(string="Name", compute="_compute_name", store=True) #Used to sort the dropdown within the session form, otherwise the SQL sort won't work.
	weekday = fields.Selection(string="Weekday", selection=weekdays_selection, default="1", required=True)

	start_time = fields.Float(string="Start Time", required=True)
	end_time = fields.Float(string="End Time", required=True)

	#Storing as dates is required due to timezones (required is not true because it fails on saving, but I don't know why...).
	start_date = fields.Datetime(compute="_compute_start_date", store=True)	
	end_date = fields.Datetime(compute="_compute_end_date", store=True)
	
	space_id = fields.Many2one(string="Space", comodel_name="ems.space", required=True)
	attendance_template_id = fields.Many2one(string="Template", comodel_name="ems.attendance_template", ondelete='cascade', required=True)	
	attendance_session_ids = fields.One2many(string="Sessions", comodel_name="ems.attendance_session_header", inverse_name="attendance_schedule_id")	
	
	# The teacher_id is used just for permission filtering pruposes.
	teacher_id = fields.Many2one(string='Teacher', related="attendance_template_id.teacher_id", store=False) 
	
	time_range = fields.Char(compute="_compute_time_range", store=True)
	notes = fields.Text(string="Notes")

	@api.depends("start_time", "end_time")
	def _compute_time_range(self):			
		for rec in self:
			end = rec.utc_datetime_to_local(rec.end_date)
			start = rec.utc_datetime_to_local(rec.start_date)
			rec.time_range = "%02d:%02d - %02d:%02d" % (start.hour, start.minute, end.hour, end.minute)
	
	@api.depends("start_time", "attendance_template_id.start_date")
	def _compute_start_date(self):			
		for rec in self:
			local = rec.time_float_to_local_datetime(rec.attendance_template_id.start_date, rec.start_time)
			utc = rec.local_datetime_to_utc(local)
			rec.start_date = rec.datetime_to_odoo(utc)
	
	@api.depends("end_time", "attendance_template_id.end_date")
	def _compute_end_date(self):			
		for rec in self:
			local = rec.time_float_to_local_datetime(rec.attendance_template_id.end_date, rec.end_time)
			utc = rec.local_datetime_to_utc(local)
			rec.end_date = rec.datetime_to_odoo(utc)

	@api.depends("attendance_template_id", "attendance_template_id.start_date", "attendance_template_id.end_date", "weekday", "start_time", "end_time")
	def _compute_name(self):			
		for rec in self:				
			weekday_str = dict(self.weekdays_selection).get(rec.weekday)
			#weekday_str = rec._fields['weekday'].convert_to_export(rec.weekday, rec)
			rec.name = "%s | %s | %s" % (rec.attendance_template_id.display_name, weekday_str, rec.time_range)
			rec.display_name = rec.name

	def unlink(self):
		if len(self.attendance_session_ids) > 0:
			raise ValidationError(_("This schedule have been already used to check the student's attendances and cannot be deleted. Please, update its data instead or archive the entire template and create a new one with the correct data."))
		return super().unlink()