# -*- coding: utf-8 -*-

from datetime import datetime
from odoo import models, fields, api
from .attendance_schedule import ems_attendance_schedule
from datetime import timedelta

#from attendance_session import ems_attendance_session

class ems_attendance_session(models.Model):
	_name = "ems.attendance_session"
	_description = "Attendance session: contains the data about every session done with the students."		
	_inherit = ['ems.utils', 'mail.thread', 'mail.activity.mixin']	
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
	
	date = fields.Date(string="Date", default=fields.Datetime.now, required=True)
	start_date = fields.Datetime(compute="_compute_start_date", store=True)	
	end_date = fields.Datetime(compute="_compute_end_date", store=True)

	level_id = fields.Many2one(string="Level", comodel_name="ems.level", compute="_compute_level_id", store=True)
	study_id = fields.Many2one(string="Study", comodel_name="ems.study", compute="_compute_study_id", store=True)
	group_id = fields.Many2one(string="Group", comodel_name="ems.group", compute="_compute_group_id", store=True)
	subject_id = fields.Many2one(string="Subject", comodel_name="ems.subject", compute="_compute_subject_id", store=True)
	space_id = fields.Many2one(string="Space", comodel_name="ems.space", compute="_compute_space_id", store=True)
	template_teacher_id = fields.Many2one(string="Template's teacher", comodel_name="hr.employee", compute="_compute_template_teacher_id", store=True)
	session_teacher_id = fields.Many2one(string="Session's teacher", comodel_name="hr.employee", domain="[('employee_type', '=', 'teacher')]", required=True, default=lambda self: self._default_teacher_id(), store=True)	
	mode = fields.Selection(string="Mode", selection=[('scheduled', 'Scheduled'), ('guard', 'Guard'), ('manual', 'Manual')], default="scheduled", required=True)
		
	attendance_status_ids = fields.One2many(string="Statuses", comodel_name="ems.attendance_status", inverse_name="attendance_session_id")		
	attendance_schedule_id = fields.Many2one(string="Session", comodel_name="ems.attendance_schedule", required=True)			
	allowed_attendance_schedule_ids = fields.Many2many(comodel_name='ems.attendance_schedule', store=False)	
	
	display_warning = fields.Boolean(default=lambda self: self._default_display_warning(), store=False)	
	is_duped = fields.Boolean(store=False)
	is_next = fields.Boolean(store=False)

	notes = fields.Text("Notes")	

	@api.model_create_multi
	def create(self, vals_list):
		records = super().create(vals_list)
		# NOTE: Tutors will receive a daily report but the notification to the families will be sent hours before that.
		#		It's important that, if a family contacts with the tutor, he/she can review the data even if this has not been sent yet
		#		(maybe we can ensure that a tutor can check the attendance entries of its own students, but this is a bit complex to prepare
		#		so right now its easier to check pending notifications). 
		# 		
		# 		Maybe we should create a new section called 'Daily Issues' and change the 'notification_xxx' model to 'issue_xxx' in order to allow
		#		quickly review options? Is the same as the current notification, but with its own section (like reports does).

		# TODO: test this
		notification_tutor_eta = 5 # TODO: compute this
		notification_status_eta = fields.Datetime.now() + timedelta(seconds=self.env.company.attendance_notification_delay * 60) # from minutes to seconds

		for record in records:
			for noti in record.create_notification_entries():
				# noti internal structure: attendance_notification_tutor (1) --> (N) attendance_notification_student (1) --> (N) attendance_notification_status
				# notifications for the tutors: daily (at the end if its tourn); notifications for the family (status): after a timeout (default 15 minutes). 

				noti.with_delay(
					eta = notification_tutor_eta,
					description=f"Notification task for the daily assistance report for tutors: '{noti.display_name}' (ID={noti.id})"
				).send_notification()

				for student in noti.attendance_notification_student_ids:
					for status in student.attendance_notification_status_ids:
						status.with_delay(
							eta = notification_status_eta,
							description=f"Notification task for the attendance session: '{status.display_name}' (ID={status.id})"
						).send_notification()
		return records

	def create_notification_entries(self):		
		separator = "; "
		notis = []
		
		for s in self.attendance_status_ids:
			lines = dict()
			if s.status in ['m_miss', 'a_issue'] and (s.student_id.auth_share or not s.student_id.is_adult):
				if s.student_id.tutor_id not in lines:
					lines[s.student_id.tutor_id] = []
				
				send_to = []
				for contact in s.student_id.child_ids:				
					send_to.append(contact.email)

				lines[s.student_id.tutor_id].append([0, 0, {													
					'attendance_status_id': s.id,
					'send_to': separator.join(send_to)
				}]) 

		if len(lines) > 0:
			for tutor_id in lines:		
				notis.append(
					s.sudo().env['ems.attendance_notification'].create({
						'attendance_session_id': self.id,
						'tutor_id': tutor_id.id,
						'attendance_notification_line_ids': lines[tutor_id]
					})
				)
		return notis	

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
	def _compute_start_date(self):			
		for rec in self:
			local = rec.time_float_to_local_datetime(rec.date, rec.start_time)
			utc = rec.local_datetime_to_utc(local)
			rec.start_date = rec.datetime_to_odoo(utc)
	
	@api.depends("attendance_schedule_id")
	def _compute_end_date(self):			
		for rec in self:
			local = rec.time_float_to_local_datetime(rec.date, rec.end_time)
			utc = rec.local_datetime_to_utc(local)
			rec.end_date = rec.datetime_to_odoo(utc)
			
	@api.depends("attendance_schedule_id")
	def _compute_level_id(self):
		for rec in self:
			rec.level_id = rec.attendance_schedule_id.attendance_template_id.sudo().level_id

	@api.depends("attendance_schedule_id")
	def _compute_study_id(self):
		for rec in self:
			rec.study_id = rec.attendance_schedule_id.attendance_template_id.sudo().study_id

	@api.depends("attendance_schedule_id")
	def _compute_group_id(self):
		for rec in self:
			rec.group_id = rec.attendance_schedule_id.attendance_template_id.sudo().group_id

	@api.depends("attendance_schedule_id")
	def _compute_subject_id(self):
		for rec in self:
			rec.subject_id = rec.attendance_schedule_id.attendance_template_id.sudo().subject_id

	@api.depends("attendance_schedule_id")
	def _compute_space_id(self):
		for rec in self:
			rec.space_id = rec.attendance_schedule_id.attendance_template_id.sudo().space_id

	@api.depends("attendance_schedule_id")
	def _compute_template_teacher_id(self):
		for rec in self:
			rec.template_teacher_id = rec.attendance_schedule_id.attendance_template_id.sudo().teacher_id
	
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
			rec.allowed_attendance_schedule_ids = [(6, 0, ids)]
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
				now = datetime.now()
				schedule_id = rec.attendance_schedule_id.id if isinstance(rec.attendance_schedule_id.id, int) else rec.attendance_schedule_id.id.origin
				rec.is_duped = self.env["ems.attendance_session"].search([("date", "=", now), ("attendance_schedule_id.id", "=", schedule_id)]) or False
								
				# NOTE: the first approach was to check if start_date of current == end_date of previous, but what happens if there's a coffe break between sessions?	
				#		its better to check if the same subject has been teached previously and load the same data (maybe there's a gap between, but the student assistance 
				# 		data should be almost the same). Let's test this behaviour (I seems like the easiest and les complex approach) and see...				
				previous = self.env["ems.attendance_session"].search(
					[
						("date", "=", datetime.now()), 						
						("attendance_schedule_id.attendance_template_id.id", "=", rec.attendance_schedule_id.attendance_template_id.sudo().id),
						("attendance_schedule_id.weekday", "=", rec.attendance_schedule_id.weekday)
					], order="end_time DESC") or False				
				
				if previous:
					end = previous[0].end_time
					rec.is_next = (end <= self.time_to_float(now.time()))	

					if rec.is_next:
						# Load new entries but with the previous session's data
						for prev in previous.attendance_status_ids:					
							students.append([0, 0, {
								"student_id": prev.student_id,
								"status": "a_attended" if prev.status == "a_delayed" else prev.status,
								"notes": prev.notes
							}])
						
			if not rec.is_next:
				# Load empty entries
				for student in rec.attendance_schedule_id.attendance_template_id.sudo().student_ids:
					# Sources: 
					# 	https://stackoverflow.com/a/70843263
					#	https://www.odoo.com/ro_RO/forum/suport-1/how-to-insert-value-to-a-one2many-field-in-table-with-create-method-28714
					
					# Linking new students
					students.append([0, 0, {
						"student_id": student
					}])	
			
			# NOTE: if duped, avoid next message.
			if rec.is_duped: rec.is_next = False
			rec.attendance_status_ids = students

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

		# NOTE: the file security/rules.xml should define which records can be loaded depeding on the current user, 
		# BUT all records must be avaliable (read only) on guard mode, so sudo will be used. 		
		regs = self.sudo().env["ems.attendance_schedule"].search(where)
		
		if self.mode == "manual": 
			return regs
		else:					
			current = []
			for r in regs:
				# NOTE: I wasn't able to filter the search by hour-range due timezones, so ill do it manually
				# 		- Spain's summer period time: GMT+2 (UTC + 2h)
				#       - Spain's winter period time: GMT+1 (UTC + 1h)	
				# 		- Getting a winter's UTC current time won't fit when compared with a summer's UTC stored time.
				#		
				# 		SOLUTION: converting all UTC dates (the BBDD ones, as Odoo does) to local and compare. Less efficient,
				#		but the schedules entries have been filtered at maximum. 
				start = r.utc_datetime_to_local(r.start_date).time()
				end = r.utc_datetime_to_local(r.end_date).time()				
				now = r.utc_datetime_to_local(datetime.now()).time()
				if now >= start and now < end:
					current.append(r)		
			return current			
	