# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from markupsafe import Markup
import xml.etree.ElementTree as ET
import base64
import json
import math
import re


def _m2m_command_ids(commands):
	"""Resolve a Many2many/One2many value (as found in raw create()/write() vals) into a plain list
	of ids - used by the working-schedule block's own create() override, which needs to read an id
	list out of a not-yet-written value rather than an already-browsable recordset. Accepts either
	the real command-tuple format ('(6, 0, ids)', '(4, id)'...) or a bare list of ids (the shape the
	Schedule tab's own grid widget cells use for 'group_ids') - both are valid Many2many vals."""
	ids = []
	for command in commands or []:
		if isinstance(command, int):
			ids.append(command)
		elif command[0] in (4, 1):
			ids.append(command[1])
		elif command[0] == 6:
			ids.extend(command[2])
	return ids

class ems_working_schedule(models.Model):
	# NOTE: 'ems.schedule_report_mixin' is only mixed in alongside 'resource.calendar' — a 2-item
	# '_inherit' list without an explicit '_name' would make Odoo's metaclass define a brand-new model
	# named after this Python class instead of extending 'resource.calendar' in place (see MetaModel
	# in odoo/models.py: '_name' defaults to the class name whenever len(_inherit) != 1).
	_name = 'resource.calendar'
	_inherit = ['resource.calendar', 'ems.schedule_report_mixin']
	_sql_constraints = [
		('unique_name', 'unique (name)', 'duplicated calendar!')
    ]

	is_framework = fields.Boolean(string="Schedule framework", help="A reusable blank period template for a level of studies, instead of a real teacher's schedule.")
	level_id = fields.Many2one(string="Level", comodel_name="ems.level")
	# NOTE: the calendar this teacher's schedule was originally built from. Unassigned periods are
	# never stored as real attendance rows (see apply_schedule_changes) — this reference is what lets
	# the 'Schedule' tab's grid widget keep showing the framework's blank slots (and its own patio/
	# meeting periods) as editable/inherited on every future "Edit", without persisting them.
	source_framework_id = fields.Many2one(string="Source framework", comodel_name="resource.calendar", domain="[('is_framework', '=', True)]")
	# NOTE: added 2026-08-06 (see plans/course_transition_teacher_schedule_archival.md) - a personal
	# calendar's own 'employee_id'/'course_id' make it queryable as a historical "who taught what,
	# which course" record on its own terms, without going through 'ems.attendance_template' (which
	# a teacher can create directly, bypassing the calendar entirely, so it can't be trusted as a
	# complete record). 'employee_id' is set once at creation and never reassigned - unlike
	# 'hr.employee.resource_calendar_id' (which moves on to a new calendar every course, once a later
	# phase of that same plan wires it up), this is the calendar's own permanent back-reference, so
	# 'get_employee()' below keeps working even for a calendar no longer any employee's *current* one.
	# Both stay empty for a framework calendar (reusable template, never tied to one teacher/course).
	employee_id = fields.Many2one(string="Teacher", comodel_name="hr.employee")
	course_id = fields.Many2one(string="Course", comodel_name="ems.course")

	@api.model_create_multi
	def create(self, vals_list):
		"""Auto-derives 'name' ("<teacher> (<course>)", matching the long-standing convention) from
		'employee_id'/'course_id' when the caller sets those but not an explicit 'name' - a single
		source of truth for the naming convention, instead of every caller having to remember to
		build the string by hand (see plans/course_transition_teacher_schedule_archival.md)."""
		for vals in vals_list:
			if not vals.get('name') and vals.get('employee_id'):
				employee = self.env['hr.employee'].browse(vals['employee_id'])
				course = self.env['ems.course'].browse(vals['course_id']) if vals.get('course_id') else False
				vals['name'] = "%s (%s)" % (employee.name, course.name) if course else employee.name
		return super().create(vals_list)

	def _refresh_personal_name(self):
		"""Rebuilds 'name' from this calendar's own 'employee_id'/'course_id' - called after either
		changes, or after the linked employee's own name does (see 'ems_employee.write()'). No-op
		for a framework calendar (its name is set by hand, never derived). Falls back to
		'get_employee()' (the reverse search) for a legacy calendar predating 'employee_id' - not yet
		backfilled by a migration, but its name must still keep tracking a rename in the meantime."""
		for calendar in self:
			if calendar.is_framework:
				continue
			employee = calendar.employee_id or calendar.get_employee()
			if not employee:
				continue
			course = calendar.course_id
			calendar.name = "%s (%s)" % (employee.name, course.name) if course else employee.name

	def seed_from_framework(self, framework):
		"""Point this calendar at 'framework' as its reference bell schedule and clear any existing
		weekday (Mon-Fri) attendances. The framework's own periods (including patio/meeting slots)
		only become real rows the first time the 'Schedule' tab actually saves them — nothing is
		written here, matching the rule that unassigned slots are never stored."""
		self.ensure_one()
		self.attendance_ids.filtered(lambda attendance: attendance.dayofweek in ('0', '1', '2', '3', '4')).unlink()
		self.source_framework_id = framework.id

	def apply_schedule_changes(self, cells, source_framework_id=None):
		"""Replace this calendar's weekday (Mon-Fri) attendances with 'cells' (called from the
		'Schedule' tab's grid widget, whose buffer already represents the full weekly state — unassigned
		slots are never included, only real subject/non-teaching entries), then re-derive the teacher's
		'teaching_ids' from the same cells so both stay in sync. 'source_framework_id' is only passed
		when "New" picked a different reference framework (directly, or inherited by copying a
		colleague), so future edits keep showing the right blank slots."""
		self.ensure_one()
		self.attendance_ids.filtered(lambda attendance: attendance.dayofweek in ('0', '1', '2', '3', '4')).unlink()
		self.write({'attendance_ids': [(0, 0, cell) for cell in cells]})
		if source_framework_id:
			self.source_framework_id = source_framework_id

		teacher = self.get_employee()
		if teacher:
			entries = [cell for cell in cells if cell.get('subject_id')]
			self.env['ems.teaching'].sync_from_schedule(teacher, entries)
			self.env['ems.attendance_template'].sync_from_schedule(teacher, entries, start_date=fields.Date.today())

	def get_employee(self):
		"""The teacher this calendar belongs to (a documented 1:1 assumption: one personal calendar
		per teacher). Also matches a 'framework'/other non-personal calendar with an empty recordset.
		Prefers the stored 'employee_id' (added 2026-08-06) - unlike the reverse search below, it
		keeps working once this calendar is no longer any employee's *current* one (see
		plans/course_transition_teacher_schedule_archival.md), which is exactly the point of storing
		it. Falls back to the reverse search for a calendar predating that field (not yet backfilled
		by a migration) - never breaks a calendar that simply hasn't been touched yet."""
		self.ensure_one()
		return self.employee_id or self.env['hr.employee'].search([('resource_calendar_id', '=', self.id)])

	def get_schedule_report_lines(self):
		"""Weekly schedule rows (one per distinct Mon-Fri period, one column per weekday) for the
		working schedule PDF report. Unassigned slots are never stored (see apply_schedule_changes),
		so every attendance row here is a real subject or non-teaching commitment. Each cell carries
		the matching attendance record (or False) plus a 'color': the same subject/non-teaching reason
		always gets the same color, even across different days, to make the printed grid easier to
		scan at a glance. A break the teacher's own calendar has no real saved row for yet is filled
		in from 'hr.employee._get_derived_break_entries()' (level-framework-derived, see that
		method), skipped for any slot a real entry already occupies."""
		self.ensure_one()
		weekday_entries = self.attendance_ids.filtered(lambda attendance: attendance.dayofweek in ('0', '1', '2', '3', '4'))
		employee = self.get_employee()
		if employee:
			occupied = {(attendance.dayofweek, attendance.hour_from, attendance.hour_to) for attendance in weekday_entries}
			derived_breaks = employee._get_derived_break_entries().filtered(
				lambda attendance: (attendance.dayofweek, attendance.hour_from, attendance.hour_to) not in occupied)
			weekday_entries = weekday_entries | derived_breaks
		periods = sorted({(attendance.hour_from, attendance.hour_to) for attendance in weekday_entries})

		color_by_key = {}
		for attendance in weekday_entries.sorted(key=lambda attendance: (attendance.dayofweek, attendance.hour_from)):
			key = self._report_color_key(attendance)
			if key not in color_by_key:
				color_by_key[key] = self.REPORT_COLOR_PALETTE[len(color_by_key) % len(self.REPORT_COLOR_PALETTE)]

		lines = []
		for hour_from, hour_to in periods:
			cells = []
			for dayofweek in ('0', '1', '2', '3', '4'):
				entry = weekday_entries.filtered(
					lambda attendance, dayofweek=dayofweek, hour_from=hour_from, hour_to=hour_to:
						attendance.dayofweek == dayofweek and attendance.hour_from == hour_from and attendance.hour_to == hour_to
				)
				cells.append({
					'entry': entry,
					'color': color_by_key.get(self._report_color_key(entry)) if entry else False,
				})
			lines.append({
				'time_label': "%s-%s" % (self._format_report_time(hour_from), self._format_report_time(hour_to)),
				'cells': cells,
			})
		return lines

	# Wednesday is dayofweek '2' (dayofweek follows date.weekday(): '0'=Monday).
	FIXED_HOURS_WEDNESDAY = '2'

	def get_schedule_hours_summary(self):
		"""Weekly hours totals for the Schedule tab's summary table, split into two columns exactly
		like the real external schedules this data is modelled on:
		- 'teaching': weekly teaching hours grouped by level (ems.group.level_id) — or, for reinforcement
		  groups (no single level), grouped per group instead — plus every non-teaching activity that
		  ISN'T a guard duty or a Wednesday coordination meeting (the break, 'BR', is dropped entirely
		  from both columns).
		- 'fixed': guard duties (any day) and coordination meetings ('CM') specifically on Wednesday —
		  the centre's fixed non-teaching commitments.
		Each period's duration is rounded UP to the nearest whole hour (a period that only partially
		overlaps an hour still counts as one full hour), then summed. Not stored — cheap to compute
		from the calendar's own attendance_ids, and reused as-is by the PDF report's own summary table
		later. For a full-time teacher, 'total' should equal 24 (full_time_required_hours)."""
		self.ensure_one()
		weekday_entries = self.attendance_ids.filtered(lambda attendance: attendance.dayofweek in ('0', '1', '2', '3', '4'))

		teaching_rows = {}
		fixed_rows = {}
		for attendance in weekday_entries:
			duration = math.ceil(attendance.hour_to - attendance.hour_from)
			if attendance.subject_id:
				group = attendance.group_ids[:1]
				bucket = teaching_rows
				if group.group_type == 'reinforcement':
					key = ('reinforcement', group.id)
					label = group.display_name
				else:
					key = ('level', group.level_id.id)
					label = group.level_id.display_name
			elif attendance.non_teaching.is_break:
				continue
			elif attendance.non_teaching:
				is_fixed = attendance.non_teaching.is_fixed or (attendance.non_teaching.code == 'CM' and attendance.dayofweek == self.FIXED_HOURS_WEDNESDAY)
				bucket = fixed_rows if is_fixed else teaching_rows
				key = ('activity', attendance.non_teaching.id)
				label = attendance.get_report_label()
			else:
				continue

			if key not in bucket:
				bucket[key] = {'label': label, 'hours': 0}
			bucket[key]['hours'] += duration

		teaching = sorted(teaching_rows.values(), key=lambda row: row['label'])
		fixed = sorted(fixed_rows.values(), key=lambda row: row['label'])
		teaching_total = sum(row['hours'] for row in teaching)
		fixed_total = sum(row['hours'] for row in fixed)

		return {
			'teaching': {'rows': teaching, 'total': teaching_total},
			'fixed': {'rows': fixed, 'total': fixed_total},
			'total': teaching_total + fixed_total,
		}

