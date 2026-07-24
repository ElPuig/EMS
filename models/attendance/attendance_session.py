# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from .attendance_schedule import ems_attendance_schedule
from .attendance_justification import ems_attendance_justification
from datetime import datetime, timedelta
from odoo.exceptions import ValidationError, UserError, AccessError
from psycopg2 import IntegrityError

class ems_attendance_session_header(models.Model):
	_name = "ems.attendance_session_header"
	_description = "Attendance session header: contains the main data about an attendance session."
	_inherit = ['ems.base', 'ems.datetime_utils', 'mail.thread', 'mail.activity.mixin']		
	_sql_constraints = [
		(
			'attendance_session_is_duped',
			'UNIQUE(date, attendance_schedule_id)',
			'Duped session (same schedule and date).' # Translated message within the method 'create'.
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
	group_ids = fields.Many2many(string="Groups", comodel_name="ems.group", compute="_compute_group_ids", store=True)
	subject_id = fields.Many2one(string="Subject", comodel_name="ems.subject", compute="_compute_subject_id", store=True)
	space_id = fields.Many2one(string="Space", comodel_name="ems.space", compute="_compute_space_id", store=True)
	template_teacher_ids = fields.Many2many(string="Template's teachers", comodel_name="hr.employee", compute="_compute_template_teacher_ids", store=True)
	session_teacher_id = fields.Many2one(string="Session's teacher", comodel_name="hr.employee", domain="[('employee_type', '=', 'teacher')]", required=True, default=lambda self: self._default_teacher_id(), store=True)	
	mode = fields.Selection(string="Mode", selection=[('scheduled', 'Scheduled'), ('guard', 'Guard'), ('manual', 'Manual')], default="scheduled", required=True)
	
	attendance_session_line_ids = fields.One2many(string="Statuses", comodel_name="ems.attendance_session_line", inverse_name="attendance_session_id")			
	attendance_schedule_id = fields.Many2one(string="Session", comodel_name="ems.attendance_schedule", required=True)

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
	
	@api.depends("attendance_schedule_id")
	def _compute_level_id(self):
		for rec in self:
			rec.level_id = rec.attendance_schedule_id.attendance_template_id.sudo().level_id

	@api.depends("attendance_schedule_id")
	def _compute_study_id(self):
		for rec in self:
			rec.study_id = rec.attendance_schedule_id.attendance_template_id.sudo().study_id

	@api.depends("attendance_schedule_id")
	def _compute_group_ids(self):
		for rec in self:
			rec.group_ids = rec.attendance_schedule_id.attendance_template_id.sudo().group_ids

	@api.depends("attendance_schedule_id")
	def _compute_subject_id(self):
		for rec in self:
			rec.subject_id = rec.attendance_schedule_id.attendance_template_id.sudo().subject_id

	@api.depends("attendance_schedule_id")
	def _compute_space_id(self):
		for rec in self:
			rec.space_id = rec.attendance_schedule_id.attendance_template_id.sudo().space_id

	@api.depends("attendance_schedule_id")
	def _compute_template_teacher_ids(self):
		for rec in self:
			rec.template_teacher_ids = rec.attendance_schedule_id.attendance_template_id.sudo().teacher_ids
	
	@api.depends('attendance_schedule_id', 'date')
	def _compute_display_name(self):              
		for rec in self:
			rec.display_name = "%s | %s | %s" % (rec.attendance_schedule_id.display_name, rec.date, rec.space_id.name)

	def _default_teacher_id(self):
		return self.env["hr.employee"].search([("user_id", "=", self.env.uid), ("employee_type", "=", "teacher")]) or False


	def _get_notification_tutor_eta(self, tutor=None):
		if tutor and tutor.resource_calendar_id and tutor.resource_calendar_id.id != 1:
			today = fields.Datetime.now()
			weekday = str(today.weekday())
			slots = tutor.resource_calendar_id.attendance_ids.filtered(
				lambda a: a.dayofweek == weekday
			).sorted(key=lambda a: a.hour_to, reverse=True)
			if slots:
				return self.datetime_to_odoo(self.time_float_to_utc_datetime(today, slots[0].hour_to))

		notification_tutor_eta = self.time_float_to_utc_datetime(fields.Datetime.now(), self.env.company.attendance_issue_tutor_default)
		return self.datetime_to_odoo(notification_tutor_eta)
	
	def _get_notification_status_eta(self):
		return fields.Datetime.now() + timedelta(seconds=self.env.company.attendance_issue_status_delay * 60) # from minutes to seconds
	
	def _get_or_create_issue_status(self, issue_student, attendance_session_line, send_to, rectification):
		data = self.get_issue_status(attendance_session_line)
		repo = data["repo"]
		issue_status = data["values"]	
		
		if not issue_status or rectification:
			as_id = self.sudo().env['ems.attendance_session_line'].sudo().search([('id', '=', attendance_session_line)])
			issue_status = repo.create({				
				'attendance_issue_student_id': issue_student.id,
				'attendance_session_line_id': attendance_session_line,
				'attendance_status_id': as_id.status_id.id,
				'rectification': rectification,
				'notes': as_id.notes,
				'send_to': send_to,				
			})

			if rectification:
				must_rectify = self.sudo().env['ems.attendance_issue_status'].sudo().search([('attendance_session_line_id', '=', attendance_session_line), ('rectified_by', '=', False), ('id', '!=', issue_status.id)])
				for rect in must_rectify:				
					rect.write({'rectified_by' : issue_status.id})

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
	
	def _get_or_create_issue_tutor(self, tutor_id, date):
		data = self.get_issue_tutor(tutor_id)		
		repo = data["repo"]
		issue_tutor = data["values"]		
		
		if not issue_tutor:
			issue_tutor = repo.create({
				'tutor_id': tutor_id.id,
				'issue_date': date
			})
		return issue_tutor
	
	def _schedule_daily_assistance_notification(self, issue_tutor, eta):		
		if issue_tutor.notification_id.id != False: return

		daily = issue_tutor.with_delay(
			eta = eta,
			description=f"Tutor's assistance report: ID={issue_tutor.id}"
		).send_notification()

		job = self.sudo().env['queue.job'].search([('uuid', '=', daily.uuid)]) or False
		if job: issue_tutor.sudo().write({'notification_id': job.id})

	def _schedule_family_assistance_notification(self, issue_status, eta, rectification):		
		if issue_status.notification_id.id != False or not issue_status.send_to or issue_status.send_to == "": return				

		noti = issue_status.with_delay(
			eta = eta,
			description="Family assistance notification %s: ID=%s" % ("" if not rectification else " (rectification)", issue_status.id)
		).send_notification()

		job = self.sudo().env['queue.job'].search([('uuid', '=', noti.uuid)]) or False
		if job: issue_status.sudo().write({
			'notification_id': job.id
		})
	
	def _setup_new_line_data(self, student_id, status_id=None, notes=None):
		return  {
			"student_id": student_id,
			"status_id": status_id or self.env.ref("ems.attendance_status_attended").id,
			"notes": notes,
			"is_auto_generated" : True
		}

	def _setup_next_session_line_data(self, previous):
		justified = self.env.ref("ems.attendance_status_justified")
		delayed = self.env.ref("ems.attendance_status_delayed")
		attended = self.env.ref("ems.attendance_status_attended")
		miss = self.env.ref("ems.attendance_status_miss")
		if previous.status_id == justified:
			return {
				"student_id": previous.student_id,
				"status_id": miss.id,
				"notes": None,
				"is_auto_generated": True,
			}
		return {
			"student_id": previous.student_id,
			"status_id": attended.id if previous.status_id == delayed else previous.status_id.id,
			"notes": previous.notes,
			"is_auto_generated": True,
		}

	def _auto_checkin_teacher(self, teacher, date, schedule=None):
		"""Auto check-in the teacher if they haven't checked in yet today."""
		mode = self.env.company.auto_checkin_mode
		if not mode or mode == 'disabled':
			return
		today = datetime.today().date()
		if not teacher or date != today:
			return

		day_start = datetime(date.year, date.month, date.day, 0, 0, 0)
		day_end   = datetime(date.year, date.month, date.day, 23, 59, 59)

		existing = self.env['hr.attendance'].sudo().search([
			('employee_id', '=', teacher.id),
			('check_in', '>=', day_start),
			('check_in', '<=', day_end),
		], limit=1)

		if existing:
			return

		if mode == 'first':
			# First working hour from the teacher's resource calendar
			if not teacher.resource_calendar_id:
				return
			weekday = str(date.weekday())
			calendar_attendances = teacher.resource_calendar_id.attendance_ids.filtered(
				lambda a: a.dayofweek == weekday
			).sorted(key=lambda a: a.hour_from)
			if not calendar_attendances:
				return
			first_hour = calendar_attendances[0].hour_from
			check_in_utc = self.time_float_to_utc_datetime(date, first_hour)
			check_in_naive = self.datetime_to_odoo(check_in_utc)

		elif mode == 'start':
			# Start time of the attendance schedule used in the current session
			if not schedule or not schedule.start_time:
				return
			check_in_utc = self.time_float_to_utc_datetime(date, schedule.start_time)
			check_in_naive = self.datetime_to_odoo(check_in_utc)

		elif mode == 'current':
			# Current clock time
			check_in_naive = self.datetime_to_odoo(
				self.local_datetime_to_utc(self.get_local_datetime())
			)

		else:
			return

		self.env['hr.attendance'].sudo().create({
			'employee_id': teacher.id,
			'check_in': check_in_naive,
			'in_mode': 'auto_check_in',
		})

	def _auto_populate_lines(self):
		"""Populate session lines when created via ORM (onchange doesn't fire outside form view)."""
		template = self.attendance_schedule_id.attendance_template_id.sudo()
		lines = []

		previous = self.env["ems.attendance_session_header"].search([
			("date", "=", self.date),
			("attendance_schedule_id.attendance_template_id", "=", template.id),
			("attendance_schedule_id.weekday", "=", self.attendance_schedule_id.weekday),
			("id", "!=", self.id),
		], order="end_time DESC", limit=1)

		previssions = ems_attendance_justification.get_current_justifications(self, self.start_date, self.end_date)

		if previous and previous.end_time <= self.start_time:
			for prev in previous.attendance_session_line_ids:
				line = None
				for p in previssions:
					if p.student_id == prev.student_id:
						line = p.perform_justification(self._setup_new_line_data(prev.student_id), True)
				if line is None:
					line = self._setup_next_session_line_data(prev)
				lines.append(line)
		else:
			for student in template.student_ids:
				line = None
				for p in previssions:
					if p.student_id == student:
						line = p.perform_justification(self._setup_new_line_data(student), True)
				if line is None:
					line = self._setup_new_line_data(student)
				lines.append(line)

		if lines:
			def _to_id(v):
				return v.id if hasattr(v, '_name') else v
			self.env['ems.attendance_session_line'].create([
				{k: _to_id(v) for k, v in line.items()} | {'attendance_session_id': self.id}
				for line in lines
			])

	@api.model_create_multi
	def create(self, vals_list):
		try:
			records = super().create(vals_list)
		except IntegrityError as e:
			raise e if "attendance_session_is_duped" not in str(e) else ValidationError(_('The current session already exists. Please, edit the existing one (maybe has been created by another teacher) or choose another available session.'))

		# NOTE: Optional, but computed here for optimization
		notification_status_eta = self._get_notification_status_eta()

		for record in records:
			if not record.attendance_session_line_ids:
				record._auto_populate_lines()

			record._auto_checkin_teacher(record.session_teacher_id, record.date, record.attendance_schedule_id)

			# NOTE: Collecting all status data first allow some optimizations.
			issue_status_by_tutor = dict()
			for attendance_session_line in record.attendance_session_line_ids:
				record.collect_issue_status_data(attendance_session_line, issue_status_by_tutor)

			record.create_notification_entries(issue_status_by_tutor, notification_status_eta=notification_status_eta)
		return records
	
	def copy(self, default=None):
		raise UserError(_("Attendance sessions cannot be duplicated."))

	def unlink(self):
		# NOTE: removing the session removes also the statuses and the related notification entries
		# TODO: should be blocked if the notifications have been sent? I guess so, but the admins should be ablte to delete those
		#		after confirming a popup. 
		date = self.date
		res = super().unlink()
		
		for issue_tutor in self.env['ems.attendance_issue_tutor'].sudo().search([('issue_date', '=', date)]):
			issue_tutor.remove_if_empty()

		return res
	
	def create_notification_entries(self, issue_status_by_tutor, notification_status_eta=None, rectification=False):
		if notification_status_eta is None: notification_status_eta = self._get_notification_status_eta()

		# NOTE: Status data is grouped by tutor and only got the ones which should be notified.
		notis = []
		for tutor_id in issue_status_by_tutor:
			for issue_status_data in issue_status_by_tutor[tutor_id]:
				issue_tutor = self._get_or_create_issue_tutor(tutor_id, self.date)
				issue_student = self._get_or_create_issue_student(issue_tutor, issue_status_data["student_id"])
				self._get_or_create_issue_status(issue_student, issue_status_data["attendance_session_line_id"], issue_status_data["send_to"], rectification)

				if not issue_tutor in notis: notis.append(issue_tutor)

		for notification_tutor in notis:
			# noti internal structure: attendance_issue_tutor (1) --> (N) attendance_issue_student (1) --> (N) attendance_issue_status
			# notifications for the tutors: daily (at the end if its tourn); notifications for the family (status): after a timeout (default 15 minutes).

			self._schedule_daily_assistance_notification(notification_tutor, self._get_notification_tutor_eta(notification_tutor.tutor_id))
			for issue_student in notification_tutor.attendance_issue_student_ids:
				for issue_status in issue_student.attendance_issue_status_ids:
					self._schedule_family_assistance_notification(issue_status, notification_status_eta, rectification)

	def collect_issue_status_data(self, attendance_session_line_id, status_by_tutor, rectification=False):
		separator = "; "
		student_id = attendance_session_line_id.student_id

		if rectification or attendance_session_line_id.status_is_notificable():
			if student_id.tutor_id not in status_by_tutor:
				status_by_tutor[student_id.tutor_id] = []
			
			send_to = [student_id.student_email]
			if student_id.auth_share or not student_id.is_adult:
				for relation in student_id.relation_all_ids:
					if relation.other_partner_id.contact_type == 'family' and relation.other_partner_id.email:
						send_to.append(relation.other_partner_id.email)

			# NOTE: The 'send_to' field will be empty if adult or family shared not authorized.
			#		All entries must be notified to the tutor, always. This trick simplifies a bit the logic.
			status_by_tutor[student_id.tutor_id].append({
				'attendance_session_line_id': attendance_session_line_id.id,
				'student_id': student_id.id,
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
	
	def get_issue_status(self, attendance_session_line):
		# NOTE: On rectification, multiple issue_status can be attanched to the same attendance_session_line, but we always
		#		whant the most recent.
		repo = self.sudo().env['ems.attendance_issue_status']
		issue_status = repo.search([('attendance_session_line_id', '=', attendance_session_line)], order='id desc', limit=1) or False
		return {"repo": repo, "values": issue_status}

	# ── Guard mode (pass-list OWL component) ─────────────────────────────────

	@api.model
	def get_guard_sessions(self, date):
		# Guard teachers need to see all sessions for the day regardless of ownership,
		# except their own (already shown in normal mode).
		# sudo() is required here — see security/rules/attendance.xml and the same
		# pattern used in _get_allowed_attendance_schedule_ids().
		if not (self.env.user.has_group('ems.group_teacher') or
				self.env.user.has_group('ems.group_academic_admin')):
			raise AccessError(_("Guard mode requires teacher access."))
		own_emp = self.env['hr.employee'].search([['user_id', '=', self.env.uid]], limit=1)
		domain = [['date', '=', date]]
		if own_emp:
			domain += ['!', '|',
				['template_teacher_ids', 'in', own_emp.id],
				['session_teacher_id', '=', own_emp.id]]
		return self.sudo().search_read(
			domain,
			fields=['id', 'time_range', 'subject_id', 'study_id',
					'attendance_schedule_id', 'start_time', 'end_time',
					'attendance_session_line_ids'],
			order='start_time asc',
		)

	@api.model
	def get_guard_planned(self, date):
		# Guard mode: return planned schedules (no session yet today) for other teachers.
		# Own schedules are already shown in normal mode, so exclude them here.
		# sudo() required — see get_guard_sessions().
		if not (self.env.user.has_group('ems.group_teacher') or
				self.env.user.has_group('ems.group_academic_admin')):
			raise AccessError(_("Guard mode requires teacher access."))
		own_emp = self.env['hr.employee'].search([['user_id', '=', self.env.uid]], limit=1)
		weekday = str(datetime.strptime(date, '%Y-%m-%d').weekday())
		used_ids = set(
			self.sudo().search([['date', '=', date], ['attendance_schedule_id', '!=', False]])
			.mapped('attendance_schedule_id.id')
		)
		domain = [['weekday', '=', weekday], ['id', 'not in', list(used_ids)],
				  ['start_date', '<=', date], ['end_date', '>=', date]]
		if own_emp:
			domain.append(['attendance_template_id.teacher_ids', 'not in', own_emp.id])
		return self.env['ems.attendance_schedule'].sudo().search_read(
			domain,
			fields=['id', 'name', 'time_range', 'attendance_template_id', 'start_time', 'end_time'],
			order='start_time asc',
		)

	@api.model
	def get_normal_sessions_and_planned(self, date):
		is_admin = self.env.user.has_group('ems.group_academic_admin')
		own_emp  = self.env['hr.employee'].search([['user_id', '=', self.env.uid]], limit=1)

		session_domain = [['date', '=', date]]
		if is_admin and own_emp:
			session_domain += ['|',
				['template_teacher_ids', 'in', own_emp.id],
				['session_teacher_id',  '=', own_emp.id]]
		sessions = self.search_read(
			session_domain,
			fields=['id', 'time_range', 'subject_id', 'study_id', 'attendance_schedule_id',
					'attendance_session_line_ids', 'start_time', 'end_time'],
			order='start_time asc',
		)

		weekday  = str(datetime.strptime(date, '%Y-%m-%d').weekday())
		used_ids = [s['attendance_schedule_id'][0] for s in sessions if s['attendance_schedule_id']]
		sched_domain = [
			['weekday',    '=',  weekday],
			['start_date', '<=', date],
			['end_date',   '>=', date],
			['id', 'not in', used_ids],
		]
		if is_admin and own_emp:
			sched_domain.append(['attendance_template_id.teacher_ids', 'in', own_emp.id])
		planned = self.env['ems.attendance_schedule'].search_read(
			sched_domain,
			fields=['id', 'name', 'time_range', 'attendance_template_id', 'start_time', 'end_time'],
			order='start_time asc',
		)
		return {'sessions': sessions, 'planned': planned}

	@api.model
	def create_scheduled_session(self, date, schedule_id):
		record   = self.create({'date': date, 'attendance_schedule_id': schedule_id, 'mode': 'scheduled'})
		template = record.attendance_schedule_id.attendance_template_id
		previous = self.search([
			('date', '=', date),
			('attendance_schedule_id.attendance_template_id', '=', template.id),
			('attendance_schedule_id.weekday', '=', record.attendance_schedule_id.weekday),
			('id', '!=', record.id),
		], order='end_time DESC', limit=1)
		return {
			'id': record.id,
			'is_continuation': bool(previous and previous.end_time <= record.start_time),
		}

	@api.model
	def write_guard_session_line(self, line_id, values):
		# Guard teachers need write access to lines in sessions they don't own.
		# sudo() is required — same justification as get_guard_sessions().
		if not (self.env.user.has_group('ems.group_teacher') or
				self.env.user.has_group('ems.group_academic_admin')):
			raise AccessError(_("Guard mode requires teacher access."))
		self.env['ems.attendance_session_line'].sudo().browse(line_id).write(values)
		return True

# NOTE: moved here because the status is strongly related to the session, it has no own list or form (as happens with the
#		attendance issues).
class ems_attendance_session_line(models.Model):	
	_name = "ems.attendance_session_line"
	_description = "Attendance status line: information about a status per student within an attendance session."
	
	status_id = fields.Many2one(
		string="Status", comodel_name="ems.attendance_status", required=True,
		default=lambda self: self.env.ref("ems.attendance_status_attended", raise_if_not_found=False),
	)
	student_id = fields.Many2one(string="Student", comodel_name="res.partner", domain="[('contact_type', '=', 'student')]")
	image_1920 = fields.Binary(string="Image", related='student_id.image_1920')
	attendance_session_id = fields.Many2one(string="Session", comodel_name="ems.attendance_session_header", ondelete="cascade")
	attendance_justification_id = fields.Many2one(string="Justification", comodel_name="ems.attendance_justification")
	attendance_prevision_id = fields.Many2one(string="Prevision", comodel_name="ems.attendance_justification")

	# This field is used to filter the availabe students within the view (avoiding the selection of repeated students on attendance session form).
	inuse_student_ids = fields.Many2many('res.partner', compute='_compute_inuse_student_ids', store=False) 

	# The teacher_ids/session_teacher_id are used just for permission filtering pruposes.
	template_teacher_ids = fields.Many2many(string="Template's teachers", related="attendance_session_id.template_teacher_ids", store=False)
	session_teacher_id = fields.Many2one(string="Session's teacher", related="attendance_session_id.session_teacher_id", store=False)

	# Stored so the 'Attendance analysis' pivot/graph view can group by them efficiently.
	date = fields.Date(string="Date", related="attendance_session_id.date", store=True)
	level_id = fields.Many2one(string="Level", comodel_name="ems.level", related="attendance_session_id.level_id", store=True)
	study_id = fields.Many2one(string="Study", comodel_name="ems.study", related="attendance_session_id.study_id", store=True)
	group_ids = fields.Many2many(
		string="Groups", comodel_name="ems.group", related="attendance_session_id.group_ids", store=True,
		relation="ems_attendance_session_line_group_rel", column1="attendance_session_line_id", column2="group_id",
	)
	subject_id = fields.Many2one(string="Subject", comodel_name="ems.subject", related="attendance_session_id.subject_id", store=True)

	# 0/100 rather than a boolean so the 'Attendance reports' graph's default measure (avg,
	# grouped by subject) resolves directly to a percentage of absence.
	absence_rate = fields.Float(string="Absence rate", compute="_compute_absence_rate", store=True, aggregator="avg")

	# Used to know if the student can be chosen manually or not (should be disabled, otherwise a justified student can be swaped for another).
	is_auto_generated = fields.Boolean(default=False)
	notes = fields.Text("Notes")
	strike_ids = fields.One2many(string="Strikes", comodel_name="ems.strike", inverse_name="attendance_session_line_id")
	strike_count = fields.Integer(string="Strike count", compute="_compute_strike_count")

	def status_is_notificable(self):
		# TODO: we want to notify also a justified miss? Maybe to prevent falsification (inform about a preveision? But if legit, will be also notified...)
		return bool(self.status_id.notifiable)
	
	@api.model_create_multi
	def create(self, vals_list):
		records = super().create(vals_list)		

		for r in records:		
			if r.attendance_prevision_id.id != False:
				r.attendance_prevision_id.attendance_session_line_ids = [(4, r.id)]
				# r.attendance_prevision_id.write({
				# 	"attendance_session_line_ids" : [(4, r.id)],
				# 	"session_teacher_ids" : [(4, r.attendance_session_id.session_teacher_id.id)]
				# })
			
		return records

	def write(self, vals):
		super(ems_attendance_session_line, self).write(vals)
		self._update_notification()   
	
	def report_eval(self, field):
		# NOTE: this is used within the 'details_table' template in order to render custom fields.		
		return eval(field)	
	
	# Allow justification (absence prevission) on manually added entries.
	@api.onchange("student_id")
	def _onchange_student_id(self):	
		for rec in self:			
			if not rec.is_auto_generated:
				data = rec.attendance_session_id._setup_new_line_data(rec.student_id)
				data["is_auto_generated"] = False
				previssions = ems_attendance_justification.get_current_justifications(self, rec.attendance_session_id.start_date, rec.attendance_session_id.end_date)
				for p in previssions:
					if p.student_id == rec.student_id:
						data = p.perform_justification(rec, True)
				rec.write(data)						

	def _update_notification(self):
		session = self.attendance_session_id

		# NOTE: Original data must be compared with the current one in order to update properly.            
		previous_issue_status = False
		issue_tutor = (session.get_issue_tutor(self.student_id.tutor_id))["values"]
		if issue_tutor: 
			issue_student = session.get_issue_student(issue_tutor, self.student_id.id)
			if issue_student:
				previous_issue_status = (session.get_issue_status(self.id))["values"]

		# NOTE: Possible scenarios when updating an attendance status:
				#       1. From issue to non-issue:
				#           1.1. If not notified yet, just remove.
				#           1.2. If notified, a rectification should be send to the family.
				#       2. From issue to issue:
				#           2.1. If not notified yet, update the notification data.
				#           2.2. If notified, a rectification should be send to the family.
				#       3. From non-issue to issue:
				#           3.1. Add the notification with the regular timeout. 
				#       4. From non-issue to non-issue:
				#           4.1. Do nothing.
		create = 0
		if previous_issue_status:            
			if not previous_issue_status.pending:
				# 1.2 & 2.2. If notified, a rectification should be send to the family.                 
				create = 1
			else:
				if not self.status_is_notificable():
					# 1.1. If not notified yet, just remove.
					# NOTE: also removes the notification.                    
					issue_tutor = previous_issue_status.attendance_issue_student_id.attendance_issue_tutor_id
					previous_issue_status.unlink()
					issue_tutor.remove_if_empty()                  
				else:
					# 2.1. If not notified yet, update the notification data.
					previous_issue_status.write({
						"attendance_status_id": self.status_id.id,
						"notes": self.notes
					})
		elif self.status_is_notificable():
			# 3.1. Add the notification with the regular timeout. 
			# TODO: do not notify to the families after certain timeout (eg: is from a few days ago).
			create = 2
		
		if create != 0:
			status_by_tutor = dict()
			session.collect_issue_status_data(self, status_by_tutor, create == 1)
			session.create_notification_entries(status_by_tutor, rectification=(create == 1))

	@api.depends('attendance_session_id')
	def _compute_attendance_session_display_name(self):
		for rec in self:
			rec.attendance_session_display_name = rec.attendance_session_id.display_name

	@api.depends('attendance_session_id')
	def _compute_inuse_student_ids(self):
		for rec in self:
			rec.inuse_student_ids = False
			if rec.attendance_session_id:
				rec.inuse_student_ids = rec.mapped('attendance_session_id.attendance_session_line_ids.student_id')   

	@api.depends('attendance_session_id', 'student_id')
	def _compute_display_name(self):
		for rec in self:
			rec.display_name = "%s | %s" % (rec.attendance_session_id.display_name, rec.student_id.display_name)

	@api.depends('strike_ids')
	def _compute_strike_count(self):
		for rec in self:
			rec.strike_count = len(rec.strike_ids)

	@api.depends('status_id')
	def _compute_absence_rate(self):
		for rec in self:
			rec.absence_rate = 100.0 if rec.status_id.category == 'absence' else 0.0

	def action_view_strikes(self):
		self.ensure_one()
		action = self.env['ir.actions.act_window']._for_xml_id('ems.action_strike_list')
		action['domain'] = [('attendance_session_line_id', '=', self.id)]
		action['context'] = {}
		return action

	