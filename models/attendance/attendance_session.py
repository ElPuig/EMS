# -*- coding: utf-8 -*-

from odoo import models, fields, api
from .attendance_schedule import ems_attendance_schedule
from datetime import datetime, timedelta

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
	time_range = fields.Char("Time range", compute="_compute_time_range", store=True)

	date = fields.Date(string="Date", default=fields.Datetime.now, required=True)
	start_date = fields.Datetime(compute="_compute_start_date", store=True)	
	end_date = fields.Datetime(compute="_compute_end_date", store=True)

	# TODO: 
	# 		1. Remove unnecessary data. 
	# 		2. Related data should not be never removed, but archived. 
	# 		For example:	
	# 			1. New course, so new templates.
	#			2. Removing templates, removes also the schedules.
	#			3. Sessions are linked to schedules, so cannot be removed because never should be removed by cascade (only manually).
	# 			4. The same if a student's group is removed, it should really be archived.   
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
	def _compute_time_range(self):
		for rec in self:
			rec.time_range = rec.attendance_schedule_id.time_range

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
	
	# TODO:  should be related? Can a "sudo" be used within a related or is not needed?
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
								
				# NOTE: The first approach was to check if start_date of current == end_date of previous, but what happens if there's a coffe break between sessions?	
				#		Its better to check if the same subject has been teached previously and load the same data (maybe there's a gap between, but the student assistance 
				# 		data should be almost the same). 
				previous = self.env["ems.attendance_session"].search(
					[
						("date", "=", datetime.now()), 						
						("attendance_schedule_id.attendance_template_id.id", "=", rec.attendance_schedule_id.attendance_template_id.sudo().id),
						("attendance_schedule_id.weekday", "=", rec.attendance_schedule_id.weekday)
					], order="end_time DESC", limit=1)
				
				if previous:
					end = previous.end_time
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
	
	def _get_notification_tutor_eta(self):
		# TODO: tutor's working schedule end-time should be loaded firts, and use the default only if not defined. 
		notification_tutor_eta = self.time_float_to_utc_datetime(fields.Datetime.now(), self.env.company.attendance_issue_tutor_default)
		return self.datetime_to_odoo(notification_tutor_eta)
	
	def _get_notification_status_eta(self):
		return fields.Datetime.now() + timedelta(seconds=self.env.company.attendance_issue_status_delay * 60) # from minutes to seconds
	
	def _get_or_create_issue_status(self, issue_student, attendance_status_id, send_to):
		data = self.get_issue_status(attendance_status_id)
		repo = data["repo"]
		issue_status = data["values"]	
				
		if not issue_status:
			issue_status = repo.create({
				#'attendance_session_id': self.id,
				'attendance_status_id': attendance_status_id,
				'attendance_issue_student_id': issue_student.id,
				'send_to': send_to
			})
		return issue_status
	
	def _get_or_create_issue_student(self, issue_tutor, student_id):
		data = self.get_issue_student(issue_tutor, student_id)		
		repo = data["repo"]
		issue_student = data["values"]	

		if not issue_student:
			issue_student = repo.create({
				'student_id': student_id,
				'attendance_issue_tutor_id': issue_tutor.id
			})		
		return issue_student
	
	def _get_or_create_issue_tutor(self, tutor_id):
		data = self.get_issue_tutor(tutor_id)		
		repo = data["repo"]
		issue_tutor = data["values"]		
		
		if not issue_tutor:
			issue_tutor = repo.create({
				'tutor_id': tutor_id.id,
				'issue_date': datetime.today()						
			})
		return issue_tutor
	
	def _schedule_daily_assistance_notification(self, entry, eta):		
		daily = entry.with_delay(
			eta = eta,
			description=f"Daily assistance report: '{entry.display_name}' (ID={entry.id})"
		).send_notification()

		job = self.sudo().env['queue.job'].search([('uuid', '=', daily.uuid)]) or False
		if job: entry.sudo().write({'notification_id': job.id})

	def _schedule_family_assistance_notification(self, status, eta):		
		if not status.send_to or status.send_to == "": return				

		noti = status.with_delay(
			eta = eta,
			description=f"Family assistance notification: '{status.display_name}' (ID={status.id})"
		).send_notification()

		job = self.sudo().env['queue.job'].search([('uuid', '=', noti.uuid)]) or False
		if job: status.sudo().write({'notification_id': job.id})
	
	@api.model_create_multi
	def create(self, vals_list):
		records = super().create(vals_list)		
		
		# NOTE: Optional, but computed here for optimization
		notification_status_eta = self._get_notification_status_eta()
		notification_tutor_eta = self._get_notification_tutor_eta()

		for record in records:		
			# NOTE: Collecting all status data first allow some optimizations.	
			status_by_tutor = dict()			
			for as_id in record.attendance_status_ids:			
				record.collect_issue_status_data(as_id, status_by_tutor)

			record.create_notification_entries(status_by_tutor, notification_tutor_eta, notification_status_eta)
		return records
		
	def create_notification_entries(self, status_by_tutor, notification_tutor_eta=None, notification_status_eta=None):				
		if notification_tutor_eta is None: notification_tutor_eta = self._get_notification_tutor_eta()
		if notification_status_eta is None: notification_status_eta = self._get_notification_status_eta()

		# NOTE: Status data is grouped by tutor and only got the ones which should be notified. 
		notis = []
		for tutor_id in status_by_tutor:
			for issue_status_data in status_by_tutor[tutor_id]:
				issue_tutor = self._get_or_create_issue_tutor(tutor_id)
				issue_student = self._get_or_create_issue_student(issue_tutor, issue_status_data["student_id"])
				self._get_or_create_issue_status(issue_student, issue_status_data["attendance_status_id"], issue_status_data["send_to"])
				
				if not issue_tutor in notis: notis.append(issue_tutor)
		
		for n in notis:
			# noti internal structure: attendance_issue_tutor (1) --> (N) attendance_issue_student (1) --> (N) attendance_issue_status
			# notifications for the tutors: daily (at the end if its tourn); notifications for the family (status): after a timeout (default 15 minutes). 

			self._schedule_daily_assistance_notification(n, notification_tutor_eta)
			for student in n.attendance_issue_student_ids:
				for status in student.attendance_issue_status_ids:
					self._schedule_family_assistance_notification(status, notification_status_eta)

	def collect_issue_status_data(self, status_id, status_by_tutor):
		separator = "; "
		if status_id.status_is_notificable():
			if status_id.student_id.tutor_id not in status_by_tutor:
				status_by_tutor[status_id.student_id.tutor_id] = []
			
			send_to = []
			if status_id.student_id.auth_share or not status_id.student_id.is_adult:
				for contact in status_id.student_id.child_ids:				
					send_to.append(contact.email)

			# NOTE: The 'send_to' field will be empty if adult or family shared not authorized.
			#		All entries must be notified to the tutor, always. This trick simplifies a bit the logic.
			status_by_tutor[status_id.student_id.tutor_id].append({
				'attendance_status_id': status_id.id,
				'student_id': status_id.student_id.id,
				'send_to': separator.join(send_to)
			})	
	
	def get_issue_tutor(self, tutor_id):
		repo = self.sudo().env['ems.attendance_issue_tutor']
		issue_tutor = repo.search([('issue_date', '=', self.date), ('tutor_id', '=', tutor_id.id)]) or False		
		return {"repo": repo, "values": issue_tutor}
	
	def get_issue_student(self, issue_tutor, student_id):
		repo = self.sudo().env['ems.attendance_issue_student']
		issue_student = repo.search([('attendance_issue_tutor_id', '=', issue_tutor.id), ('student_id', '=', student_id)]) or False
		return {"repo": repo, "values": issue_student}
	
	def get_issue_status(self, attendance_status_id):
		# NOTE: On rectification, multiple issue_status can be attanched to the same attendance_status, but we always
		#		whant the most recent. 
		repo = self.sudo().env['ems.attendance_issue_status']
		issue_status = repo.search([('attendance_status_id', '=', attendance_status_id)], order='id desc', limit=1) or False
		return {"repo": repo, "values": issue_status}	
	