class ems_working_schedule_assignation(models.Model):
	_inherit = 'resource.calendar.attendance'
	# NOTE: no need to constraint, the main model avoids overlapping.

	# NOTE: core 'resource.calendar.attendance' has no 'active' field at all - added 2026-08-06 so a
	# course transition can archive a teacher's migrating blocks instead of unlink()-ing them (which
	# would destroy the exact history a later "who taught what, which course" query needs - see
	# plans/course_transition_teacher_schedule_archival.md). Odoo's own generic action_archive()/
	# action_unarchive() (models.py) already work for any model with this field - no override needed
	# here yet; nothing writes 'active=False' on this model until a later phase of that same plan.
	active = fields.Boolean(default=True)
	non_teaching = fields.Many2one(string="Non-teaching", comodel_name="ems.non_teaching_type")
	subject_id = fields.Many2one(string="Subject", comodel_name="ems.subject")
	group_ids = fields.Many2many(string="Groups", comodel_name="ems.group")
	# NOTE: a plain stored field (not a compute) since 2026-08-01 - a schedule block's own room can
	# now genuinely diverge from its group's default (e.g. a one-off room reassignment resolving an
	# import conflict), and must stay put afterwards rather than being silently re-derived from the
	# group on every load. Still defaults from the group at creation time (create() below) for the
	# common case where no explicit room is given - same "first selected group wins when several
	# are assigned" convention already used by 'ems.attendance_template'.
	space_id = fields.Many2one(string="Classroom", comodel_name="ems.space", store=True)
	# NOTE: stored because it's read in bulk whenever a group's schedule is aggregated across many
	# different teachers' calendars (see ems.group.get_subject_teachers_summary) — computing it on the
	# fly for every row would mean one 'hr.employee' search per row instead of a plain read.
	employee_id = fields.Many2one(string="Teacher", comodel_name="hr.employee", compute="_compute_employee_id", store=True, compute_sudo=True)
	# NOTE: a plain 'related' so the Schedule tab's grid widget (client-side, from prefetched record
	# data) can single out a break from every OTHER non-teaching activity (guard duty, a coordination
	# meeting...) without fetching 'ems.non_teaching_type' separately — only a break is short enough
	# to need the grid's compact single-line rendering, see 'schedule_grid_field.js'/
	# 'group_schedule_grid_field.js'.
	non_teaching_is_break = fields.Boolean(related="non_teaching.is_break", store=True)

	@api.model_create_multi
	def create(self, vals_list):
		for vals in vals_list:
			if not vals.get('space_id'):
				group_ids = _m2m_command_ids(vals.get('group_ids'))
				if group_ids:
					vals['space_id'] = self.env['ems.group'].browse(group_ids[0]).space_id.id
		return super().create(vals_list)

	@api.depends("calendar_id")
	def _compute_employee_id(self):
		for attendance in self:
			attendance.employee_id = attendance.calendar_id.get_employee()

	def get_report_label(self):
		"""Display label for the working schedule PDF report. NOT 'self.name': that Char is frozen in
		whatever language was active when the row was saved (Edit/Import always write it in English —
		see 'non_teaching_items' in this file and 'catalog.nonTeaching' in schedule_grid_field.js), so a
		non-teaching row would otherwise always show "Guard" even when printing in Catalan/Spanish.
		'non_teaching.name' is translatable, so it resolves to the report's current language for free."""
		self.ensure_one()
		return self.non_teaching.name if self.non_teaching else self.name

