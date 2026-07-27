# -*- coding: utf-8 -*-

from odoo import models, fields, api

overall_status = [("assistance", "Assistance"), ("absence", "Absence")]

# A single wizard (ems.attendance_report_wizard) drives all 3 PDF variants through a 'report_type'
# selector (by group / by student / by subject). Each variant filters the same
# ems.attendance_session_line data, groups it by a different dimension and renders its own QWeb
# template (reports/attendance/{group,student,subject}.xml) via its own ir.actions.report — the
# render side is deliberately left as 3 templates/actions so grouping/layout stay explicit.


class EmsAttendanceReportWizard(models.TransientModel):
	_name = "ems.attendance_report_wizard"
	_description = "Attendance report wizard (by group / student / subject)."

	report_type = fields.Selection(
		string="Report type",
		selection=[("group", "By group"), ("student", "By student"), ("subject", "By subject")],
		required=True, default="group",
	)

	# Selection fields: only the one matching report_type is shown/required (see the view).
	group_id = fields.Many2one(string="Group", comodel_name="ems.group")
	student_id = fields.Many2one(string="Student", comodel_name="res.partner", domain="[('contact_type', '=', 'student')]")
	subject_id = fields.Many2one(string="Subject", comodel_name="ems.subject")
	group_ids = fields.Many2many(string="Groups", comodel_name="ems.group")

	# Dropdown scoping (a teacher only sees their own teaching); computed per report_type.
	allowed_group_ids = fields.Many2many("ems.group", compute="_compute_allowed_ids")
	allowed_student_ids = fields.Many2many("res.partner", compute="_compute_allowed_ids")
	allowed_subject_ids = fields.Many2many("ems.subject", compute="_compute_allowed_ids")

	# Read-only, informational: the tutor(s) of whatever is currently selected, whichever the type.
	tutor_ids = fields.Many2many(string="Tutors", comodel_name="hr.employee", compute="_compute_tutor_ids")

	# Per-dimension "Details"/"Strikes" sections of the PDF: default to absence-category statuses
	# only, so the detail listing doesn't grow with every single "Attended" session (which is what
	# made the by-subject report choke on large subject/group combinations).
	detail_status_ids = fields.Many2many(
		string="Detail statuses", comodel_name="ems.attendance_status",
		default=lambda self: self._default_detail_status_ids(),
	)
	include_strikes = fields.Boolean(string="Include strikes", default=True)
	# Inline alert (not a blocking dialog) shown when detail_status_ids grows beyond the default.
	detail_status_warning = fields.Boolean(compute="_compute_detail_status_warning")

	from_date = fields.Date(string="From", default=fields.Datetime.now, required=True)
	to_date = fields.Date(string="To", default=fields.Datetime.now, required=True)

	# --- defaults / teacher-scoping helpers ---------------------------------------------------

	def _default_detail_status_ids(self):
		return self.env["ems.attendance_status"].search([("category", "=", "absence")])

	def _get_current_teacher(self):
		# An employee id <= 1 means ADMIN: no teacher-scoping is applied to the dropdowns.
		return self.env["hr.employee"].search([("user_id", "=", self.env.uid)])

	def _get_teacher_group_ids(self):
		teacher = self._get_current_teacher()
		domain = [("teacher_id", "=", teacher.id)] if teacher.id > 1 else []
		return self.env["ems.teaching"].search(domain).mapped("group_id")

	def _get_teacher_subject_ids(self):
		teacher = self._get_current_teacher()
		domain = [("teacher_id", "=", teacher.id)] if teacher.id > 1 else []
		return self.env["ems.teaching"].search(domain).mapped("subject_id")

	def _get_teacher_student_ids(self):
		teacher = self._get_current_teacher()
		if teacher.id <= 1:
			return self.env["ems.enrollment"].search([]).mapped("student_id")
		# A student is allowed if enrolled in a (group, subject) pair the teacher actually teaches.
		teachings = self.env["ems.teaching"].search([("teacher_id", "=", teacher.id)])
		taught_pairs = {(teaching.group_id.id, teaching.subject_id.id) for teaching in teachings}
		enrollments = self.env["ems.enrollment"].search([("group_id", "in", teachings.mapped("group_id").ids)])
		enrollments = enrollments.filtered(lambda enrollment: (enrollment.group_id.id, enrollment.subject_id.id) in taught_pairs)
		return enrollments.mapped("student_id")

	def _get_groups_teaching(self, subject):
		if not subject:
			return self.env["ems.group"]
		teacher = self._get_current_teacher()
		domain = [("subject_id", "=", subject.id)]
		if teacher.id > 1:
			domain.append(("teacher_id", "=", teacher.id))
		return self.env["ems.teaching"].search(domain).mapped("group_id")

	@api.model
	def default_get(self, fields_list):
		# A compute that only depends on context (uid) isn't reliably run on a freshly-opened
		# wizard, so seed the allowed_* sets here (default_get is always called on form open).
		res = super().default_get(fields_list)
		res.setdefault("allowed_group_ids", [(6, 0, self._get_teacher_group_ids().ids)])
		res.setdefault("allowed_student_ids", [(6, 0, self._get_teacher_student_ids().ids)])
		res.setdefault("allowed_subject_ids", [(6, 0, self._get_teacher_subject_ids().ids)])
		return res

	# --- computes -----------------------------------------------------------------------------

	@api.depends_context("uid")
	@api.depends("report_type", "subject_id")
	def _compute_allowed_ids(self):
		for wizard in self:
			wizard.allowed_student_ids = wizard._get_teacher_student_ids()
			wizard.allowed_subject_ids = wizard._get_teacher_subject_ids()
			# For the by-subject variant the group picker is scoped to groups teaching the chosen
			# subject; otherwise (by-group) it's scoped to the teacher's own groups.
			if wizard.report_type == "subject":
				wizard.allowed_group_ids = wizard._get_groups_teaching(wizard.subject_id)
			else:
				wizard.allowed_group_ids = wizard._get_teacher_group_ids()

	@api.depends("report_type", "group_id.tutor_id", "student_id.tutor_id", "group_ids.tutor_id")
	def _compute_tutor_ids(self):
		for wizard in self:
			if wizard.report_type == "group":
				wizard.tutor_ids = wizard.group_id.tutor_id
			elif wizard.report_type == "student":
				wizard.tutor_ids = wizard.student_id.tutor_id
			else:
				wizard.tutor_ids = wizard.group_ids.tutor_id

	@api.depends("detail_status_ids")
	def _compute_detail_status_warning(self):
		for wizard in self:
			default_ids = set(wizard._default_detail_status_ids().ids)
			wizard.detail_status_warning = not set(wizard.detail_status_ids.ids) <= default_ids

	# --- onchange: fill From/To from the selection's own session range ------------------------

	def _fill_dates(self, sessions):
		if not sessions:
			return
		ordered = sessions.sorted("date")
		self.from_date = ordered[0].date
		self.to_date = ordered[-1].date

	@api.onchange("group_id")
	def _onchange_group_id(self):
		for wizard in self:
			if wizard.report_type == "group" and wizard.group_id:
				wizard._fill_dates(self.env["ems.attendance_session_header"].search([
					("group_ids", "in", [wizard.group_id.id]),
				]))

	@api.onchange("student_id")
	def _onchange_student_id(self):
		for wizard in self:
			if wizard.report_type == "student" and wizard.student_id:
				sessions = self.env["ems.attendance_session_line"].search([
					("student_id", "=", wizard.student_id.id),
				]).mapped("attendance_session_id")
				wizard._fill_dates(sessions)

	@api.onchange("subject_id")
	def _onchange_subject_id(self):
		for wizard in self:
			if wizard.report_type != "subject":
				continue
			allowed_groups = wizard._get_groups_teaching(wizard.subject_id)
			# Pre-fill with every group teaching the subject; the user can then remove the ones
			# they don't want (the field stays editable, restricted to allowed_group_ids).
			wizard.group_ids = allowed_groups
			if wizard.subject_id:
				wizard._fill_dates(self.env["ems.attendance_session_header"].search([
					("subject_id", "=", wizard.subject_id.id), ("group_ids", "in", allowed_groups.ids),
				]))

	# --- action -------------------------------------------------------------------------------

	def print(self):
		self.ensure_one()
		line_model = self.env["ems.attendance_session_line"]
		if self.report_type == "student":
			status_ids = line_model.search([
				("student_id", "=", self.student_id.id),
				("attendance_session_id.date", ">=", self.from_date),
				("attendance_session_id.date", "<=", self.to_date),
			]).ids
			report_ref = "ems.action_attendance_report_student"
		else:
			session_domain = [("date", ">=", self.from_date), ("date", "<=", self.to_date)]
			if self.report_type == "group":
				session_domain.append(("group_ids", "in", [self.group_id.id]))
				report_ref = "ems.action_attendance_report_group"
			else:
				session_domain += [("group_ids", "in", self.group_ids.ids), ("subject_id", "=", self.subject_id.id)]
				report_ref = "ems.action_attendance_report_subject"
			session_ids = self.env["ems.attendance_session_header"].search(session_domain).ids
			# Exclude student-less lines: when a student partner is hard-deleted, their session
			# lines survive with student_id = NULL (Odoo's default ondelete='set null'). Grouping
			# those by student would render a phantom blank-name row/group in the PDF.
			status_ids = line_model.search([
				("attendance_session_id", "in", session_ids), ("student_id", "!=", False),
			]).ids

		data = {"doc_ids": [self.read()[0]["id"]], "status_ids": status_ids}
		return self.env.ref(report_ref).with_context(landscape=True).report_action(None, data=data)


