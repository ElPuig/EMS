# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
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
		per teacher). Also matches a 'framework'/other non-personal calendar with an empty recordset."""
		self.ensure_one()
		return self.env['hr.employee'].search([('resource_calendar_id', '=', self.id)])

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
		('internal_conflicts', "Internal conflicts"),
		('db_conflicts', "Existing schedule conflicts"),
		('pending_info', "Pending teachers"),
		('override_info', "Existing teachers"),
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
	# NOTE: drives whether "Continue" renders enabled or disabled (developer feedback 2026-08-05:
	# "que quedará mas claro si los botones de continuar... aparecen como enabled o disabled" rather
	# than appearing/disappearing) - the view keeps the button in the SAME place either way (two
	# stacked buttons, only one visible at a time: the real actionable one, or a cosmetic
	# 'disabled="disabled"' twin with no 'name' - see import_wizard.xml), instead of hiding it
	# outright the way 'override_info' still does for a wholly different screen's button.
	continue_disabled = fields.Boolean(compute="_compute_continue_disabled")

	@api.depends("state", "ready_to_import", "group_line_ids.group_id", "teacher_line_ids.employee_id")
	def _compute_continue_disabled(self):
		for wizard in self:
			if wizard.state == 'intro':
				wizard.continue_disabled = not wizard.ready_to_import
			elif wizard.state == 'groups':
				wizard.continue_disabled = bool(wizard.group_line_ids.filtered(lambda line: not line.group_id))
			elif wizard.state == 'teachers':
				wizard.continue_disabled = bool(wizard.teacher_line_ids.filtered(lambda line: not line.employee_id))
			else:
				wizard.continue_disabled = False

	_STATE_SEQUENCE = ['intro', 'groups', 'teachers', 'internal_conflicts', 'db_conflicts', 'pending_info', 'override_info']

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
		step's own logic. Only 'intro', 'groups' and 'teachers' have real logic built so far (see
		plans/working_schedule_import_redesign.md); every other step is still a placeholder that
		just advances the statusbar, so the skeleton is clickable end-to-end already and each step
		gets filled in here as it's built."""
		self.ensure_one()
		if self.state == 'intro':
			self._continue_from_intro()
		elif self.state == 'groups':
			self._continue_from_groups()
		elif self.state == 'teachers':
			self._continue_from_teachers()
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

	def _continue_from_teachers(self):
		"""The 'teachers' step's own 'Continue' handler, mirroring '_continue_from_groups': every
		'teacher_line_ids' row must have a teacher picked (raised otherwise), then every 'node_cache'
		item sharing that row's raw identifier gets an 'employee_id' key written onto it directly
		(the identifier is the item's own top-level field, not part of 'entries'/'attendance_ids'
		like a group reference - no '_finalize_pending_groups'-style dict-shape juggling needed)."""
		self.ensure_one()
		unresolved_lines = self.teacher_line_ids.filtered(lambda line: not line.employee_id)
		if unresolved_lines:
			raise ValidationError(_(
				"Please select a teacher for every unresolved e-mail before continuing:\n%s"
			) % "\n".join(unresolved_lines.mapped('raw_identifier')))

		identifier_to_employee = {line.raw_identifier: line.employee_id for line in self.teacher_line_ids}
		node_cache = json.loads(self.parsed_entries_json or '[]')
		for item in node_cache:
			employee = identifier_to_employee.get(item['identifier'])
			if employee:
				item['employee_id'] = employee.id
		self.parsed_entries_json = json.dumps(node_cache)
		self._advance_state()

	def _write_teacher_schedule(self, teacher, course_id, attendance_ids):
		"""Creates (if missing) or updates 'teacher's resource.calendar for 'course_id', writing
		'attendance_ids' (already-parsed (0, 0, {...}) commands - see '_parse_schedule_entries')."""
		name = "%s (%s)" % (teacher.name, course_id.name)
		schedule = self.env['resource.calendar'].search([('name', '=', name)]) or False
		if not schedule:
			schedule = self.env['resource.calendar'].create({'name': name, 'full_time_required_hours': 24})
		schedule.write({'attendance_ids': attendance_ids})
		teacher.write({'resource_calendar_id': schedule})

	def _apply_import(self, node_cache):
		"""Writes everything (resource.calendar/ems.teaching per teacher, then the
		ems.attendance_template batch sync) from the raw per-node cache '_continue_from_intro' built -
		deferred until this final step so nothing is written before the whole wizard flow completes.
		Mirrors this model's former create() override, adapted to work from the cache instead of
		re-parsing the XML from scratch (which would also re-resolve teachers/pending-codes against
		data this same call is about to change)."""
		course_id = self.env.company.current_course_id
		# NOTE: attendance_template sync is deferred and batched across every teacher (see
		# sync_from_schedule_batch_fresh_import) — syncing one teacher at a time here would let an
		# early teacher's fresh schedule line falsely collide with a later teacher's still-stale one
		# whenever they share a classroom, since the later teacher hasn't been re-synced yet.
		teacher_entries = []
		for item in node_cache:
			identifier = item['identifier']
			if item.get('employee_id'):
				# NOTE: resolved on the 'teachers' step (see '_continue_from_teachers') - an
				# identifier that never needed a correction line (already matched 'work_email' on
				# its own) falls through to the plain lookup branch below instead, unaffected.
				teacher = self.env["hr.employee"].browse(item['employee_id'])
			elif self._is_email_like(identifier):
				teacher = self.env["hr.employee"].search([("work_email", "=", identifier)])
				if not teacher.id:
					# NOTE: safety net for a direct ORM/API caller bypassing the wizard's own
					# step-by-step UI - a real user reaching Import through the wizard already had
					# every unresolved e-mail turned into a 'teacher_line' at the 'teachers' step.
					raise ValidationError(_("Teacher with email '%s' not found.") % identifier)
			else:
				teacher = self.env["hr.employee"].search([("schedule_import_code", "=", identifier)])
				if not teacher.id:
					teacher = self.env["hr.employee"].create({
						"name": _("Pending teacher (%s)") % identifier,
						"employee_type": "teacher",
						"schedule_import_code": identifier,
					})

			self._write_teacher_schedule(teacher, course_id, item['attendance_ids'])
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
	# True}") - the developer's own call, see plans/working_schedule_import_redesign.md's step 3: a
	# brand-new teacher record is screen 6's job (pending-identification, automatic at Import), this
	# screen only ever attaches the schedule to an already-existing employee.
	employee_id = fields.Many2one(string="Teacher", comodel_name="hr.employee", domain="[('employee_type', '=', 'teacher')]")

