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

		# Exclude student-less lines: when a student partner is hard-deleted, their session
		# lines survive with student_id = NULL (Odoo's default ondelete='set null'). Grouping
		# those by student would render a phantom blank-name row/group in the PDF.
		status_ids = self.env["ems.attendance_session_line"].search([
			("attendance_session_id", "in", session_ids), ("student_id", "!=", False),
		]).ids

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

	subject_id = fields.Many2one(string="Subject", comodel_name="ems.subject", required=True)
	allowed_subject_ids = fields.Many2many('ems.subject', compute='_compute_allowed_subject_ids', store=False)
	group_ids = fields.Many2many(string='Groups', comodel_name='ems.group')
	allowed_group_ids = fields.Many2many('ems.group', compute='_compute_allowed_group_ids', store=False)
	tutor_ids = fields.Many2many(string='Tutors', comodel_name='hr.employee', compute='_compute_tutor_ids')

	# Per-student "Details" section of the PDF (see print()): defaults to absence-category
	# statuses only, so the report doesn't grow with every single "Attended" session — that's
	# what made it choke on large subject/group combinations before this field existed.
	detail_status_ids = fields.Many2many(
		string="Detail statuses", comodel_name="ems.attendance_status", default=lambda self: self._default_detail_status_ids(),
	)
	include_strikes = fields.Boolean(string="Include strikes", default=True)
	# Shown as an inline alert on the form (not a blocking dialog) when detail_status_ids grows
	# beyond the default absence-only set - see _compute_detail_status_warning.
	detail_status_warning = fields.Boolean(compute='_compute_detail_status_warning')

	from_date = fields.Date(string="From", default=fields.Datetime.now, required=True)
	to_date = fields.Date(string="To", default=fields.Datetime.now, required=True)

	def _default_detail_status_ids(self):
		return self.env['ems.attendance_status'].search([('category', '=', 'absence')])

	@api.depends('detail_status_ids')
	def _compute_detail_status_warning(self):
		for wizard in self:
			default_ids = set(wizard._default_detail_status_ids().ids)
			wizard.detail_status_warning = not set(wizard.detail_status_ids.ids) <= default_ids

	@api.model
	def default_get(self, fields_list):
		res = super().default_get(fields_list)
		if 'allowed_subject_ids' in fields_list:
			res['allowed_subject_ids'] = [(6, 0, self._get_allowed_subject_ids().ids)]
		return res

	def _get_current_teacher(self):
		# TODO: use this to set the permissions (uid = 1 means ADMIN)
		return self.env["hr.employee"].search([("user_id", "=", self.env.uid)])

	def _get_allowed_subject_ids(self):
		current_teacher = self._get_current_teacher()
		domain = [('teacher_id', '=', current_teacher.id)] if current_teacher.id > 1 else []
		return self.env["ems.teaching"].search(domain).mapped('subject_id')

	def _get_allowed_group_ids(self, subject):
		if not subject:
			return self.env["ems.group"]
		current_teacher = self._get_current_teacher()
		domain = [('subject_id', '=', subject.id)]
		if current_teacher.id > 1:
			domain.append(('teacher_id', '=', current_teacher.id))
		return self.env["ems.teaching"].search(domain).mapped('group_id')

	@api.depends_context('uid')
	def _compute_allowed_subject_ids(self):
		subjects = self._get_allowed_subject_ids()
		for wizard in self:
			wizard.allowed_subject_ids = subjects

	@api.depends('subject_id')
	def _compute_allowed_group_ids(self):
		for wizard in self:
			wizard.allowed_group_ids = wizard._get_allowed_group_ids(wizard.subject_id)

	@api.depends('group_ids.tutor_id')
	def _compute_tutor_ids(self):
		for wizard in self:
			wizard.tutor_ids = wizard.group_ids.tutor_id

	@api.onchange("subject_id")
	def _onchange_subject_id(self):
		for wizard in self:
			allowed_groups = wizard._get_allowed_group_ids(wizard.subject_id)
			# Pre-fill with every group teaching the subject; the user can then remove the
			# ones they don't want (the field stays editable, restricted to allowed_group_ids).
			wizard.group_ids = allowed_groups
			if wizard.subject_id.id != False:
				sessions = self.env["ems.attendance_session_header"].search([
					("subject_id", "=", wizard.subject_id.id), ("group_ids", "in", allowed_groups.ids),
				])
				first = sessions.search([], order="date asc", limit=1)
				last = sessions.search([], order="date desc", limit=1)
				wizard.from_date = first.date
				wizard.to_date = last.date

	def print(self):
		session_ids = self.env["ems.attendance_session_header"].search([
			("group_ids", "in", self.group_ids.ids),
			("subject_id", "=", self.subject_id.id),
			("date", ">=", self.from_date),
			("date", "<=", self.to_date),
		]).ids

		# Exclude student-less lines: when a student partner is hard-deleted, their session
		# lines survive with student_id = NULL (Odoo's default ondelete='set null'). Grouping
		# those by student would render a phantom blank-name row/group in the PDF.
		status_ids = self.env["ems.attendance_session_line"].search([
			("attendance_session_id", "in", session_ids), ("student_id", "!=", False),
		]).ids

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

		wizard = self.env["ems.attendance_report_subject_wizard"].browse(data['doc_ids'])
		detail_status_ids = set(wizard.detail_status_ids.ids)

		# Per-student "Details"/"Strikes" sections: kept out of _report_data (which still
		# aggregates every entry, regardless of detail_status_ids, for the % summary) since
		# they're only used for the optional, filterable session-by-session listing.
		detail_entries = {}
		detail_strikes = {}
		for student, student_entries in grp_by_student.items():
			detail_entries[student] = [entry for entry in student_entries if entry.status_id.id in detail_status_ids]
			detail_strikes[student] = self.env['ems.strike'].search([
				('attendance_session_line_id', 'in', [entry.id for entry in student_entries]),
			]) if wizard.include_strikes else self.env['ems.strike']

		return {
			'doc_ids': docids,
			'doc_model': 'ems.attendance_report_subject_wizard',
			'docs': wizard,
			'main': main,
			'lines': lines,
			'detail_entries': detail_entries,
			'detail_strikes': detail_strikes,
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
