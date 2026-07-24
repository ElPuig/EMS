# -*- coding: utf-8 -*-

from odoo import models, fields, api

overall_status = [("assistance", "Assistance"), ("absence", "Absence")]

# Reports:
#	1. Attendance by group (for tutors and above, teachers can calso use it, but only its teaching subject/students will be displayed)
#	2. Attendance by student (for tutors and above, teachers can calso use it, but only its teaching subject/students will be displayed)
#	3. Attendance by subject (for the teachers teaching that subject and above)

class EmsAttendanceReportGroupWizard(models.TransientModel):
	_name = "ems.attendance_report_group_wizard"
	_description = "Attendance report wizard: by group."

	group_id = fields.Many2one(string='Group', comodel_name='ems.group')
	tutor_id = fields.Many2one(string='Tutor', related="group_id.tutor_id")
	allowed_group_ids = fields.Many2many('ems.group', compute='_compute_allowed_group_ids', store=False)
	from_date = fields.Date(string="From", default=fields.Datetime.now, required=True)
	to_date = fields.Date(string="To", default=fields.Datetime.now, required=True)

	@api.model
	def default_get(self, fields_list):
		res = super().default_get(fields_list)
		if 'allowed_group_ids' in fields_list:
			res['allowed_group_ids'] = [(6, 0, self._get_allowed_group_ids().ids)]
		return res

	def _get_allowed_group_ids(self):
		# TODO: use this to set the permissions (uid = 1 means ADMIN)
		current_teacher = self.env["hr.employee"].search([("user_id", "=", self.env.uid)])
		domain = [('teacher_id', '=', current_teacher.id)] if current_teacher.id > 1 else []
		return self.env["ems.teaching"].search(domain).mapped('group_id')

	@api.depends_context('uid')
	def _compute_allowed_group_ids(self):
		groups = self._get_allowed_group_ids()
		for wizard in self:
			wizard.allowed_group_ids = groups

	@api.onchange("group_id")
	def _onchange_group_id(self):
		for wizard in self:
			if wizard.group_id.id != False:
				sessions = self.env["ems.attendance_session_header"].search([("group_ids", "in", [wizard.group_id.id])])
				first = sessions.search([], order="date asc", limit=1)
				last = sessions.search([], order="date desc", limit=1)
				wizard.from_date = first.date
				wizard.to_date = last.date

	def print(self):
		session_ids = self.env["ems.attendance_session_header"].search([
			("group_ids", "in", [self.group_id.id]),
			("date", ">=", self.from_date),
			("date", "<=", self.to_date),
		]).ids

		status_ids = self.env["ems.attendance_session_line"].search([("attendance_session_id", "in", session_ids)]).ids

		data = {'doc_ids': [self.read()[0]['id']], 'status_ids': status_ids}
		return self.env.ref('ems.action_attendance_report_group').with_context(landscape=True).report_action(None, data=data)

class EmsAttendanceReportStudentWizard(models.TransientModel):
	_name = "ems.attendance_report_student_wizard"
	_description = "Attendance report wizard: by student."

	student_id = fields.Many2one(string="Student", comodel_name="res.partner", domain="[('contact_type', '=', 'student')]", required=True)
	tutor_id = fields.Many2one(string='Tutor', related="student_id.tutor_id")
	allowed_student_ids = fields.Many2many('res.partner', compute='_compute_allowed_student_ids', store=False)
	from_date = fields.Date(string="From", default=fields.Datetime.now, required=True)
	to_date = fields.Date(string="To", default=fields.Datetime.now, required=True)

	@api.model
	def default_get(self, fields_list):
		res = super().default_get(fields_list)
		if 'allowed_student_ids' in fields_list:
			res['allowed_student_ids'] = [(6, 0, self._get_allowed_student_ids().ids)]
		return res

	def _get_allowed_student_ids(self):
		# TODO: use this to set the permissions (uid = 1 means ADMIN)
		current_teacher = self.env["hr.employee"].search([("user_id", "=", self.env.uid)])
		if current_teacher.id <= 1:
			return self.env["ems.enrollment"].search([]).mapped('student_id')

		# Crossing student's enrollment data with teacher's teaching data: a student is
		# allowed if enrolled in a (group, subject) pair the current teacher actually teaches.
		teachings = self.env["ems.teaching"].search([('teacher_id', '=', current_teacher.id)])
		taught_pairs = {(teaching.group_id.id, teaching.subject_id.id) for teaching in teachings}
		enrollments = self.env["ems.enrollment"].search([('group_id', 'in', teachings.mapped('group_id').ids)])
		enrollments = enrollments.filtered(lambda enrollment: (enrollment.group_id.id, enrollment.subject_id.id) in taught_pairs)
		return enrollments.mapped('student_id')

	@api.depends_context('uid')
	def _compute_allowed_student_ids(self):
		students = self._get_allowed_student_ids()
		for wizard in self:
			wizard.allowed_student_ids = students

	@api.onchange("student_id")
	def _onchange_student_id(self):
		for wizard in self:
			if wizard.student_id.id != False:
				sessions = self.env["ems.attendance_session_line"].search([("student_id", "=", wizard.student_id.id)]).mapped('attendance_session_id')
				first = sessions.search([], order="date asc", limit=1)
				last = sessions.search([], order="date desc", limit=1)
				wizard.from_date = first.date
				wizard.to_date = last.date

	def print(self):
		status_ids = self.env["ems.attendance_session_line"].search([
			('student_id', '=', self.student_id.id),
			('attendance_session_id.date', '>=', self.from_date),
			('attendance_session_id.date', '<=', self.to_date),
		]).ids

		data = {'doc_ids': [self.read()[0]['id']], 'status_ids': status_ids}
		return self.env.ref('ems.action_attendance_report_student').with_context(landscape=True).report_action(None, data=data)