class ems_working_schedules_import_wizard(models.TransientModel):
	_name = "ems.working_schedules_import_wizard"
	_description = "Working schedules: import wizard."
	_inherit = ['ems.datetime_utils']
	_EMAIL_RE = re.compile(r'\S+@\S+')

	# The only way in: a batch load, one or several planner files, each one possibly describing
	# several teachers (see create()). There is no per-employee scoped variant any more — a teacher
	# joining mid-year gets their schedule via the Schedule tab's own "New" panel (blank framework or
	# copy from another teacher) or by hand, never a single-file upload (see
	# docs/en/developers/employees/working_schedule.md).
	attachment_ids = fields.Many2many(string="Planner files (XML)", comodel_name="ir.attachment")
	# NOTE: gates the 'Continue' button on the intro screen - deliberately just "is any file
	# attached", nothing more. Found the hard way (2026-08-05, developer feedback after actually
	# using this screen): the old single-screen wizard's banners (unknown e-mail, unresolved
	# group/subject, room conflicts...) used to render here too, immediately on file upload - but
	# resolving those IS the whole point of steps 2 ("Resolve groups") through 5 ("Existing
	# schedule conflicts"), so blocking (or even just showing anything about) them on the WELCOME
	# screen pre-empts what those screens are for. Every one of those checks is deferred to
	# '_apply_import' at the final step instead (see '_classify_attachments'/'_continue_from_intro'
	# below) - until steps 2-6 exist to resolve them interactively, a real problem simply surfaces
	# later, at Import time, rather than here.
	ready_to_import = fields.Boolean(compute="_compute_ready_to_import", store=False)

	@api.depends("attachment_ids")
	def _compute_ready_to_import(self):
		for wizard in self:
			wizard.ready_to_import = bool(wizard.attachment_ids)

	# NOTE: the 7-screen guided flow (see plans/working_schedule_import_redesign.md's "Multi-step
	# wizard" section) - a statusbar Selection, non-clickable (no jumping steps by clicking the
	# bar itself; Cancel is the only way back, discarding the whole in-progress wizard). Only
	# 'intro' and 'groups' (this pass) have real per-step logic; the rest are placeholders that
	# just advance the statusbar until each one gets its own screen built (see 'action_continue').
	state = fields.Selection([
		('intro', "Welcome"),
		('groups', "Resolve groups"),
		('teachers', "Resolve teachers"),
		('pending_info', "Pending teachers"),
		('internal_conflicts', "File conflicts"),
		('db_conflicts', "Existing schedule conflicts"),
		('summary', "Overall summary"),
	], default='intro', required=True)
	# NOTE: JSON cache of the raw per-teacher-node parse result (see '_classify_attachments'),
	# populated once by 'action_continue' leaving 'intro' - nothing is written to any real model
	# before the final step's 'import_planner_data()' reads this back. A stored Text field survives
	# across this TransientModel's own several write() calls (one per statusbar step), unlike an
	# in-memory value would.
	parsed_entries_json = fields.Text(readonly=True)
	# NOTE: one line per distinct unresolved '<Students>' name found anywhere in the batch (see
	# '_continue_from_intro'/'_classify_attachments') - populated once, leaving 'intro', regardless
	# of whether it ends up empty (the 'groups' screen shows a success message instead of the list
	# in that case).
	group_line_ids = fields.One2many(string="Unresolved groups", comodel_name="ems.working_schedules_import_wizard.group_line", inverse_name="wizard_id")
	# NOTE: one line per distinct unresolved e-mail (see '_pending_teacher_identifiers') - populated
	# once, leaving 'groups' (not 'intro' - unlike 'group_line_ids', this needs the group picks
	# already applied first, per the flow's own 'groups --> teachers' transition).
	teacher_line_ids = fields.One2many(string="Unresolved teachers", comodel_name="ems.working_schedules_import_wizard.teacher_line", inverse_name="wizard_id")
	# NOTE: one line per colliding pair found by '_find_internal_conflicts' - populated once,
	# leaving 'teachers' (needs both group and teacher picks already applied - group resolution
	# affects which classroom an entry defaults to; teacher resolution affects the display label).
	internal_conflict_line_ids = fields.One2many(string="File conflicts", comodel_name="ems.working_schedules_import_wizard.internal_conflict_line", inverse_name="wizard_id")
	# NOTE: one line per colliding pair found by '_build_external_conflict_lines' against
	# already-active DB schedules - populated once, leaving 'internal_conflicts'.
	external_conflict_line_ids = fields.One2many(string="Existing schedule conflicts", comodel_name="ems.working_schedules_import_wizard.external_conflict_line", inverse_name="wizard_id")
	# NOTE: both are pure informational previews/recaps of what Import will actually do (screen 4
	# and "Overall summary" - see 'action_continue' - purely read-only, no resolution needed unlike
	# every other screen's own line model) - a plain Html field is enough, no dedicated line
	# model/security entry needed for content that's never edited. Built leaving 'teachers'
	# ('pending_teachers_html', screen 4) and 'db_conflicts' ('overall_summary_html', "Overall
	# summary") respectively - see '_teacher_preview_html'/'_summary_blocks_html'.
	pending_teachers_html = fields.Html(readonly=True)
	# NOTE: 'overall_summary_html' is one field holding every category's own block (unresolved
	# groups/teachers, pending teachers, both conflict kinds, existing teachers affected) - there
	# used to be a separate 'existing_teachers_html' field just for the last category, but folding
	# it into its own block here (2026-08-10, developer feedback: "quiero saber cómo [se resolvió],
	# no solo cuántos") made a standalone field for that one category alone redundant on this same
	# screen - removed rather than kept alongside as a duplicate of the same content.
	overall_summary_html = fields.Html(readonly=True)
	# NOTE: drives whether "Continue" renders enabled or disabled (developer feedback 2026-08-05:
	# "que quedará mas claro si los botones de continuar... aparecen como enabled o disabled" rather
	# than appearing/disappearing) - the view keeps the button in the SAME place either way (two
	# stacked buttons, only one visible at a time: the real actionable one, or a cosmetic
	# 'disabled="disabled"' twin with no 'name' - see import_wizard.xml), instead of hiding it
	# outright the way 'summary' still does for a wholly different screen's button.
	continue_disabled = fields.Boolean(compute="_compute_continue_disabled")

	@api.depends(
		"state", "ready_to_import", "group_line_ids.group_id", "teacher_line_ids.employee_id",
		"teacher_line_ids.create_new", "internal_conflict_line_ids.resolution",
		"internal_conflict_line_ids.left_space_id", "internal_conflict_line_ids.right_space_id",
		"external_conflict_line_ids.resolution", "external_conflict_line_ids.left_space_id",
		"external_conflict_line_ids.right_space_id",
	)
	def _compute_continue_disabled(self):
		for wizard in self:
			if wizard.state == 'intro':
				wizard.continue_disabled = not wizard.ready_to_import
			elif wizard.state == 'groups':
				wizard.continue_disabled = bool(wizard.group_line_ids.filtered(lambda line: not line.group_id))
			elif wizard.state == 'teachers':
				wizard.continue_disabled = bool(wizard.teacher_line_ids.filtered(lambda line: not line.employee_id and not line.create_new))
			elif wizard.state == 'internal_conflicts':
				wizard.continue_disabled = bool(wizard.internal_conflict_line_ids.filtered(lambda line: not line._resolution_is_valid()))
			elif wizard.state == 'db_conflicts':
				wizard.continue_disabled = bool(wizard.external_conflict_line_ids.filtered(lambda line: not line._resolution_is_valid()))
			else:
				wizard.continue_disabled = False

	_STATE_SEQUENCE = ['intro', 'groups', 'teachers', 'pending_info', 'internal_conflicts', 'db_conflicts', 'summary']

	@staticmethod
	def _is_email_like(value):
		"""True for a real e-mail address; False for a schedule-import placeholder code (e.g. 'X1') —
		the only thing that distinguishes the two in the planner XML."""
		return "@" in (value or "")

	@classmethod
	def _teacher_identifier(cls, name_attr):
		"""The value that identifies a <TeacherNode>'s 'name' attribute for lookup/creation: the real
		e-mail if one appears anywhere in it (planner rows normally look like '<email> <display
		name>' — only the e-mail itself is ever used, the rest is a discardable label), otherwise the
		ENTIRE (stripped) attribute value. Deliberately NOT 'name_attr.split(' ')[0]': a not-yet-
		identified teacher's node has no code/label split at all — it may be a short placeholder code
		('X1') or the person's own real, multi-word name ('Fulanito Menganito'), and naively taking
		the first whitespace-separated token would silently truncate the latter to just 'Fulanito'."""
		match = cls._EMAIL_RE.search(name_attr or "")
		return match.group(0) if match else (name_attr or "").strip()

	def _conflict_lines(self, conflicts):
		"""One bullet line per ems.attendance_schedule conflict (co-teaching or space), naming the
		other teacher(s), subject and time — shared wording for both the co-teaching banner and the
		space-conflict blocking issue."""
		lines = []
		for conflict in conflicts:
			template = conflict.attendance_template_id
			weekday = dict(conflict.weekdays_selection).get(conflict.weekday)
			lines.append(_("%(teacher)s — %(subject)s (%(weekday)s %(time)s)") % {
				'teacher': ", ".join(template.teacher_ids.mapped('display_name')),
				'subject': template.display_name,
				'weekday': weekday,
				'time': conflict.time_range,
			})
		return lines

	def _space_conflict_lines(self, conflicts):
		return [
			_("Room conflict: this import wants the same space and time as %s.") % line
			for line in self._conflict_lines(conflicts)
		]

	def _self_conflict_lines(self, conflicts):
		"""One line per ems.attendance_template.find_self_conflicts() result - a teacher imported in
		this same batch double-booked against their own, already-existing schedule for a different
		subject/group (e.g. two departments scheduling them at the same time in separate files)."""
		return [
			_("Schedule conflict: this teacher already has an overlapping session, %s.") % line
			for line in self._conflict_lines(conflicts)
		]

	def _groups_without_space(self, teacher_entries):
		"""Every distinct ems.group referenced by a teaching entry (group_ids present — non-teaching
		entries carry none) that has no classroom (space_id) assigned. ems.group.space_id is optional,
		but the room on ems.attendance_template it feeds is required — importing a subject taught to
		such a group fails with Odoo's generic "mandatory field is not set" error instead of naming the
		actual problem, so this is checked upfront to raise/warn with the group(s) at fault instead."""
		group_ids = set()
		for _teacher, entries in teacher_entries:
			for entry in entries:
				group_ids.update(entry.get('group_ids') or [])
		if not group_ids:
			return self.env['ems.group']
		return self.env['ems.group'].browse(group_ids).filtered(lambda group: not group.space_id)

	def _missing_space_lines(self, missing_space):
		"""One bullet line per group missing a classroom — shared by every onchange handler so the
		message is worded identically wherever it appears."""
		return [_("Group '%s' has no classroom assigned.") % group.name for group in missing_space]

	def _classify_attachments(self):
		"""Parses every 'attachment_ids' file (without writing anything), building the raw
		per-teacher-node cache '_continue_from_intro' needs to defer the actual import to the final
		step. Deliberately does NOT resolve teachers, check for missing classrooms, or look for
		schedule conflicts here any more (2026-08-05, developer feedback after actually using this
		screen) - every one of those is deferred all the way to '_apply_import' at the final step
		instead (or to the 'groups' step for an unresolved group name - see 'pending_group_names'
		below), since resolving those problems is exactly what the later steps exist for, not
		something this welcome screen should pre-empt by blocking on them. The one thing that
		genuinely can't be deferred: a node whose own schedule content fails to parse at all (an
		unresolved SUBJECT code, or a genuinely malformed node - inside '_parse_schedule_entries')
		has no entries to cache in the first place - collected in 'unparseable_issues' and still
		blocks leaving this screen, since there is no later step that could resolve it and no data
		to silently carry forward instead."""
		unparseable_issues, node_cache = [], []
		for attachment in self.attachment_ids:
			xml_content = base64.b64decode(attachment.datas)
			tree = ET.ElementTree(ET.fromstring(xml_content))

			for teacherNode in tree.getroot():
				identifier = self._teacher_identifier(teacherNode.attrib['name'])
				try:
					entries, attendance_ids = self._parse_schedule_entries(teacherNode)
				except ValidationError as error:
					unparseable_issues.append(str(error))
					continue
				node_cache.append({'identifier': identifier, 'entries': entries, 'attendance_ids': attendance_ids})

		return {
			'unparseable_issues': unparseable_issues,
			'node_cache': node_cache,
			'pending_group_names': self._pending_group_names(node_cache),
		}

	@staticmethod
	def _pending_group_names(node_cache):
		"""Every distinct raw '<Students>' name left unresolved anywhere in 'node_cache' (see
		'pending_group_names' on an 'entries' item, set by '_parse_schedule_entries') - dedup by raw
		text, so the same typo'd name appearing in many hour-nodes across a file becomes ONE
		correction line on the 'groups' step, not one per occurrence."""
		names = set()
		for item in node_cache:
			for entry in item['entries']:
				names.update(entry.get('pending_group_names') or [])
		return sorted(names)

	def _advance_state(self):
		self.ensure_one()
		self.state = self._STATE_SEQUENCE[self._STATE_SEQUENCE.index(self.state) + 1]

	def _reopen_self_action(self):
		"""Re-opens this exact wizard record, still as a dialog. A 'type=object' button whose
		Python method returns a falsy value (e.g. None, the implicit return of a method with no
		explicit 'return') gets converted client-side into '{'type': 'ir.actions.act_window_close'}'
		(see odoo/addons/web/static/src/webclient/actions/action_service.js's own 'doActionButton') -
		for a wizard opened as 'target: new', that silently closes the dialog the moment its very
		first save happens (found empirically 2026-08-05: the 'Continue' button on the intro screen
		closed the whole wizard on its first click, instead of advancing to the next step). Returning
		this action instead keeps the same dialog open, now showing whatever state was just written."""
		self.ensure_one()
		return {
			'type': 'ir.actions.act_window',
			'res_model': self._name,
			'res_id': self.id,
			'view_mode': 'form',
			'target': 'new',
		}

	def action_continue(self):
		"""The single 'Continue' button's handler for every non-final step - dispatches to each
		step's own logic. 'summary' (the final, non-Continue step) is the only one still a
		placeholder that just advances the statusbar - every other step now has real logic."""
		self.ensure_one()
		if self.state == 'intro':
			self._continue_from_intro()
		elif self.state == 'groups':
			self._continue_from_groups()
		elif self.state == 'teachers':
			self._continue_from_teachers()
		elif self.state == 'internal_conflicts':
			self._continue_from_internal_conflicts()
		elif self.state == 'db_conflicts':
			self._continue_from_db_conflicts()
		elif self.state == 'pending_info':
			self._continue_from_pending_info()
		else:
			self._advance_state()
		return self._reopen_self_action()

	def _continue_from_intro(self):
		"""Parses every attached file (without writing anything yet - see '_classify_attachments'),
		caches the result, and advances to the next step. The 'no course configured'/'no file
		attached' checks stay here (there is no later step that could ever resolve either one), but
		everything about the file's own CONTENT (unresolved teachers, missing classrooms, schedule
		conflicts...) is deferred to '_apply_import' - see that method's own docstring - except an
		unresolved group name, deferred to the 'groups' step instead (see 'group_line_ids' below)."""
		self.ensure_one()
		if not self.env.company.current_course_id.id:
			raise ValidationError(_("No 'current course' has been setup. Please, select or create the current course within the EMS settings section."))
		if not self.attachment_ids:
			raise ValidationError(_("No XML file has been loaded. Please, provide at least one XML file and try again."))
		result = self._classify_attachments()
		if result['unparseable_issues']:
			# NOTE: the actual issues are folded into the message (not a generic "please fix the
			# issues shown above") - this is also reachable from a direct ORM/API call with no
			# banner to look at, e.g. a test bypassing the onchange-then-click UI flow.
			raise ValidationError(_(
				"Please fix the following issues before continuing:\n%s"
			) % "\n".join(result['unparseable_issues']))
		self.parsed_entries_json = json.dumps(result['node_cache'])
		self.group_line_ids = [(5, 0, 0)] + [
			(0, 0, {'raw_name': name}) for name in result['pending_group_names']
		]
		self._advance_state()

	def _continue_from_groups(self):
		"""The 'groups' step's own 'Continue' handler: every 'group_line_ids' row must have a group
		picked (raised, same convention as every other validation in this wizard - the developer's
		own choice, see 'plans/working_schedule_import_redesign.md's step 2), then every occurrence
		of each resolved raw name across the whole cached batch is substituted in place (see
		'_finalize_pending_groups') before advancing - nothing reaches '_apply_import()' with a
		'pending_group_names' marker still attached."""
		self.ensure_one()
		unresolved_lines = self.group_line_ids.filtered(lambda line: not line.group_id)
		if unresolved_lines:
			raise ValidationError(_(
				"Please select a group for every unresolved name before continuing:\n%s"
			) % "\n".join(unresolved_lines.mapped('raw_name')))

		name_to_group = {line.raw_name: line.group_id for line in self.group_line_ids}
		node_cache = json.loads(self.parsed_entries_json or '[]')
		for item in node_cache:
			for entry in item['entries']:
				self._finalize_pending_groups(entry, name_to_group)
			for command in item['attendance_ids']:
				if command[0] == 0:
					self._finalize_pending_groups(command[2], name_to_group)
		self.parsed_entries_json = json.dumps(node_cache)
		self.teacher_line_ids = [(5, 0, 0)] + [
			(0, 0, {'raw_identifier': identifier}) for identifier in self._pending_teacher_identifiers(node_cache)
		]
		self._advance_state()

	def _pending_teacher_identifiers(self, node_cache):
		"""Every distinct e-mail-shaped identifier (see '_is_email_like') in 'node_cache' with no
		matching 'hr.employee.work_email' - a pending-identification CODE (no '@') is never included
		here, it isn't a problem for this screen to resolve (see screen 6, automatic at Import)."""
		identifiers = set()
		for item in node_cache:
			identifier = item['identifier']
			if self._is_email_like(identifier) and not self.env['hr.employee'].search([('work_email', '=', identifier)]):
				identifiers.add(identifier)
		return sorted(identifiers)

	def _classify_teacher_item(self, item):
		"""Classifies a 'node_cache' item's eventual Import-time fate - the single source of truth
		both '_apply_import' (the real write path) and screens 6/7 (pure previews of what Import
		will do) branch on, so the previews can never diverge from what actually happens:
		- 'resolved': an existing 'hr.employee' picked on the 'teachers' step.
		- 'create_pending': 'New' ticked on that same step - a genuinely never-hired teacher.
		- 'email_match': an e-mail that already matched an existing 'hr.employee.work_email' on
		  its own, needing no correction at all.
		- 'placeholder': a bare code/name, never an e-mail - resolved to a pending-identification
		  teacher at Import, same as 'create_pending' but with no manually-attempted e-mail."""
		if item.get('employee_id'):
			return 'resolved'
		elif item.get('create_pending'):
			return 'create_pending'
		elif self._is_email_like(item['identifier']):
			return 'email_match'
		else:
			return 'placeholder'

	def _teacher_preview_line(self, item):
		"""One label for 'item', worded per its own '_classify_teacher_item' fate - shared by
		screens 6 ('create_pending'/'placeholder') and 7 ('resolved'/'email_match')."""
		identifier = item['identifier']
		fate = self._classify_teacher_item(item)
		if fate == 'create_pending':
			return _("Pending teacher (%s) - the e-mail will be pre-filled as an attempt, not auto-generated") % identifier
		elif fate == 'placeholder':
			return _("Pending teacher (%s)") % identifier
		teacher = (
			self.env['hr.employee'].browse(item['employee_id']) if fate == 'resolved'
			else self.env['hr.employee'].search([('work_email', '=', identifier)], limit=1)
		)
		return _("%(teacher)s (file identifier: %(identifier)s)") % {'teacher': teacher.display_name, 'identifier': identifier}

	def _teacher_preview_items(self, node_cache, fates):
		"""Every 'node_cache' item whose fate is in 'fates', deduped by identifier - the same
		dedup every other resolution screen in this wizard already applies (the same teacher
		mentioned in several files/hour-nodes is one line, not one per occurrence). Shared by
		'_teacher_preview_html' (screens 6-7's own bullet lists) and the "Overall summary" screen's
		own counts, so a count and its matching list can never disagree."""
		seen = set()
		items = []
		for item in node_cache:
			identifier = item['identifier']
			if identifier in seen or self._classify_teacher_item(item) not in fates:
				continue
			seen.add(identifier)
			items.append(item)
		return items

	def _teacher_preview_html(self, node_cache, fates):
		lines = [self._teacher_preview_line(item) for item in self._teacher_preview_items(node_cache, fates)]
		return self._bullet_html(lines)

	def _bullet_html(self, lines):
		"""Wraps 'lines' (already-translated strings) into the same up-to-3-column bullet list
		('ems_wizard_bullet_list') every informational screen in this wizard uses - 'Markup.format'
		auto-escapes each line, same safety property as 'ems.base.build_html_list' (not inherited
		here - this is a TransientModel wizard, pulling in mail.thread/mail.activity.mixin just for
		this one helper would be a heavier dependency than the helper itself)."""
		if not lines:
			return Markup("")
		return Markup('<ul class="ems_wizard_bullet_list">{}</ul>').format(
			Markup("").join(Markup("<li>{}</li>").format(line) for line in lines)
		)

	def _selection_label(self, record, field_name):
		"""Translated label for one Selection field value on 'record' (a single-record recordset) -
		'convert_to_export' is the ORM's own idiomatic way to resolve a Selection value to its
		current-language label (it delegates to '_description_selection', which consults the
		translated 'ir.model.fields.selection' rows) - NOT the field's raw '.selection' attribute,
		which is always the untranslated English list passed at field-definition time."""
		field = record._fields[field_name]
		return field.convert_to_export(record[field_name], record)

	def _conflict_detail_line(self, line):
		"""One human-readable line for an already-resolved 'conflict_mixin' line ('internal_
		conflict_line'/'external_conflict_line' both share this shape) - shown on the "Overall
		summary" screen's own file/db conflict blocks, so the admin sees not just how many conflicts
		were resolved but how each one was."""
		detail = _("%(left)s vs. %(right)s --> %(kind)s: resolved as %(resolution)s") % {
			'left': line.left_label,
			'right': line.right_label,
			'kind': self._selection_label(line, 'kind'),
			'resolution': self._selection_label(line, 'resolution'),
		}
		if line.resolution == 'reassign_rooms':
			detail += _(" - rooms: %(left_space)s / %(right_space)s") % {
				'left_space': line.left_space_id.display_name,
				'right_space': line.right_space_id.display_name,
			}
		return detail

	def _summary_block_html(self, title, lines, note=None):
		"""One card for the "Overall summary" screen: a bold count-sentence header (e.g. "1
		unresolved group name(s) resolved"), and its own concrete detail lines below it - so a count
		and its "how" are visually grouped instead of one flat list mixing every category together
		(developer feedback 2026-08-10: "si se ha resuelto 1 grupo, quiero saber cómo"). Reuses
		Bootstrap's own 'card' classes (already bundled, no bespoke CSS needed) rather than a custom
		block style - matches this repo's "Odoo way first" rule. Full-width (no 'flex: 1 1 ...'
		sizing) - see '_summary_blocks_html' for why one-per-row replaced the original side-by-side
		layout. 'note' is an optional short explanation shown once above the detail lines (only when
		there are any - an empty block has nothing to explain) - added for the "existing teacher(s)
		affected" block, whose own count/names alone didn't say what "affected" actually means for
		them (developer feedback 2026-08-10: "deberíamos aclarar cómo se verán afectados")."""
		parts = []
		if note and lines:
			parts.append(Markup('<p class="text-muted mb-2">{}</p>').format(note))
		if lines:
			parts.append(Markup('<ul class="mb-0 ps-3">{}</ul>').format(
				Markup("").join(Markup("<li>{}</li>").format(line) for line in lines)
			))
		else:
			parts.append(Markup('<span class="text-muted">{}</span>').format(_("Nothing to show here.")))
		return Markup(
			'<div class="card">'
			'<div class="card-header"><strong>{}</strong></div>'
			'<div class="card-body">{}</div>'
			'</div>'
		).format(title, Markup("").join(parts))

	def _summary_blocks_html(self, blocks):
		"""Lays every '_summary_block_html' card out as a vertical stack, one full-width card per
		row (Bootstrap's own 'd-flex flex-column gap-*' utilities - no bespoke CSS needed).
		Originally a wrapping horizontal row (several cards per line) - changed the same day
		(developer feedback, after seeing it rendered for real: "La primera fila tiene 4 tarjetas y
		se ven muy apretadas... vamos a poner una tarjeta por fila") once 6 cards side by side at
		the dialog's actual width turned out too cramped to read comfortably."""
		return Markup('<div class="d-flex flex-column gap-3 mb-3">{}</div>').format(
			Markup("").join(blocks)
		)

	def _continue_from_teachers(self):
		"""The 'teachers' step's own 'Continue' handler, mirroring '_continue_from_groups': every
		'teacher_line_ids' row must have EITHER a teacher picked OR 'create_new' ticked (raised
		otherwise), then every 'node_cache' item sharing that row's raw identifier gets an
		'employee_id' or 'create_pending' key written onto it directly (the identifier is the
		item's own top-level field, not part of 'entries'/'attendance_ids' like a group reference -
		no '_finalize_pending_groups'-style dict-shape juggling needed). Every teacher's eventual
		fate is fully determined right here - conflict resolution (the next two screens) only ever
		touches 'entries'/'attendance_ids'/'space_id', never 'employee_id'/'create_pending' - which
		is exactly why 'pending_info' (screen 6) moved to sit immediately after this step (2026-08-10,
		developer feedback) rather than after conflict resolution: nothing about it depends on
		conflicts being resolved first."""
		self.ensure_one()
		unresolved_lines = self.teacher_line_ids.filtered(lambda line: not line.employee_id and not line.create_new)
		if unresolved_lines:
			raise ValidationError(_(
				"Please select a teacher for every unresolved e-mail before continuing:\n%s"
			) % "\n".join(unresolved_lines.mapped('raw_identifier')))

		identifier_to_employee = {line.raw_identifier: line.employee_id for line in self.teacher_line_ids if line.employee_id}
		identifiers_to_create = {line.raw_identifier for line in self.teacher_line_ids if line.create_new}
		node_cache = json.loads(self.parsed_entries_json or '[]')
		for item in node_cache:
			if item['identifier'] in identifiers_to_create:
				item['create_pending'] = True
			else:
				employee = identifier_to_employee.get(item['identifier'])
				if employee:
					item['employee_id'] = employee.id
		self.parsed_entries_json = json.dumps(node_cache)
		self.pending_teachers_html = self._teacher_preview_html(node_cache, ('create_pending', 'placeholder'))
		self._advance_state()

	@staticmethod
	def _format_hour(value):
		hour, minutes = divmod(round(value * 60), 60)
		return "%02d:%02d" % (hour, minutes)

	def _entry_default_space_id(self, entry):
		"""The classroom an entry would use absent any explicit override - the SAME "first group
		wins" convention already used throughout this file (e.g. 'ems_working_schedule_assignation.
		create()'). A non-teaching entry, or one whose group has no classroom, has none - callers
		skip it (that gap is caught elsewhere, see '_groups_without_space')."""
		group_ids = entry.get('group_ids')
		if not group_ids:
			return False
		return self.env['ems.group'].browse(group_ids[0]).space_id.id

	@staticmethod
	def _classify_conflict_kind(entry_a, entry_b):
		"""Shared classification (see plans/working_schedule_import_redesign.md's "Conflict kind
		classification", also meant for screen 5's not-yet-built external conflicts)."""
		if entry_a['subject_id'] != entry_b['subject_id']:
			return 'plain_conflict'
		if set(entry_a.get('group_ids') or []) & set(entry_b.get('group_ids') or []):
			return 'co_teaching_eligible'
		return 'desdoble_eligible'

	def _teacher_label_for_item(self, item):
		"""Best-effort display name for a node_cache item's teacher - already-resolved by this
		point (either it always matched, or screen 3 attached an 'employee_id') for any real e-mail;
		a pending-identification code has no employee yet, so it's shown as-is (e.g. 'X1')."""
		if item.get('employee_id'):
			return self.env['hr.employee'].browse(item['employee_id']).display_name
		identifier = item['identifier']
		if self._is_email_like(identifier):
			employee = self.env['hr.employee'].search([('work_email', '=', identifier)], limit=1)
			if employee:
				return employee.display_name
		return identifier

	def _entry_label(self, item, entry):
		groups = ", ".join(self.env['ems.group'].browse(entry.get('group_ids') or []).mapped('display_name'))
		weekday = dict(self.env['ems.attendance_schedule'].weekdays_selection).get(entry['dayofweek'])
		time_range = "%s-%s" % (self._format_hour(entry['hour_from']), self._format_hour(entry['hour_to']))
		return _("%(teacher)s — %(subject)s (%(groups)s, %(weekday)s %(time)s)") % {
			'teacher': self._teacher_label_for_item(item),
			'subject': entry.get('name') or '',
			'groups': groups,
			'weekday': weekday,
			'time': time_range,
		}

	def _find_internal_conflicts(self, node_cache):
		"""Every pair of TEACHING entries from DIFFERENT node_cache items that collide on the same
		classroom + weekday + time - a genuinely new check (see plans/
		working_schedule_import_redesign.md's step 4). Non-teaching entries carry no classroom, so
		are excluded; a slot with 3+ colliding entries produces multiple pairwise pairs rather than
		one n-way one (documented simplification, not expected to matter in practice). Returns a list
		of (item_index_a, entry_index_a, item_index_b, entry_index_b) tuples."""
		by_slot = {}
		for item_index, item in enumerate(node_cache):
			for entry_index, entry in enumerate(item['entries']):
				if entry.get('non_teaching'):
					continue
				space_id = self._entry_default_space_id(entry)
				if not space_id:
					continue
				slot_key = (space_id, entry['dayofweek'], entry['hour_from'], entry['hour_to'])
				by_slot.setdefault(slot_key, []).append((item_index, entry_index))

		pairs = []
		for slot_refs in by_slot.values():
			for i in range(len(slot_refs)):
				for j in range(i + 1, len(slot_refs)):
					item_index_a, entry_index_a = slot_refs[i]
					item_index_b, entry_index_b = slot_refs[j]
					if item_index_a == item_index_b:
						continue  # the same teacher can't conflict with their own entry here
					pairs.append((item_index_a, entry_index_a, item_index_b, entry_index_b))
		return pairs

	# NOTE: 'plain_conflict' defaults to 'prevail_left' here - only correct for a genuine
	# self-time-only conflict (different rooms, same teacher double-booked in time - reassigning
	# rooms fixes nothing there). A genuine same-room clash overrides this to 'reassign_rooms'
	# explicitly at the call site instead (see '_build_internal_conflict_lines'/
	# '_build_external_conflict_lines' - internal conflicts are ALWAYS a same-room clash by
	# construction, so they always override; external ones only override when the candidate's own
	# room actually matches).
	_RESOLUTION_DEFAULTS = {
		'co_teaching_eligible': 'co_teaching',
		'desdoble_eligible': 'reassign_rooms',
		'plain_conflict': 'prevail_left',
	}

	def _build_internal_conflict_lines(self, node_cache):
		"""(0, 0, {...}) create-commands for 'internal_conflict_line_ids', one per pair found by
		'_find_internal_conflicts'. Positional references (item/entry indices), not content
		matching - built once here, from the very 'node_cache' '_continue_from_internal_conflicts'
		re-reads unchanged, so they stay valid. Unlike screen 5's own external conflicts, EVERY
		'plain_conflict' pair found here is a genuine same-room clash - '_find_internal_conflicts'
		only ever pairs entries that already matched on 'space_id' - so it always overrides
		'_RESOLUTION_DEFAULTS' to 'reassign_rooms' (developer feedback 2026-08-05: picking a room is
		the actual fix for a real room conflict, not an afterthought behind
		'prevail_left'/'prevail_right'), with 'left_space_id'/'right_space_id' pre-filled with the
		colliding room (the group's own currently-assigned classroom - the same value on both sides,
		since that's exactly why they collided in the first place) so they're ready the moment
		'reassign_rooms' is picked."""
		commands = []
		for item_index_a, entry_index_a, item_index_b, entry_index_b in self._find_internal_conflicts(node_cache):
			entry_a = node_cache[item_index_a]['entries'][entry_index_a]
			entry_b = node_cache[item_index_b]['entries'][entry_index_b]
			kind = self._classify_conflict_kind(entry_a, entry_b)
			same_room_conflict = kind in ('desdoble_eligible', 'plain_conflict')
			vals = {
				'kind': kind,
				'resolution': 'reassign_rooms' if same_room_conflict else self._RESOLUTION_DEFAULTS[kind],
				'left_item_index': item_index_a,
				'left_entry_index': entry_index_a,
				'left_label': self._entry_label(node_cache[item_index_a], entry_a),
				'right_item_index': item_index_b,
				'right_entry_index': entry_index_b,
				'right_label': self._entry_label(node_cache[item_index_b], entry_b),
			}
			if same_room_conflict:
				space_id = self._entry_default_space_id(entry_a)
				vals['left_space_id'] = space_id
				vals['right_space_id'] = space_id
			commands.append((0, 0, vals))
		return commands

	def _continue_from_internal_conflicts(self):
		"""The 'internal_conflicts' step's own 'Continue' handler: every line's 'resolution' must be
		valid for its own 'kind' (raised otherwise, naming the offending pairs), then every line's
		pick is applied to a freshly re-read 'node_cache' - 'co_teaching' is a no-op (the existing
		'_reconcile_fresh_import' auto-merge already handles it), 'prevail_left'/'prevail_right'
		deletes the losing side's one specific entry (never the whole item), 'reassign_rooms' writes
		'space_id' onto both sides. Deletions across every line are collected first (grouped by item)
		and applied in reverse-index order per item only once every room write has happened, so one
		line's deletion can never shift another still-unprocessed line's stored index within the same
		item (only relevant for the rare 3+-way collision case - see '_find_internal_conflicts')."""
		self.ensure_one()
		invalid_lines = self.internal_conflict_line_ids.filtered(lambda line: not line._resolution_is_valid())
		if invalid_lines:
			raise ValidationError(_(
				"Please choose a valid resolution for every conflict before continuing:\n%s"
			) % "\n".join(
				_("%(left)s vs. %(right)s") % {'left': line.left_label, 'right': line.right_label}
				for line in invalid_lines
			))

		node_cache = json.loads(self.parsed_entries_json or '[]')
		indices_to_remove = {}
		for line in self.internal_conflict_line_ids:
			if line.resolution == 'prevail_left':
				indices_to_remove.setdefault(line.right_item_index, set()).add(line.right_entry_index)
			elif line.resolution == 'prevail_right':
				indices_to_remove.setdefault(line.left_item_index, set()).add(line.left_entry_index)
			elif line.resolution == 'reassign_rooms':
				for item_index, entry_index, space_id in (
					(line.left_item_index, line.left_entry_index, line.left_space_id.id),
					(line.right_item_index, line.right_entry_index, line.right_space_id.id),
				):
					node_cache[item_index]['entries'][entry_index]['space_id'] = space_id
					node_cache[item_index]['attendance_ids'][entry_index + 1][2]['space_id'] = space_id

		for item_index, entry_indices in indices_to_remove.items():
			for entry_index in sorted(entry_indices, reverse=True):
				del node_cache[item_index]['entries'][entry_index]
				del node_cache[item_index]['attendance_ids'][entry_index + 1]

		self.parsed_entries_json = json.dumps(node_cache)
		self.external_conflict_line_ids = [(5, 0, 0)] + self._build_external_conflict_lines(node_cache)
		self._advance_state()

	def _resolve_teacher_for_classification(self, item):
		"""Read-only counterpart to '_apply_import's per-item teacher resolution - never creates a
		pending teacher (unlike '_apply_import' itself), since this is only used to build the
		'db_conflicts' screen's own conflict lines, well before Import actually writes anything. An
		item whose teacher doesn't exist yet (a not-yet-created placeholder code) resolves to an
		empty recordset - harmless for classification, since nothing in the DB could possibly
		reference a teacher that doesn't exist yet."""
		if item.get('employee_id'):
			return self.env['hr.employee'].browse(item['employee_id'])
		identifier = item['identifier']
		if self._is_email_like(identifier):
			return self.env['hr.employee'].search([('work_email', '=', identifier)], limit=1)
		return self.env['hr.employee'].search([('schedule_import_code', '=', identifier)], limit=1)

	def _external_conflict_label(self, candidate):
		weekday = dict(candidate.weekdays_selection).get(candidate.weekday)
		return _("%(teacher)s — %(subject)s (%(groups)s, %(weekday)s %(time)s)") % {
			'teacher': ", ".join(candidate.attendance_template_id.teacher_ids.mapped('display_name')),
			'subject': candidate.attendance_template_id.subject_id.display_name,
			'groups': ", ".join(candidate.attendance_template_id.group_ids.mapped('display_name')),
			'weekday': weekday,
			'time': candidate.time_range,
		}

	def _find_external_conflicts(self, node_cache):
		"""Every (item_index, entry_index, candidate) triple where 'candidate' is an already-active
		'ems.attendance_schedule' colliding with that entry - either EXTERNAL (same classroom +
		weekday + time-overlap, held by a teacher not in this batch at all) or SELF (the entry's own
		resolved teacher already has an active session overlapping in weekday/time, for a genuinely
		different (subject, group) combo - resubmitting the SAME combo is handled by the normal sync
		refresh, not a conflict to show here).

		Deliberately reimplements the two searches here rather than reusing
		'classify_external_conflicts'/'find_self_conflicts' as black boxes (the same methods
		'_apply_import' itself still uses, unchanged, as its own safety net): those methods only
		ever return the AGGREGATE colliding recordset, by design (their original callers only need a
		yes/no blocking check) - critically, 'find_self_conflicts' matches purely on
		weekday/time-overlap with NO room restriction at all (the same teacher physically can't be
		in two rooms at once, regardless of which rooms), so trying to re-derive the pairing
		afterward by matching on room (as screen 4's own within-batch detection safely can, since
		every one of ITS candidates was already room-matched by construction) would silently miss
		every genuine self-conflict whose colliding room differs from the new entry's own - found
		while building this exact method, not guessed at.

		Same pairwise-only simplification as '_find_internal_conflicts': if the same existing
		record would collide with more than one new entry, only the first one found becomes a
		line."""
		batch_teacher_ids = {
			teacher.id for teacher in (self._resolve_teacher_for_classification(item) for item in node_cache) if teacher
		}
		results = []
		seen_schedule_ids = set()
		for item_index, item in enumerate(node_cache):
			teacher = self._resolve_teacher_for_classification(item)
			for entry_index, entry in enumerate(item['entries']):
				if entry.get('non_teaching') or not entry.get('group_ids'):
					continue
				entry_combo = (entry['subject_id'], tuple(sorted(entry['group_ids'])))

				space_id = self._entry_default_space_id(entry)
				external_candidates = self.env['ems.attendance_schedule']
				if space_id:
					external_candidates = self.env['ems.attendance_schedule'].search([
						('weekday', '=', entry['dayofweek']),
						('space_id', '=', space_id),
						('attendance_template_id.teacher_ids', 'not in', list(batch_teacher_ids)),
					]).filtered(lambda c, entry=entry: c.ranges_overlap(c.start_time, c.end_time, entry['hour_from'], entry['hour_to']))

				self_candidates = self.env['ems.attendance_schedule']
				if teacher:
					self_candidates = self.env['ems.attendance_schedule'].search([
						('weekday', '=', entry['dayofweek']),
						('attendance_template_id.teacher_ids', 'in', teacher.id),
					]).filtered(lambda c, entry=entry: c.ranges_overlap(c.start_time, c.end_time, entry['hour_from'], entry['hour_to']))
					self_candidates = self_candidates.filtered(lambda c: (
						c.attendance_template_id.subject_id.id, tuple(sorted(c.attendance_template_id.group_ids.ids)),
					) != entry_combo)

				for candidate in external_candidates | self_candidates:
					if candidate.id in seen_schedule_ids:
						continue
					seen_schedule_ids.add(candidate.id)
					results.append((item_index, entry_index, candidate))
		return results

	def _build_external_conflict_lines(self, node_cache):
		"""(0, 0, {...}) create-commands for 'external_conflict_line_ids', one per triple found by
		'_find_external_conflicts'. A 'plain_conflict' triple here can come from either of that
		method's two searches: a genuine same-room clash ('external_candidates', room-matched by
		construction) - defaults to 'reassign_rooms' like screen 4's own plain conflicts, same
		reasoning; or a SELF conflict ('self_candidates', matched purely on the teacher's own
		weekday/time overlap, no room involved at all) - reassigning rooms fixes nothing there (the
		same teacher still can't be in two places at once regardless of which rooms are picked), so
		that sub-case keeps the older 'prevail_left' default and no room pre-fill, exactly as before
		this default changed for the genuine-room-clash case."""
		commands = []
		for item_index, entry_index, candidate in self._find_external_conflicts(node_cache):
			entry = node_cache[item_index]['entries'][entry_index]
			candidate_entry = {
				'subject_id': candidate.attendance_template_id.subject_id.id,
				'group_ids': candidate.attendance_template_id.group_ids.ids,
			}
			kind = self._classify_conflict_kind(entry, candidate_entry)
			space_id = self._entry_default_space_id(entry)
			same_room_conflict = kind == 'plain_conflict' and candidate.space_id.id == space_id
			vals = {
				'kind': kind,
				'resolution': 'reassign_rooms' if same_room_conflict else self._RESOLUTION_DEFAULTS[kind],
				'left_item_index': item_index,
				'left_entry_index': entry_index,
				'left_label': self._entry_label(node_cache[item_index], entry),
				'right_schedule_id': candidate.id,
				'right_label': self._external_conflict_label(candidate),
			}
			if kind == 'desdoble_eligible' or same_room_conflict:
				vals['left_space_id'] = space_id
				vals['right_space_id'] = space_id
			commands.append((0, 0, vals))
		return commands

	def _continue_from_db_conflicts(self):
		"""The 'db_conflicts' step's own 'Continue' handler - mirrors '_continue_from_internal_
		conflicts' exactly on the left (new-entry) side, but the right side is a real, already-
		persisted 'ems.attendance_schedule' record instead of another node_cache position:
		'prevail_left' archives it outright (always allowed regardless of 'has_sessions' - only
		in-place field edits on a line with real history are locked), 'reassign_rooms' writes its
		new room through the shared 'ems.attendance_mixin._write_or_new_version()' (archives and
		clones with the new room if it already has sessions, plain write otherwise) rather than a
		raw 'write()' - the one piece of forward-planning from an earlier session that made this
		screen's own Green phase smaller than screen 4's. Also builds the "Overall summary" step's
		own content before advancing - one block per category, each with its own count header AND
		concrete detail lines (see '_summary_block_html') - the last screen before Import, so this
		is the last point anything needs precomputing."""
		self.ensure_one()
		invalid_lines = self.external_conflict_line_ids.filtered(lambda line: not line._resolution_is_valid())
		if invalid_lines:
			raise ValidationError(_(
				"Please choose a valid resolution for every conflict before continuing:\n%s"
			) % "\n".join(
				_("%(left)s vs. %(right)s") % {'left': line.left_label, 'right': line.right_label}
				for line in invalid_lines
			))

		node_cache = json.loads(self.parsed_entries_json or '[]')
		indices_to_remove = {}
		for line in self.external_conflict_line_ids:
			if line.resolution == 'prevail_left':
				# NOTE: "archives/trims the existing DB session's template" (the plan's own words)
				# - archiving just this one line is enough to free the slot ("trims"), but if that
				# was the template's only active line, the now-empty template is archived outright
				# too ("archives") rather than left as an orphaned, lineless record.
				template = line.right_schedule_id.attendance_template_id
				line.right_schedule_id.action_archive()
				if not template.attendance_schedule_ids:
					template.action_archive()
			elif line.resolution == 'prevail_right':
				indices_to_remove.setdefault(line.left_item_index, set()).add(line.left_entry_index)
			elif line.resolution == 'reassign_rooms':
				node_cache[line.left_item_index]['entries'][line.left_entry_index]['space_id'] = line.left_space_id.id
				node_cache[line.left_item_index]['attendance_ids'][line.left_entry_index + 1][2]['space_id'] = line.left_space_id.id
				if line.right_schedule_id.space_id != line.right_space_id:
					line.right_schedule_id._write_or_new_version({'space_id': line.right_space_id.id})

		for item_index, entry_indices in indices_to_remove.items():
			for entry_index in sorted(entry_indices, reverse=True):
				del node_cache[item_index]['entries'][entry_index]
				del node_cache[item_index]['attendance_ids'][entry_index + 1]

		self.parsed_entries_json = json.dumps(node_cache)
		existing_items = self._teacher_preview_items(node_cache, ('resolved', 'email_match'))
		pending_items = self._teacher_preview_items(node_cache, ('create_pending', 'placeholder'))
		group_lines = [
			_("%(raw)s resolved to %(group)s") % {'raw': line.raw_name, 'group': line.group_id.display_name}
			for line in self.group_line_ids
		]
		teacher_lines = [
			_("%(raw)s will be created as a new pending teacher") % {'raw': line.raw_identifier}
			if line.create_new else
			_("%(raw)s resolved to %(teacher)s") % {'raw': line.raw_identifier, 'teacher': line.employee_id.display_name}
			for line in self.teacher_line_ids
		]
		self.overall_summary_html = self._summary_blocks_html([
			self._summary_block_html(
				_("%s unresolved group name(s) resolved") % len(self.group_line_ids), group_lines),
			self._summary_block_html(
				_("%s unresolved teacher e-mail(s) resolved") % len(self.teacher_line_ids), teacher_lines),
			self._summary_block_html(
				_("%s pending teacher(s) will be created") % len(pending_items),
				[self._teacher_preview_line(item) for item in pending_items],
				note=_(
					"These are placeholder employees, created now so their schedule and subjects "
					"are ready immediately. Afterwards, open each one's own record to replace the "
					"placeholder name with the real one, fill in their personal e-mail, and click "
					"Generate Google account - exactly like any other new teacher."
				)),
			self._summary_block_html(
				_("%s file conflict(s) resolved") % len(self.internal_conflict_line_ids),
				[self._conflict_detail_line(line) for line in self.internal_conflict_line_ids]),
			self._summary_block_html(
				_("%s existing schedule conflict(s) resolved") % len(self.external_conflict_line_ids),
				[self._conflict_detail_line(line) for line in self.external_conflict_line_ids]),
			self._summary_block_html(
				_("%s existing teacher(s) affected") % len(existing_items),
				[self._teacher_preview_line(item) for item in existing_items],
				note=_(
					"Their weekly schedule will be synced with this file's content. Each affected "
					"attendance template is updated in place if it has no real attendance history "
					"yet, or archived and replaced by a new version if it does - the original's "
					"history is never lost."
				)),
		])
		self._advance_state()

	def _continue_from_pending_info(self):
		"""The 'pending_info' step's own 'Continue' handler - purely informational (see screen 6's
		own docstring above), nothing to validate or write back to 'node_cache', just builds the
		next screen's own data ('internal_conflict_line_ids', screen 4) before advancing - same
		"build the next screen's content here" convention every other step in this wizard follows."""
		self.ensure_one()
		node_cache = json.loads(self.parsed_entries_json or '[]')
		self.internal_conflict_line_ids = [(5, 0, 0)] + self._build_internal_conflict_lines(node_cache)
		self._advance_state()

	def _get_or_create_pending_teacher(self, identifier, manual_email=False):
		"""Get-or-create-by-'schedule_import_code' shared by both not-yet-identified-teacher paths:
		a placeholder code (e.g. 'X1', 'manual_email=False') and a 'create_new'-ticked e-mail that
		genuinely doesn't match any existing teacher ('manual_email=True' - see 'teacher_line.
		create_new'). Re-importing an updated file before this teacher's real identity is resolved
		reuses the SAME record either way, never creating a duplicate - 'identifier' is exactly what
		a re-import would search for again next time.

		'manual_email=True' additionally pre-fills 'work_email' with 'identifier' itself and sets
		'google_ws_manual_email' (the existing Google Workspace integration field - already means
		"edit Work Email by hand instead of letting EMS generate it") - the developer's own framing
		for this case: *"esa dirección de correo no se puede dar por buena... pero me gustaría
		intentarlo"* - worth trying, but never silently treated as confirmed/auto-generated the way
		a normal corporate email would be."""
		teacher = self.env["hr.employee"].search([("schedule_import_code", "=", identifier)])
		if teacher.id:
			return teacher
		vals = {
			"name": _("Pending teacher (%s)") % identifier,
			"employee_type": "teacher",
			"schedule_import_code": identifier,
		}
		if manual_email:
			vals["work_email"] = identifier
			vals["google_ws_manual_email"] = True
		return self.env["hr.employee"].create(vals)

	def _write_teacher_schedule(self, teacher, attendance_ids):
		"""Writes 'attendance_ids' (already-parsed (0, 0, {...}) commands - see
		'_parse_schedule_entries') onto 'teacher's CURRENT resource.calendar. Never searches by name
		or creates a calendar itself (2026-08-06, see
		plans/course_transition_teacher_schedule_archival.md decision 5) - every teacher already has
		one, auto-created at 'employee.create()' time (see 'ems_employee'), and rolling it onto a
		fresh one for a new course is the transition wizard's own job now
		('_apply_calendar_rollover'), not the importer's."""
		teacher.resource_calendar_id.write({'attendance_ids': attendance_ids})

	def _apply_import(self, node_cache):
		"""Writes everything (resource.calendar/ems.teaching per teacher, then the
		ems.attendance_template batch sync) from the raw per-node cache '_continue_from_intro' built -
		deferred until this final step so nothing is written before the whole wizard flow completes.
		Mirrors this model's former create() override, adapted to work from the cache instead of
		re-parsing the XML from scratch (which would also re-resolve teachers/pending-codes against
		data this same call is about to change)."""
		# NOTE: attendance_template sync is deferred and batched across every teacher (see
		# sync_from_schedule_batch_fresh_import) — syncing one teacher at a time here would let an
		# early teacher's fresh schedule line falsely collide with a later teacher's still-stale one
		# whenever they share a classroom, since the later teacher hasn't been re-synced yet.
		teacher_entries = []
		for item in node_cache:
			identifier = item['identifier']
			fate = self._classify_teacher_item(item)
			if fate == 'resolved':
				# NOTE: resolved on the 'teachers' step (see '_continue_from_teachers') - an
				# identifier that never needed a correction line (already matched 'work_email' on
				# its own) falls through to the 'email_match' branch below instead, unaffected.
				teacher = self.env["hr.employee"].browse(item['employee_id'])
			elif fate == 'create_pending':
				# NOTE: 'create_new' ticked on the 'teachers' step (see '_continue_from_teachers') -
				# a genuinely never-hired teacher, not a typo/mismatch of an existing one. Reuses the
				# exact same get-or-create mechanism as a placeholder code, only adding
				# 'manual_email=True' - see '_get_or_create_pending_teacher's own docstring.
				teacher = self._get_or_create_pending_teacher(identifier, manual_email=True)
			elif fate == 'email_match':
				teacher = self.env["hr.employee"].search([("work_email", "=", identifier)])
				if not teacher.id:
					# NOTE: safety net for a direct ORM/API caller bypassing the wizard's own
					# step-by-step UI - a real user reaching Import through the wizard already had
					# every unresolved e-mail turned into a 'teacher_line' at the 'teachers' step.
					raise ValidationError(_("Teacher with email '%s' not found.") % identifier)
			else:
				teacher = self._get_or_create_pending_teacher(identifier)

			self._write_teacher_schedule(teacher, item['attendance_ids'])
			entries = [e for e in item['entries'] if not e["non_teaching"]]
			# NOTE: replace=False - this file only ever describes ONE SLICE of the centre's
			# schedule (e.g. one department), never a teacher's ENTIRE teaching load, so a
			# combo from a DIFFERENT, already-imported file must never be unlinked just
			# because this teacher also appears here (see sync_from_schedule's own docstring).
			self.env['ems.teaching'].sync_from_schedule(teacher, entries, replace=False)
			teacher_entries.append((teacher, entries))

		# NOTE: ems.attendance_template.space_id is required, but ems.group.space_id (where it's
		# taken from) is not — a group missing a classroom would otherwise fail with Odoo's generic
		# "mandatory field is not set" error instead of naming the actual problem.
		missing_space = self._groups_without_space(teacher_entries)
		if missing_space:
			raise ValidationError(_(
				"These groups have no classroom assigned, so their schedule cannot be imported: %s"
			) % ", ".join(missing_space.mapped('name')))

		# NOTE: a batch import never writes on top of an already-populated schedule for its own
		# scope (groups are reused across academic years, but their attendance templates are
		# archived by the course transition wizard first - see
		# docs/en/developers/employees/working_schedule.md), so an external overlap found here is
		# always either legitimate co-teaching (left alone - sync_from_schedule_batch's own
		# reconciliation folds the new teacher into the same shared template) or a genuine problem
		# the onchange preview should already have caught. Raising here too (not just previewing)
		# is the safety net for a wizard whose cache was built before some other change landed.
		_co_teaching, space_conflicts = self.env['ems.attendance_template'].classify_external_conflicts(teacher_entries)
		if space_conflicts:
			raise ValidationError(_(
				"These existing sessions occupy the same space and time as what you're importing, "
				"for a different group/subject - fix the room conflict and try again: %s"
			) % "; ".join(self._conflict_lines(space_conflicts)))

		# NOTE: a teacher double-booked against their OWN existing schedule (e.g. two departments'
		# files scheduling them at the same time) is never caught above - classify_external_conflicts
		# only ever looks for OTHER teachers sharing the same space.
		self_conflicts = self.env['ems.attendance_template'].find_self_conflicts(teacher_entries)
		if self_conflicts:
			raise ValidationError(_(
				"This teacher already has an overlapping session for a different subject/group - "
				"fix the schedule conflict and try again: %s"
			) % "; ".join(self._conflict_lines(self_conflicts)))
		self.env['ems.attendance_template'].sync_from_schedule_batch_fresh_import(teacher_entries)

	def import_planner_data(self):
		self.ensure_one()
		self._apply_import(json.loads(self.parsed_entries_json or '[]'))
		return {
			'type': 'ir.actions.client',
			'tag': 'soft_reload',
		}

	def _resolve_group_name(self, full_name):
		"""Resolve one '<Students name="...">' raw value into an 'ems.group', or an empty recordset
		if no heuristic below matches - extracted out of '_parse_schedule_entries' so it can be
		reused for a name that failed to resolve at parse time (see 'pending_group_names') once the
		'groups' step's picks are known."""
		# NOTE: try the FULL attribute value first — a reinforcement group's name is free-form and
		# can contain spaces (e.g. "Reforç Programació"), so it must match exactly as-is; the real
		# planner export never appends anything to it. Only fall back to the legacy "first word (+
		# trailing 'A')" heuristic below for the 'main' groups' naming convention, where the planner
		# names a level's only group "DAM1" while EMS always stores it with a trailing letter
		# ("DAM1A") — still not found after both attempts means a genuine mismatch that needs manual
		# review.
		group = self.env["ems.group"].search([("name", "=", full_name)], limit=1)
		if group:
			return group
		acro = full_name.split(' ')[0]
		group = self.env["ems.group"].search([("name", "=", acro)], limit=1) \
			or self.env["ems.group"].search([("name", "=", acro + "A")], limit=1)
		if group:
			return group
		# NOTE: for a study with a single course AND a single group, the planner sometimes exports
		# just the bare study acronym ("DEV", "AO"), omitting BOTH the course number and the
		# trailing group letter EMS always stores ("DEV1A", "AO1A") — unlike the "DAM1" case above
		# (course present, only the letter missing), here neither is known upfront, so search by
		# prefix and accept it only if exactly one group matches (an ambiguous prefix is a genuine
		# mismatch, not a guess this heuristic should make).
		candidates = self.env["ems.group"].search([("name", "=like", acro + "%")])
		pattern = re.compile(r"^%s\d+[A-Za-z]$" % re.escape(acro))
		matches = candidates.filtered(lambda group: pattern.match(group.name or ""))
		return matches if len(matches) == 1 else self.env["ems.group"]

	def _finalize_pending_groups(self, entry, name_to_group):
		"""Substitutes 'entry's still-unresolved 'pending_group_names' (see '_parse_schedule_entries')
		with the picks made on the 'groups' step, using 'name_to_group' (a plain dict, raw name ->
		'ems.group'). Called on both shapes 'entry' can take once loaded back from the JSON cache -
		an 'entries' list item, whose 'group_ids' is a flat list of ints, or an 'attendance_ids'
		command's own inner dict, whose 'group_ids' is still in '[(6, 0, ids)]' command form - and
		normalizes both into the same resolved id set. No-op if there's nothing pending (most
		entries, and every entry once already resolved). Always removes the 'pending_group_names'
        key - it must never reach '_apply_import()' still attached, since that key isn't a real
		field on 'resource.calendar.attendance'."""
		pending_names = entry.pop('pending_group_names', None)
		if not pending_names:
			return
		current_group_ids = entry.get('group_ids') or []
		is_command_form = bool(current_group_ids) and isinstance(current_group_ids[0], (list, tuple))
		existing_ids = current_group_ids[0][2] if is_command_form else current_group_ids
		groups = self.env['ems.group'].browse(sorted(
			set(existing_ids) | {name_to_group[name].id for name in pending_names}
		))
		entry['group_ids'] = [(6, 0, groups.ids)] if is_command_form else groups.ids
		entry['name'] += " (%s)" % ", ".join(groups.mapped('name'))

	def _parse_schedule_entries(self, xml_node):
		"""Parse a <Teacher> XML node into (entries, attendance_ids) — the flattened list of real
		(subject/non-teaching) slots plus the (0,0,{...})-command list ready for a resource.calendar's
		'attendance_ids', without writing anything. Pure parsing, reused for a preview (the import
		wizard's onchange handlers, or conflict detection), for the intro step's own cache
		('_classify_attachments'), and for the final step's real write ('_apply_import') - without any
		side effect until that final call. A group name that fails to resolve no longer raises here -
		see 'pending_group_names' below and '_finalize_pending_groups'."""
		non_teaching_items = {t.code: t for t in self.env['ems.non_teaching_type'].search([])}

		entries = []
		attendance_ids = [[5]]
		for dayNode in xml_node:
			# NOTE: 0: Monday; 1: Tuesday as today.weekday() does.			
			dwe = []
			dayofweek = int(dayNode.attrib['name'].split(' ')[0]) - 1			

			for hourNode in dayNode:	
				acronyms = []						
				start = hourNode.attrib['name'].split(' ')[1]				
				new_entry = {						
					"dayofweek": str(dayofweek),
					"day_period": 'morning' if int(start[:2]) < 15 else 'afternoon',
					"hour_from": self.time_string_to_float(start),
					"hour_to": None,
				}

				for content in hourNode:
					# NOTE: 'NonTeaching' is only kept for backward compatibility with older planner
					# exports — the current external app sends non-teaching hours as a 'Subject' node
					# too (its only observable difference is the missing 'Students' sibling), so the
					# real distinction is made by code membership in 'non_teaching_items', not by tag.
					if content.tag in ('Subject', 'NonTeaching'):
						code = content.attrib['name'].split(' ')[0]
						if code in non_teaching_items:
							non_teaching_type = non_teaching_items[code]
							new_entry["name"] = "%s: %s" % (code, non_teaching_type.name)
							new_entry["subject_id"] = False
							new_entry["group_ids"] = [(6, 0, [])]
							new_entry["non_teaching"] = non_teaching_type.id
						else:
							subject = self.env["ems.subject"].search([("code", "=", code)])
							if not subject.id: raise ValidationError("Subject with code '%s' not found." % code)

							new_entry["name"] = "%s: %s" % (subject.acronym, subject.name)
							new_entry["subject_id"] = subject.id
							new_entry["non_teaching"] = False

					elif content.tag == 'Students':
						acronyms.append(content.attrib['name'])

				if len(acronyms) > 0:
					groups = self.env["ems.group"]
					pending_names = []
					for full_name in acronyms:
						group = self._resolve_group_name(full_name)
						if group:
							groups |= group
						else:
							pending_names.append(full_name)
					new_entry["group_ids"] = [(6, 0, groups.ids)]
					if pending_names:
						# NOTE: deferred to the 'groups' step's own resolution screen (see
						# 'ems.working_schedules_import_wizard._continue_from_groups') instead of raising
						# here - a transient, JSON-cache-only marker that must never survive into the
						# '(0, 0, {...})' commands actually passed to
						# 'resource.calendar.attendance.create()' (see '_finalize_pending_groups'). The
						# '(group names)' suffix below is skipped while any name is still pending -
						# rebuilt from the FULL final group set once resolution completes.
						new_entry["pending_group_names"] = pending_names
					else:
						new_entry["name"] += " (%s)" % (", ".join(g.name for g in groups))
				dwe.append(new_entry)
				
			dwe = sorted(dwe, key=lambda e: e["hour_from"])
			for i in range(len(dwe)-1):
				dwe[i]["hour_to"] = dwe[i+1]["hour_from"]

			# NOTE: the planner XML never carries an end time, only each period's start — the day's
			# last period has no "next" one to borrow hour_to from, so it inherits the immediately
			# preceding period's own duration instead. Only a single-period day (nothing to infer
			# duration from) falls back to the fixed company setting.
			if len(dwe) > 1:
				last_period_duration = dwe[-2]["hour_to"] - dwe[-2]["hour_from"]
				dwe[-1]["hour_to"] = dwe[-1]["hour_from"] + last_period_duration
			else:
				dwe[-1]["hour_to"] = self.env.company.schedule_import_last_entry_time

			for e in (x for x in dwe if x.get("name", False)):
				meta = dict(e)
				meta["group_ids"] = e["group_ids"][0][2]
				entries.append(meta)
				attendance_ids.append([0, 0, e])

		return entries, attendance_ids

