# -*- coding: utf-8 -*-

from odoo import api, fields, models

overall_status = [("assistance", "Assistance"), ("absence", "Absence")]

REPORT_REFS = {
	"group": "ems.action_attendance_report_group",
	"student": "ems.action_attendance_report_student",
	"subject": "ems.action_attendance_report_subject",
}

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
	# The subject as the reports list it: 'subject [- topic]' (issue #633), so a topic taught apart
	# is a subject of its own. Its options are the user's own (_selection_subject_label); a value
	# outside their scope sent by hand only ever reaches the lines in scope, i.e. none.
	subject_label = fields.Selection(string="Subject", selection="_selection_subject_label")
	group_ids = fields.Many2many(string="Groups", comodel_name="ems.group")

	# Dropdown scoping: what the user may consult (see _get_scope_lines); computed per report_type.
	allowed_group_ids = fields.Many2many("ems.group", compute="_compute_allowed_ids")
	allowed_student_ids = fields.Many2many("res.partner", compute="_compute_allowed_ids")

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

	# --- scope: one source with the 'Reports' screen ------------------------------------------

	def _default_detail_status_ids(self):
		return self.env["ems.attendance_status"].search([("category", "=", "absence")])

	@api.model
	def _get_scope_lines(self, domain, date_range=None):
		"""The attendance lines the user may consult (ems.attendance_session_line._get_reports_domain(),
		the same the 'Reports' screen shows, issue #633) narrowed down by 'domain' and, if given, a
		(from, to) 'date_range'. Searched as the user, returned under sudo(): the scope is already
		decided by the domain, and the PDF reads the session's date and teacher, which the session's
		record rules hide from a tutor or a chief when another teacher took it. active_test forced on:
		a student removed from the roll-call (archived line) never counts, even when the wizard is
		reached from a screen listing archived records (issue #628)."""
		Line = self.env["ems.attendance_session_line"].with_context(active_test=True)
		domain = Line._get_reports_domain() + domain
		if date_range:
			domain += [("date", ">=", date_range[0]), ("date", "<=", date_range[1])]
		return Line.search(domain).sudo()

	@api.model
	def _get_scope_values(self, field_name, domain=None):
		"""The distinct values of one field over the user's scope (_get_scope_lines' domain), without
		loading the lines: what the dropdowns offer."""
		Line = self.env["ems.attendance_session_line"].with_context(active_test=True)
		groups = Line._read_group(Line._get_reports_domain() + (domain or []), [field_name])
		return [value for value, in groups if value]

	@api.model
	def _selection_subject_label(self):
		return [(label, label) for label in sorted(self._get_scope_values("subject_label"))]

	def _date_range(self):
		return (self.from_date, self.to_date)

	def _get_student_lines(self, date_range=True):
		"""The by-student report's lines: every subject of this one student in the user's scope."""
		self.ensure_one()
		if not self.student_id:
			return self.env["ems.attendance_session_line"]
		return self._get_scope_lines([("student_id", "=", self.student_id._origin.id)], date_range and self._date_range())

	def _get_group_lines(self, date_range=True):
		"""The by-group report's lines: those of the group's students, by the group each line keeps
		from its roll-call (student_group_id), not by the session's groups, which would bring in
		every other group's students of a shared session."""
		self.ensure_one()
		if not self.group_id:
			return self.env["ems.attendance_session_line"]
		return self._get_scope_lines(
			[("student_group_id", "=", self.group_id._origin.id), ("student_id", "!=", False)],
			date_range and self._date_range())

	def _get_subject_lines(self, date_range=True):
		"""The by-subject report's lines: the selected subject (and topic) of the selected groups'
		students, by the group each line keeps from its roll-call, like the by-group report.
		Student-less lines (a hard-deleted student keeps their lines with student_id = NULL) would
		render a phantom blank row."""
		self.ensure_one()
		if not self.subject_label:
			return self.env["ems.attendance_session_line"]
		# _origin: inside an onchange the wizard's x2many values are NewId copies of the groups.
		return self._get_scope_lines([
			("subject_label", "=", self.subject_label),
			("student_group_id", "in", self.group_ids._origin.ids),
			("student_id", "!=", False),
		], date_range and self._date_range())

	def _get_groups_teaching(self, subject_label):
		"""The groups whose students have the given subject (and topic) in the user's scope."""
		if not subject_label:
			return self.env["ems.group"]
		return self.env["ems.group"].browse(
			[group.id for group in self._get_scope_values("student_group_id", [("subject_label", "=", subject_label)])])

	@api.model
	def default_get(self, fields_list):
		# A compute that only depends on context (uid) isn't reliably run on a freshly-opened
		# wizard, so seed the allowed_* sets here (default_get is always called on form open).
		res = super().default_get(fields_list)
		res.setdefault("allowed_group_ids", [(6, 0, [group.id for group in self._get_scope_values("student_group_id")])])
		res.setdefault("allowed_student_ids", [(6, 0, [student.id for student in self._get_scope_values("student_id")])])
		res.update(self._defaults_from_search())
		return res

	@api.model
	def _defaults_from_search(self):
		"""The report the 'Reports' screen's active search facets point at (issue #633), passed by its
		print button as ems_report_<field> context keys (attendance_report_print.js): a student gives
		the by-student report; a subject the by-subject one, its groups narrowed to the group facet if
		there is one; a group alone the by-group one. The onchanges then fill the dates and groups,
		as when picked by hand (the form's first onchange runs them for every default). A subject
		split into several topics in the user's scope leaves the subject to pick."""
		context = self.env.context
		student, group, subject = (context.get(f"ems_report_{name}")
								   for name in ("student_id", "student_group_id", "subject_id"))
		if student:
			return {"report_type": "student", "student_id": student}
		if subject:
			labels = self._get_scope_values("subject_label", [("subject_id", "=", subject)])
			return {"report_type": "subject", "subject_label": labels[0] if len(labels) == 1 else False}
		if group:
			return {"report_type": "group", "group_id": group}
		return {}

	# --- computes -----------------------------------------------------------------------------

	@api.depends_context("uid")
	@api.depends("report_type", "subject_label")
	def _compute_allowed_ids(self):
		for wizard in self:
			wizard.allowed_student_ids = self.env["res.partner"].browse(
				[student.id for student in wizard._get_scope_values("student_id")])
			# For the by-subject variant the group picker is scoped to the groups having the chosen
			# subject; otherwise (by-group) to every group in scope.
			if wizard.report_type == "subject":
				wizard.allowed_group_ids = wizard._get_groups_teaching(wizard.subject_label)
			else:
				wizard.allowed_group_ids = self.env["ems.group"].browse(
					[group.id for group in wizard._get_scope_values("student_group_id")])

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

	# --- onchange: fill From/To from the selection's own lines --------------------------------

	def _fill_dates(self, lines):
		if not lines:
			return
		dates = lines.mapped("date")
		self.from_date = min(dates)
		self.to_date = max(dates)

	@api.onchange("group_id")
	def _onchange_group_id(self):
		for wizard in self:
			if wizard.report_type == "group" and wizard.group_id:
				wizard._fill_dates(wizard._get_group_lines(date_range=False))

	@api.onchange("student_id")
	def _onchange_student_id(self):
		for wizard in self:
			if wizard.report_type == "student" and wizard.student_id:
				wizard._fill_dates(wizard._get_student_lines(date_range=False))

	@api.onchange("subject_label")
	def _onchange_subject_label(self):
		for wizard in self:
			if wizard.report_type != "subject":
				continue
			# Pre-fill with every group having the subject, or only the group filtered on the screen
			# the wizard was opened from (_defaults_from_search); the user can then remove or add
			# groups (the field stays editable, restricted to allowed_group_ids).
			groups = wizard._get_groups_teaching(wizard.subject_label)
			searched = groups.browse(self.env.context.get("ems_report_student_group_id")) & groups
			wizard.group_ids = searched or groups
			if wizard.subject_label:
				wizard._fill_dates(wizard._get_subject_lines(date_range=False))

	# --- action -------------------------------------------------------------------------------

	def print(self):
		# Printed on the wizard itself (docids, no data): the PDF recomputes its lines from the
		# wizard, and the download gets its file name from print_report_name.
		self.ensure_one()
		return self.env.ref(REPORT_REFS[self.report_type]).with_context(landscape=True).report_action(self)

	# --- business -----------------------------------------------------------------------------

	def _get_report_lines(self):
		"""The session lines the selected report covers."""
		self.ensure_one()
		return {
			"student": self._get_student_lines,
			"group": self._get_group_lines,
			"subject": self._get_subject_lines,
		}[self.report_type]()

	def get_report_filename(self):
		"""Download file name (print_report_name of the 3 reports): the report's own name plus the
		student, group or subject it's about, so several downloads can be told apart."""
		self.ensure_one()
		subject = {"group": self.group_id.name, "student": self.student_id.name, "subject": self.subject_label}[self.report_type]
		# No colon: the subject's label carries one ('ACR: Name') and some systems reject it in a file name.
		return f"{self.env.ref(REPORT_REFS[self.report_type]).name}_{(subject or '').replace(':', '').replace(' ', '_')}"


