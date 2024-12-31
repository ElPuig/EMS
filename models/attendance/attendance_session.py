# -*- coding: utf-8 -*-

import math, pytz
from datetime import datetime, time
from odoo import models, fields, api
from odoo.exceptions import UserError
from .attendance_schedule import ems_attendance_schedule

#from attendance_session import ems_attendance_session

class ems_attendance_session(models.Model):
	_name = "ems.attendance_session"
	_description = "Attendance session: contains the data about every session done with the students."		
	_display_warning = fields.Boolean(default=lambda self: self._default_display_warning(), store=False)	
	
	# NOTE: This is an statistical data model, should be unaltered if master-data changes, so the parent data will be copied.		
	weekday = fields.Selection(string="Weekday", compute="_compute_weekday", selection=ems_attendance_schedule.weekdays_selection, store=True)
	start_time = fields.Float("Start Time", compute="_compute_start_time", store=True)
	end_time = fields.Float("End Time", compute="_compute_end_time", store=True)	
	
	level_id = fields.Many2one(string="Level", comodel_name="ems.level", compute="_compute_level_id", store=True)
	study_id = fields.Many2one(string="Study", comodel_name="ems.study", compute="_compute_study_id", store=True)
	group_id = fields.Many2one(string="Group", comodel_name="ems.group", compute="_compute_group_id", store=True)
	subject_id = fields.Many2one(string="Subject", comodel_name="ems.subject", compute="_compute_subject_id", store=True)
	space_id = fields.Many2one(string="Space", comodel_name="ems.space", compute="_compute_space_id", store=True)
	template_teacher_id = fields.Many2one(string="Template's teacher", comodel_name="hr.employee", compute="_compute_template_teacher_id", store=True)
	session_teacher_id = fields.Many2one(string="Session's teacher", comodel_name="hr.employee", compute="_compute_session_teacher_id", store=True)
	
	date = fields.Date(string="Date", default=fields.Datetime.now, required=True)
	guard_mode = fields.Boolean(string= "Guard mode", default=False, store=True)
	notes = fields.Text("Notes")
	
	attendance_status_ids = fields.One2many(string="Statuses", comodel_name="ems.attendance_status", inverse_name="attendance_session_id")	
	attendance_schedule_id = fields.Many2one(string="Session", comodel_name="ems.attendance_schedule", default=lambda self: self._default_attendance_schedule(), required=True)	

	@api.depends("attendance_schedule_id")
	def _compute_weekday(self):
		for rec in self:
			rec.weekday = rec.attendance_schedule_id.weekday

	@api.depends("attendance_schedule_id")
	def _compute_start_time(self):
		for rec in self:
			rec.start_time = rec.attendance_schedule_id.start_time

	@api.depends("attendance_schedule_id")
	def _compute_end_time(self):
		for rec in self:
			rec.end_time = rec.attendance_schedule_id.end_time

	@api.depends("attendance_schedule_id")
	def _compute_level_id(self):
		for rec in self:
			rec.level_id = rec.attendance_schedule_id.attendance_template_id.level_id

	@api.depends("attendance_schedule_id")
	def _compute_study_id(self):
		for rec in self:
			rec.study_id = rec.attendance_schedule_id.attendance_template_id.study_id

	@api.depends("attendance_schedule_id")
	def _compute_group_id(self):
		for rec in self:
			rec.group_id = rec.attendance_schedule_id.attendance_template_id.group_id

	@api.depends("attendance_schedule_id")
	def _compute_subject_id(self):
		for rec in self:
			rec.subject_id = rec.attendance_schedule_id.attendance_template_id.subject_id

	@api.depends("attendance_schedule_id")
	def _compute_space_id(self):
		for rec in self:
			rec.space_id = rec.attendance_schedule_id.attendance_template_id.space_id

	@api.depends("attendance_schedule_id")
	def _compute_template_teacher_id(self):
		for rec in self:
			rec.template_teacher_id = rec.attendance_schedule_id.attendance_template_id.teacher_id
	
	@api.depends("attendance_schedule_id")
	def _compute_session_teacher_id(self):		
		for rec in self:
			# NOTE: When loading the demo data, the root user fires this method			
			current_teacher = self.env["hr.employee"].search([("user_id", "=", self.env.uid)])
			rec.session_teacher_id = rec.template_teacher_id if current_teacher.name == False else current_teacher									

	def _default_attendance_schedule(self):
		attendance_schedule_records = self._get_attendance_schedule_records()
		return attendance_schedule_records[0] if len(attendance_schedule_records) == 1 else False

	def _default_display_warning(self):						
		attendance_schedule_records = self._get_attendance_schedule_records()
		return (self.id == False and len(attendance_schedule_records) != 1)
	
	def _get_attendance_schedule_records(self):		
		# TODO: this method is called twice, I tried to store the result somewhere in order to catch it and avoid duped queries, but I can't do it work properly :(
		today = datetime.now()
				
		# TODO: filter directly on search, I tried but didn't worked :(
		current = []
		regs = self.env["ems.attendance_schedule"].search([("attendance_template_id.teacher_id.user_id", "=", self.env.uid), ("weekday", "=", today.weekday()), ("start_date", "<=", today), ("end_date", ">=", today)])
		for r in regs:
			start = r.start_date.time()
			end = r.end_date.time()
			now = today.time()
			if now >= start and now < end:
				current.append(r)
		return current
		
	

	@api.onchange("guard_mode")
	def _onchange_guard_mode(self):		
		return {'domain': {'attendance_schedule_id': "[]" if self.guard_mode else "[('attendance_template_id.teacher_id.user_id', '=', uid)]"}}

	@api.onchange("attendance_schedule_id")	
	def _onchange_attendance_schedule_id(self):		
		for rec in self:
			students = []
			
			# TODO: rec.write({'attendance_status_ids' : [(6, 0, students)]}) --> '6' means unlink previous and link the new ones.

			for attendance_status in rec.attendance_status_ids:
				# Unlink previous students
				students.append([3, attendance_status.id])

			for student in rec.attendance_schedule_id.attendance_template_id.student_ids:
				# Sources: 
				# 	https://stackoverflow.com/a/70843263
				#	https://www.odoo.com/ro_RO/forum/suport-1/how-to-insert-value-to-a-one2many-field-in-table-with-create-method-28714
				
				# Linking new students
				students.append([0, 0, {
					"student_id": student
				}])	
			#self.write({"attendance_status_ids": students})
			rec.write({"attendance_status_ids": students})

	@api.depends('attendance_schedule_id', 'date')
	def _compute_display_name(self):              
		for rec in self:
			rec.display_name = "%s | %s | %s" % (rec.attendance_schedule_id.display_name, rec.date, rec.space_id.name)

	def convert_to_utc_date(self, local_date):
		user_time_zone = self.env.context["tz"] # can be fetched form logged in user if it is set 
		local = pytz.timezone(user_time_zone) 
		start_date = local.localize(local_date, is_dst=None) # start_date is a naive datetime 
		start_date = start_date.astimezone(pytz.utc) 
		return datetime(start_date.year, start_date.month, start_date.day, start_date.hour, start_date.minute, 0, tzinfo=None)

	# def print_sample_report(self):
	# 	data = {
	# 		'model_id': self.id,
	# 		'to_date': self.to_date,
	# 		'from_date': self.from_date,
	# 		'vehicle_id': self.vehicle_id.id,
	# 		'vehicle_name': self.vehicle_id.vehicle_name
	# 	}
	# 	# docids = self.env['purchase.order'].search([]).ids
	# 	return self.env.ref('module_name.action_report_vehicle_order).report_action(None, data=data)
					  
	# def action_report_truck_booking(self):
    #     query = """select pr.name,fv.name as truck,gt.name as goods,tb.from_location,tb.to_location,tb.distance,
    #             tb.weight,tb.unit,amount,tb.date,tb.state from truck_booking as tb
    #             inner join res_partner as pr on pr.id = tb.partner_id
    #             inner join fleet_vehicle_model as fv on fv.id = tb.truck_id
    #             inner join goods_type as gt on gt.id = tb.goods_type_id """
    #     if self.from_date:
    #         query += """ where tb.date >= '%s' and tb.date <= '%s'""" % self.from_date, % self.to_date
    #     self.env.cr.execute(query)
    #     report = self.env.cr.dictfetchall()
    #     data = {'date': self.read()[0],'report': report}
    #     return self.env.ref('module_name.action_report_booking').report_action(None, data=data)