class ems_working_schedules_import_wizard_group_line(models.TransientModel):
	_name = "ems.working_schedules_import_wizard.group_line"
	_description = "Working schedules import wizard: unresolved group correction line."

	wizard_id = fields.Many2one(string="Wizard", comodel_name="ems.working_schedules_import_wizard", required=True, ondelete="cascade")
	raw_name = fields.Char(string="Name found in file", required=True, readonly=True)
	# NOTE: create-on-the-fly deliberately allowed (no 'no_create'/'no_create_edit' context) - a
	# plain Many2one already gives "pick an existing group, or create one on the spot" for free, no
	# bespoke code needed (see plans/working_schedule_import_redesign.md's step 2).
	group_id = fields.Many2one(string="Group", comodel_name="ems.group")

class ems_working_schedules_import_wizard_teacher_line(models.TransientModel):
	_name = "ems.working_schedules_import_wizard.teacher_line"
	_description = "Working schedules import wizard: unresolved teacher e-mail correction line."

	wizard_id = fields.Many2one(string="Wizard", comodel_name="ems.working_schedules_import_wizard", required=True, ondelete="cascade")
	raw_identifier = fields.Char(string="E-mail found in file", required=True, readonly=True)
	# NOTE: create explicitly disabled in the view (context="{'no_create': True, 'no_create_edit':
	# True}") - the developer's own original call, see plans/working_schedule_import_redesign.md's
	# step 3: a brand-new teacher record is normally screen 6's job (pending-identification,
	# automatic at Import), this screen only ever attaches the schedule to an already-existing
	# employee - EXCEPT when 'create_new' is ticked below, for the genuinely-never-hired case.
	employee_id = fields.Many2one(string="Teacher", comodel_name="hr.employee", domain="[('employee_type', '=', 'teacher')]")
	# NOTE: added 2026-08-05 (developer feedback): some unresolved e-mails are a genuinely new hire,
	# not a typo/mismatch of an already-existing teacher - forcing a pick from 'employee_id' (create
	# disabled) makes no sense for those. Ticking this creates a new pending-identification teacher
	# at Import instead (see '_get_or_create_pending_teacher') - a row is valid if EITHER
	# 'employee_id' is set OR this is ticked, never neither (see '_resolution_is_valid'-equivalent
	# check in '_continue_from_teachers'). Defaults to True (changed 2026-08-06, developer feedback
	# after using it for real): a genuinely never-hired teacher turned out to be the more common
	# case in practice, so an admin who actually needs to pick an existing teacher now has to
	# actively untick this, rather than the other way around.
	create_new = fields.Boolean(string="New", default=True)

	@api.onchange('create_new')
	def _onchange_create_new(self):
		# Keeps the two fields from ever disagreeing - ticking "create new" while a real employee
		# is still picked would leave it ambiguous which one '_continue_from_teachers' should use.
		for line in self:
			if line.create_new:
				line.employee_id = False