def _build_report_values(env, docids, data, group_key):
	# Shared by the 3 report data models below: they only differ in group_key (the dimension the
	# per-line entries are grouped by for the detail sections).
	if not docids:
		docids = data["doc_ids"]  # report_action(None, ...) never sets active_ids, so docids is None here.
	entries = list(env["ems.attendance_session_line"].browse(data["status_ids"]))
	main = _report_data(entries, env)

	grouped = {}
	for entry in entries:
		grouped.setdefault(group_key(entry), []).append(entry)
	lines = {key: _report_data(items, env) for key, items in grouped.items()}

	wizard = env["ems.attendance_report_wizard"].browse(data["doc_ids"])
	detail_status_ids = set(wizard.detail_status_ids.ids)
	# Per-dimension "Details"/"Strikes" are kept out of _report_data (which still aggregates every
	# entry, regardless of detail_status_ids, for the % summary) — they're only the optional,
	# filterable session-by-session listing.
	detail_entries = {}
	detail_strikes = {}
	for key, items in grouped.items():
		detail_entries[key] = [entry for entry in items if entry.status_id.id in detail_status_ids]
		detail_strikes[key] = env["ems.strike"].search([
			("attendance_session_line_id", "in", [entry.id for entry in items]),
		]) if wizard.include_strikes else env["ems.strike"]

	return {
		"doc_ids": docids,
		"doc_model": "ems.attendance_report_wizard",
		"docs": wizard,
		"main": main,
		"lines": lines,
		"detail_entries": detail_entries,
		"detail_strikes": detail_strikes,
		"attendance_session_line": {status.id: status.name for status in env["ems.attendance_status"].with_context(active_test=False).search([])},
		"overall_status": dict(overall_status),
	}


class EmsAttendanceReportGroup(models.AbstractModel):
	_name = "report.ems.attendance_report_group"
	_description = "Attendance report data: by group."

	def _get_report_values(self, docids, data=None):
		return _build_report_values(self.env, docids, data, lambda entry: entry.attendance_session_id.subject_id)


class EmsAttendanceReportStudent(models.AbstractModel):
	_name = "report.ems.attendance_report_student"
	_description = "Attendance report data: by student."

	def _get_report_values(self, docids, data=None):
		return _build_report_values(self.env, docids, data, lambda entry: entry.attendance_session_id.subject_id)


class EmsAttendanceReportSubject(models.AbstractModel):
	_name = "report.ems.attendance_report_subject"
	_description = "Attendance report data: by subject."

	def _get_report_values(self, docids, data=None):
		return _build_report_values(self.env, docids, data, lambda entry: entry.student_id)


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