def _build_report_values(env, docids, group_key):
	# Shared by the 3 report data models below: they only differ in group_key (the dimension the
	# per-line entries are grouped by for the detail sections). docids is the wizard: the lines are
	# always recomputed from it, never taken from the client (see _get_scope_lines).
	wizard = env["ems.attendance_report_wizard"].browse(docids)
	report_lines = wizard._get_report_lines()
	entries = list(report_lines)
	main = _report_data(entries, env)

	grouped = {}
	for entry in entries:
		grouped.setdefault(group_key(entry), []).append(entry)
	lines = {key: _report_data(items, env) for key, items in grouped.items()}

	detail_status_ids = set(wizard.detail_status_ids.ids)
	# Per-dimension "Details"/"Strikes" are kept out of _report_data (which still aggregates every
	# entry, regardless of detail_status_ids, for the % summary) — they're only the optional,
	# filterable session-by-session listing.
	detail_entries = {}
	detail_strikes = {}
	for key, items in grouped.items():
		detail_entries[key] = [entry for entry in items if entry.status_id.id in detail_status_ids]
		# Same environment as the lines (sudo): the strikes of lines already in the user's scope, the
		# ones the 'Reports' screen counts as strike_count.
		detail_strikes[key] = report_lines.env["ems.strike"].search([
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
		# Translated here, in the report's language: the module-level labels are only the keys' English.
		"overall_status": {"assistance": env._("Assistance"), "absence": env._("Absence")},
	}


class EmsAttendanceReportGroup(models.AbstractModel):
	_name = "report.ems.attendance_report_group"
	_description = "Attendance report data: by group."

	def _get_report_values(self, docids, data=None):
		return _build_report_values(self.env, docids, lambda entry: entry.subject_label)


class EmsAttendanceReportStudent(models.AbstractModel):
	_name = "report.ems.attendance_report_student"
	_description = "Attendance report data: by student."

	def _get_report_values(self, docids, data=None):
		return _build_report_values(self.env, docids, lambda entry: entry.subject_label)


class EmsAttendanceReportSubject(models.AbstractModel):
	_name = "report.ems.attendance_report_subject"
	_description = "Attendance report data: by subject."

	def _get_report_values(self, docids, data=None):
		return _build_report_values(self.env, docids, lambda entry: entry.student_id)


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