class ems_working_schedules_import_wizard_conflict_mixin(models.AbstractModel):
	_name = "ems.working_schedules_import_wizard.conflict_mixin"
	_description = "Working schedules import wizard: shared kind/resolution fields for a conflict line (internal or against an existing DB schedule)."

	# NOTE: computed once, at line-creation time (see '_build_internal_conflict_lines'/
	# '_build_external_conflict_lines') - not an '@api.depends' compute, same convention as
	# 'group_line.raw_name'/'teacher_line.raw_identifier'.
	kind = fields.Selection([
		('co_teaching_eligible', "Co-teaching"),
		('desdoble_eligible', "Split session"),
		('plain_conflict', "Room conflict"),
	], string="Conflict", required=True, readonly=True)
	left_label = fields.Char(string="Left", required=True, readonly=True)
	right_label = fields.Char(string="Right", required=True, readonly=True)
	# NOTE: a flat Selection with every option always visible/selectable, validated server-side on
	# Continue (see '_resolution_is_valid') rather than a widget hiding the options invalid for this
	# row's own 'kind' - confirmed with the developer 2026-08-05 as the simpler, equally-valid
	# option the plan itself offered (plans/working_schedule_import_redesign.md's "Complexity flag").
	resolution = fields.Selection([
		('co_teaching', "Confirm"),
		('prevail_left', "Left prevails"),
		('prevail_right', "Right prevails"),
		('reassign_rooms', "Reassign rooms"),
	], string="Resolution", required=True)
	# NOTE: only relevant when 'resolution' is 'reassign_rooms' - pre-filled with the colliding room
	# for every desdoble-eligible line regardless of its current resolution, so they're ready the
	# moment "reassign_rooms" is picked.
	left_space_id = fields.Many2one(string="Left classroom", comodel_name="ems.space")
	right_space_id = fields.Many2one(string="Right classroom", comodel_name="ems.space")

	def _resolution_is_valid(self):
		self.ensure_one()
		allowed_by_kind = {
			'co_teaching_eligible': {'co_teaching', 'prevail_left', 'prevail_right'},
			'desdoble_eligible': {'reassign_rooms', 'prevail_left', 'prevail_right'},
			'plain_conflict': {'reassign_rooms', 'prevail_left', 'prevail_right'},
		}
		if self.resolution not in allowed_by_kind[self.kind]:
			return False
		if self.resolution == 'reassign_rooms':
			return bool(self.left_space_id) and bool(self.right_space_id) and self.left_space_id != self.right_space_id
		return True