class EmsAttendanceReportSubjectWizard(models.TransientModel):
	_name = "ems.attendance_report_subject_wizard"
	_description = "Attendance report wizard: by subject."

	level_id = fields.Many2one(string='Level', comodel_name='ems.level')
	study_id = fields.Many2one(string='Studies', comodel_name='ems.study')
	group_id = fields.Many2one(string='Group', comodel_name='ems.group')
	tutor_id = fields.Many2one(string='Tutor', related="group_id.tutor_id")
	subject_id = fields.Many2one(string="Subject", comodel_name="ems.subject", required=True)
	allowed_subject_ids = fields.Many2many('ems.subject', compute='_compute_allowed_subject_ids', store=False)

	from_date = fields.Date(string="From", default=fields.Datetime.now, required=True)
	to_date = fields.Date(string="To", default=fields.Datetime.now, required=True)

	@api.depends('group_id')
	def _compute_allowed_subject_ids(self):
		# TODO: use this to set the permissions (uid = 1 means ADMIN)
		current_teacher = self.env["hr.employee"].search([("user_id", "=", self.env.uid)])

		for wizard in self:
			if wizard.group_id.id == False:
				wizard.allowed_subject_ids = []
			else:
				domain = [('group_id', '=', wizard.group_id.id)]
				if current_teacher.id > 1: domain.append(('teacher_id', '=', current_teacher.id))
				wizard.allowed_subject_ids = self.env["ems.teaching"].search(domain).mapped('subject_id')

	@api.onchange('level_id')
	def _onchange_level_id(self):
		for wizard in self:
			wizard.study_id = False

	@api.onchange('study_id')
	def _onchange_study_id(self):
		for wizard in self:
			wizard.group_id = False

	@api.onchange("subject_id")
	def _onchange_subject_id(self):
		for wizard in self:
			if wizard.subject_id.id != False:
				sessions = self.env["ems.attendance_session_header"].search([("subject_id", "=", wizard.subject_id.id), ("group_ids", "in", [wizard.group_id.id])])
				first = sessions.search([], order="date asc", limit=1)
				last = sessions.search([], order="date desc", limit=1)
				wizard.from_date = first.date
				wizard.to_date = last.date

	def print(self):
		session_ids = self.env["ems.attendance_session_header"].search([
			("group_ids", "in", [self.group_id.id]),
			("subject_id", "=", self.subject_id.id),
			("date", ">=", self.from_date),
			("date", "<=", self.to_date),
		]).ids

		status_ids = self.env["ems.attendance_session_line"].search([("attendance_session_id", "in", session_ids)]).ids

		data = {'doc_ids': [self.read()[0]['id']], 'status_ids': status_ids}
		return self.env.ref('ems.action_attendance_report_subject').with_context(landscape=True).report_action(None, data=data)

