# -*- coding: utf-8 -*-

import math, pytz
from datetime import datetime
from odoo import models, fields, api
from odoo.exceptions import ValidationError
from .attendance_schedule import ems_attendance_schedule

#from attendance_session import ems_attendance_session

class ems_attendance_session(models.Model):
	_name = "ems.attendance_session"
	_description = "Attendance session: contains the data about every session done with the students."		
	_inherit = ['ems.utils']	
	_sql_constraints = [
		# TODO: localize this (the same message appears in form).
        (
            'attendance_session_is_duped',
            'UNIQUE(date, attendance_schedule_id)',
            'The current session already exists. Please, edit the existing one (maybe has been created by another teacher) or choose another available session.' # El mensaje de error
        )
    ]
	
	# NOTE: This is an statistical data model, should be unaltered if master-data (template, etc.) changes, so the parent data will be copied.		
	weekday = fields.Selection(string="Weekday", compute="_compute_weekday", selection=ems_attendance_schedule.weekdays_selection, store=True)
	start_time = fields.Float("Start Time", compute="_compute_start_time", store=True)
	end_time = fields.Float("End Time", compute="_compute_end_time", store=True)	
	
	level_id = fields.Many2one(string="Level", comodel_name="ems.level", compute="_compute_level_id", store=True)
	study_id = fields.Many2one(string="Study", comodel_name="ems.study", compute="_compute_study_id", store=True)
	group_id = fields.Many2one(string="Group", comodel_name="ems.group", compute="_compute_group_id", store=True)
	subject_id = fields.Many2one(string="Subject", comodel_name="ems.subject", compute="_compute_subject_id", store=True)
	space_id = fields.Many2one(string="Space", comodel_name="ems.space", compute="_compute_space_id", store=True)
	template_teacher_id = fields.Many2one(string="Template's teacher", comodel_name="hr.employee", compute="_compute_template_teacher_id", store=True)
	session_teacher_id = fields.Many2one(string="Session's teacher", comodel_name="hr.employee", domain="[('employee_type', '=', 'teacher')]", required=True, default=lambda self: self._default_teacher_id(), store=True)
	
	date = fields.Date(string="Date", default=fields.Datetime.now, required=True)
	mode = fields.Selection(string="Mode", selection=[('scheduled', 'Scheduled'), ('guard', 'Guard'), ('manual', 'Manual')], default="scheduled", required=True)
		
	attendance_status_ids = fields.One2many(string="Statuses", comodel_name="ems.attendance_status", inverse_name="attendance_session_id")		
	attendance_schedule_id = fields.Many2one(string="Session", comodel_name="ems.attendance_schedule", required=True)			
	allowed_attendance_schedule_ids = fields.Many2many(comodel_name='ems.attendance_schedule', store=False)	
	
	display_warning = fields.Boolean(default=lambda self: self._default_display_warning(), store=False)	
	is_duped = fields.Boolean(store=False)
	is_next = fields.Boolean(store=False)

	notes = fields.Text("Notes")	

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
	
	@api.depends('attendance_schedule_id', 'date')
	def _compute_display_name(self):              
		for rec in self:
			rec.display_name = "%s | %s | %s" % (rec.attendance_schedule_id.display_name, rec.date, rec.space_id.name)

	@api.onchange("mode")
	def _onchange_mode(self):
		for rec in self:
			ids = []		
			for allowed in self._get_allowed_attendance_schedule_ids():				
				ids.append(allowed.id)
			rec.write({'allowed_attendance_schedule_ids' : [(6, 0, ids)]})
			rec.attendance_schedule_id = False if len(rec.allowed_attendance_schedule_ids) == 0 else rec.allowed_attendance_schedule_ids[0]
		
	@api.onchange("attendance_schedule_id")	
	def _onchange_attendance_schedule_id(self):		
		for rec in self:			
			students = []
			rec.is_next = False
			rec.is_duped = False
			
			for attendance_status in rec.attendance_status_ids:
				# Unlink previous students
				students.append([3, attendance_status.id])

			if rec.attendance_schedule_id.id != False:
				schedule_id = rec.attendance_schedule_id.id if isinstance(rec.attendance_schedule_id.id, int) else rec.attendance_schedule_id.id.origin
				rec.is_duped = self.env["ems.attendance_session"].search([("date", "=", datetime.now()), ("attendance_schedule_id.id", "=", schedule_id)]) or False
								
				# NOTE: the first approach was to check if start_date of current == end_date of previous, but what happens if there's a coffe break between sessions?	
				#		its better to check if the same subject has been teached previously and load the same data (maybe there's a gap between, but the student assistance 
				# 		data should be almost the same). Let's test this behaviour (I seems like the easiest and les complex approach) and see...				
				previous = self.env["ems.attendance_session"].search(
					[
						("date", "=", datetime.now()), 						
						("attendance_schedule_id.attendance_template_id.id", "=", rec.attendance_schedule_id.attendance_template_id.id),
						("attendance_schedule_id.weekday", "=", rec.attendance_schedule_id.weekday)
					], order="end_time DESC") or False				
				
				if previous:
					end = self.time_float_to_utc_time_float(previous[0].end_time)					
					rec.is_next = (end <= self.time_to_float(datetime.now().time()))	

					if rec.is_next:
						# Load new entries but with the previous session's data
						for prev in previous.attendance_status_ids:					
							students.append([0, 0, {
								"student_id": prev.student_id,
								"status": prev.status,
								"notes": prev.notes
							}])
						
			if not rec.is_next:
				# Load empty entries
				for student in rec.attendance_schedule_id.attendance_template_id.student_ids:
					# Sources: 
					# 	https://stackoverflow.com/a/70843263
					#	https://www.odoo.com/ro_RO/forum/suport-1/how-to-insert-value-to-a-one2many-field-in-table-with-create-method-28714
					
					# Linking new students
					students.append([0, 0, {
						"student_id": student
					}])	
			
			# NOTE: if duped, avoid next message.
			if rec.is_duped: rec.is_next = False
			rec.write({"attendance_status_ids": students})

	def _default_teacher_id(self):							
		return self.env["hr.employee"].search([("user_id", "=", self.env.uid), ("employee_type", "=", "teacher")]) or False

	def _default_display_warning(self):						
		attendance_schedule_records = self._get_allowed_attendance_schedule_ids()
		return self.id == False and len(attendance_schedule_records) != 1
	
	def _get_allowed_attendance_schedule_ids(self):		
		# TODO: this method is called twice on load, one from the _default_display_warning and the other one from _onchange_guard_mode
		# 		the context (self.context) is not shared because there calls come from different instances, so I 
		# 		can't share the registers in order to avoid duped calls...
		today = datetime.now()		
		where = [("start_date", "<=", today), ("end_date", ">=", today)]	
		
		if self.mode == "manual" and not self.env.user.has_group('ems.group_admin'):
			where.append(("teacher_id.user_id", "=", self.env.uid))
		elif self.mode != "manual":
			where.append(("weekday", "=", today.weekday()))
			where.append(("teacher_id.user_id", "!=" if self.mode == "guard" else "=", self.env.uid))

		# NOTE: the file security/rules.xml should define which records can be loaded depeding on the current user, BUT all records must be avaliable (read only) on guard mode, so it will be filtered here. 		
		regs = self.env["ems.attendance_schedule"].search(where)
		
		if self.mode == "manual": 
			return regs
		else:
			# NOTE: I wasn't able to filter the search by hour-range, so ill do it manually
			current = []
			for r in regs:
				start = r.start_date.time()
				end = r.end_date.time()
				now = today.time()
				if now >= start and now < end:
					current.append(r)		
			return current			
	