class ems_working_schedules_import_wizard_internal_conflict_line(models.TransientModel):
	_name = "ems.working_schedules_import_wizard.internal_conflict_line"
	_inherit = ["ems.working_schedules_import_wizard.conflict_mixin"]
	_description = "Working schedules import wizard: within-batch room collision line."

	wizard_id = fields.Many2one(string="Wizard", comodel_name="ems.working_schedules_import_wizard", required=True, ondelete="cascade")
	# NOTE: positional references into the wizard's own 'parsed_entries_json' node_cache structure
	# (item index, entry index within that item's own 'entries' list) - not content-matching, see
	# '_continue_from_internal_conflicts'. Both sides are new entries from THIS import here.
	left_item_index = fields.Integer(required=True, readonly=True)
	left_entry_index = fields.Integer(required=True, readonly=True)
	right_item_index = fields.Integer(required=True, readonly=True)
	right_entry_index = fields.Integer(required=True, readonly=True)

class ems_working_schedules_import_wizard_external_conflict_line(models.TransientModel):
	_name = "ems.working_schedules_import_wizard.external_conflict_line"
	_inherit = ["ems.working_schedules_import_wizard.conflict_mixin"]
	_description = "Working schedules import wizard: new entry vs. already-active DB schedule collision line."

	wizard_id = fields.Many2one(string="Wizard", comodel_name="ems.working_schedules_import_wizard", required=True, ondelete="cascade")
	# NOTE: the LEFT side is a new entry from this import - positional reference into node_cache,
	# same as 'internal_conflict_line'. The RIGHT side is a real, already-persisted
	# 'ems.attendance_schedule' record - a genuine Many2one, not a position.
	left_item_index = fields.Integer(required=True, readonly=True)
	left_entry_index = fields.Integer(required=True, readonly=True)
	right_schedule_id = fields.Many2one(string="Existing session", comodel_name="ems.attendance_schedule", required=True, readonly=True)