class EmsAttendanceReportStudent(models.AbstractModel):
	_name = 'report.ems.attendance_report_student'
	_description = "Attendance report data: by student."

	def _get_report_values(self, docids, data=None):
		if not docids: docids = data['doc_ids'] # TODO: is there any way to got this from docids param? Always null even when setting up at report_action
		entries = list(self.env["ems.attendance_session_line"].browse(data['status_ids']))
		main = _report_data(entries, self.env)

		grp_by_subject = {}
		for entry in entries:
			key = entry.attendance_session_id.subject_id
			if not key in grp_by_subject: grp_by_subject[key] = []
			values = grp_by_subject[key]
			values.append(entry)

		lines = {}
		for subject in grp_by_subject:
			lines[subject] = _report_data(grp_by_subject[subject], self.env)

		return {
			'doc_ids': docids,
			'doc_model': 'ems.attendance_report_student_wizard',
			'docs': self.env["ems.attendance_report_student_wizard"].browse(data['doc_ids']),
			'main': main,
			'lines': lines,
			'attendance_session_line': {status.id: status.name for status in self.env['ems.attendance_status'].with_context(active_test=False).search([])},
			'overall_status': dict(overall_status)
		}

class EmsAttendanceReportSubject(models.AbstractModel):
	_name = 'report.ems.attendance_report_subject'
	_description = "Attendance report data: by subject."

	def _get_report_values(self, docids, data=None):
		if not docids: docids = data['doc_ids'] # TODO: is there any way to got this from docids param? Always null even when setting up at report_action
		entries = list(self.env["ems.attendance_session_line"].browse(data['status_ids']))
		main = _report_data(entries, self.env)

		grp_by_student = {}
		for entry in entries:
			key = entry.student_id
			if not key in grp_by_student: grp_by_student[key] = []
			values = grp_by_student[key]
			values.append(entry)

		lines = {}
		for student in grp_by_student:
			lines[student] = _report_data(grp_by_student[student], self.env)

		return {
			'doc_ids': docids,
			'doc_model': 'ems.attendance_report_subject_wizard',
			'docs': self.env["ems.attendance_report_subject_wizard"].browse(data['doc_ids']),
			'main': main,
			'lines': lines,
			'attendance_session_line': {status.id: status.name for status in self.env['ems.attendance_status'].with_context(active_test=False).search([])},
			'overall_status': dict(overall_status)
		}

class EmsAttendanceReportGroup(models.AbstractModel):
	_name = 'report.ems.attendance_report_group'
	_description = "Attendance report data: by group."

	def _get_report_values(self, docids, data=None):
		if not docids: docids = data['doc_ids'] # TODO: is there any way to got this from docids param? Always null even when setting up at report_action
		entries = list(self.env["ems.attendance_session_line"].browse(data['status_ids']))
		main = _report_data(entries, self.env)

		grp_by_subject = {}
		for entry in entries:
			key = entry.attendance_session_id.subject_id
			if not key in grp_by_subject: grp_by_subject[key] = []
			values = grp_by_subject[key]
			values.append(entry)

		lines = {}
		for subject in grp_by_subject:
			lines[subject] = _report_data(grp_by_subject[subject], self.env)

		return {
			'doc_ids': docids,
			'doc_model': 'ems.attendance_report_group_wizard',
			'docs': self.env["ems.attendance_report_group_wizard"].browse(data['doc_ids']),
			'main': main,
			'lines': lines,
			'attendance_session_line': {status.id: status.name for status in self.env['ems.attendance_status'].with_context(active_test=False).search([])},
			'overall_status': dict(overall_status)
		}

class _report_data:
	def __init__(self, entries, env):
		self.entries = entries
		self.comments = []
		self.breakdown = {}
		statuses = env['ems.attendance_status'].with_context(active_test=False).search([])

		assistance = 	self._get_status('assistance')[0]
		absence = 	self._get_status('absence')[0]
		self.overall = {
			assistance : self._setup_counters(0, len(entries)),
			absence : self._setup_counters(0, len(entries))
		}

		for status in statuses:
			self.breakdown[status.id] = self._setup_counters(0, len(entries))

		for entry in entries:
			self.breakdown[entry.status_id.id]['count'] += 1
			if entry.notes != False: self.comments.append(entry)
			if entry.status_id.category == 'assistance': self.overall[assistance]['count'] += 1
			else: self.overall[absence]['count'] += 1

		for status in statuses:
			self._compute_counters(self.breakdown[status.id])

		self._compute_counters(self.overall[assistance])
		self._compute_counters(self.overall[absence])


	def _get_status(self, name):
		return list(filter(lambda x: x[0] == name, overall_status))[0]

	def _setup_counters(self, count, total):
		overall = {
			'count' : count,
			'total' : total,
			'%'		: 0
		}
		self._compute_counters(overall)
		return overall

	def _compute_counters(self, overall):
		if overall['total'] > 0: overall['%'] = round((overall['count'] / overall['total']) * 100, 2)
