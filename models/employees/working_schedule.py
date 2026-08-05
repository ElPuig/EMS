# -*- coding: utf-8 -*-

from markupsafe import Markup, escape
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import xml.etree.ElementTree as ET
import base64
import math
import re


def _m2m_command_ids(commands):
	"""Resolve a Many2many/One2many value (as found in raw create()/write() vals, e.g. a planner
	XML entry's 'group_ids') into a plain list of ids - shared by the import wizard and the
	working-schedule block's own create() override, both of which need to read an id list out of
	a not-yet-written value rather than an already-browsable recordset. Accepts either the real
	command-tuple format ('(6, 0, ids)', '(4, id)'...) or a bare list of ids (the shape the
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
	# Non-blocking yellow banner: bullet list of teachers who already have a schedule that will be
	# updated. Html (not Char) so many teachers render as a real list instead of one long comma sentence.
	overrided_teachers_html = fields.Html(readonly=True, store=False)
	# Non-blocking yellow banner: bullet list of OTHER teachers (not part of this file) whose existing
	# session overlaps one of this file's own, same subject and sharing a group — i.e. legitimate
	# co-teaching (see ems.attendance_template.classify_external_conflicts), left untouched, just
	# surfaced so the admin can confirm this is really intended before continuing.
	co_teaching_html = fields.Html(readonly=True, store=False)
	# Blocking (red banner, hides the 'Import' button): bullet list of specific problems that each
	# prevent the import from continuing (unknown teacher e-mail, unresolved group/subject code,
	# missing classroom, a genuine room double-booking against a teacher outside this file...). Html
	# (not Char) so several problems render as a real list instead of one long comma sentence.
	blocking_issues_html = fields.Html(readonly=True, store=False)
	# Non-blocking (blue banner): bullet list of identifiers with no '@' (a short placeholder code like
	# "X1", or a not-yet-hired teacher's own full name) that don't match any employee by e-mail or
	# existing code; a pending-identification teacher will be created for each one on import. Never
	# hides the 'Import' button. Html (not Char) so several of them render as a real list instead of
	# one long comma sentence — same reasoning as 'blocking_issues_html'.
	info_html = fields.Html(readonly=True, store=False)
	# Gates the 'Import' button. Deliberately fail-closed (starts False, only this onchange ever sets
	# it True) instead of fail-open (hide only once a problem is confirmed) - a file upload's own async
	# work finishes before the onchange RPC that validates its content does, and with a fail-open
	# design (hide only when blocking_issues_html is set) the button was visible and clickable during
	# that whole gap, since that field simply hadn't been computed yet. Fail-closed means there is no
	# gap: the button cannot render enabled before this onchange has actually finished confirming there
	# is nothing wrong.
	ready_to_import = fields.Boolean(store=False)

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

	def _bullet_html(self, lines):
		"""A readonly <ul><li> list from plain-text lines (escaped), or False for none — used to
		render the wizard's warning banners as a real list instead of one long comma sentence. Balanced
		into a few CSS columns (see 'ems_wizard_bullet_list' in ems.css) so a long list of short items
		(pending codes, teacher names...) doesn't waste the dialog's horizontal space."""
		if not lines:
			return False
		items = Markup("").join(Markup("<li>%s</li>") % escape(line) for line in lines)
		return Markup('<ul class="ems_wizard_bullet_list">%s</ul>') % items

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

	@api.onchange("attachment_ids")
	def _onchange_attachment_ids(self):
		for rec in self:
			rec.blocking_issues_html = False
			rec.info_html = False
			rec.co_teaching_html = False
			rec.ready_to_import = False
			overrided, blocking_issues, pending_codes, teacher_entries = [], [], [], []
			for attachment in rec.attachment_ids:
				xml_content = base64.b64decode(attachment.datas)
				tree = ET.ElementTree(ET.fromstring(xml_content))

				for teacherNode in tree.getroot():
					email = rec._teacher_identifier(teacherNode.attrib['name'])
					teacher = False
					if rec._is_email_like(email):
						teacher = self.env["hr.employee"].search([("work_email", "=", email)]) or False
						if not teacher:
							blocking_issues.append(_("unknown e-mail '%s' in '%s'") % (email, attachment.name))
							continue
					else:
						teacher = self.env["hr.employee"].search([("schedule_import_code", "=", email)]) or False
						if not teacher:
							# NOTE: no real employee exists yet for this code - one will only be
							# created for real in create(). Still parse this node's own schedule
							# content below (subject/group resolution) rather than skipping it
							# entirely: an unresolvable group/subject in a not-yet-identified
							# teacher's row must surface here as a blocking issue too, not only
							# blow up uncaught later, when 'create()' actually imports it.
							pending_codes.append(email)

					if teacher and teacher.resource_calendar_id.id:
						overrided.append(teacher.display_name)
					try:
						entries = [e for e in rec._parse_schedule_entries(teacherNode)[0] if not e["non_teaching"]]
					except ValidationError as error:
						blocking_issues.append(str(error))
						continue
					if teacher:
						teacher_entries.append((teacher, entries))

			missing_space = rec._groups_without_space(teacher_entries)
			blocking_issues += rec._missing_space_lines(missing_space)

			if not missing_space:
				co_teaching, space_conflicts = self.env['ems.attendance_template'].classify_external_conflicts(teacher_entries)
				rec.co_teaching_html = rec._bullet_html(rec._conflict_lines(co_teaching))
				blocking_issues += rec._space_conflict_lines(space_conflicts)
				self_conflicts = self.env['ems.attendance_template'].find_self_conflicts(teacher_entries)
				blocking_issues += rec._self_conflict_lines(self_conflicts)

			rec.blocking_issues_html = rec._bullet_html(blocking_issues)
			rec.info_html = rec._bullet_html(pending_codes)
			rec.overrided_teachers_html = rec._bullet_html(overrided)
			rec.ready_to_import = bool(rec.attachment_ids) and not blocking_issues

	def import_planner_data(self):
		return {
			'type': 'ir.actions.client',
			'tag': 'soft_reload',
		}
	
	@api.model_create_multi
	def create(self, values):
		course_id = self.env.company.current_course_id
		if not course_id.id:
			raise ValidationError("No 'current course' has been setup. Please, select or create the current course within the EMS settings section.")
		
		for item in values:
			xml_contents = self._collect_xml_contents(item)
			if not xml_contents:
				raise ValidationError(_("No XML file has been loaded. Please, provide at least one XML file and try again."))

			# NOTE: attendance_template sync is deferred and batched across every teacher in this item
			# (see sync_from_schedule_batch) — syncing one teacher at a time here would let an early
			# teacher's fresh schedule line falsely collide with a later teacher's still-stale one
			# whenever they share a classroom, since the later teacher hasn't been re-synced yet.
			teacher_entries = []
			for xml_content in xml_contents:
				tree = ET.ElementTree(ET.fromstring(xml_content))
				root = tree.getroot()

				nodes = []
				for node in root:
					email = self._teacher_identifier(node.attrib['name'])
					if self._is_email_like(email):
						teacher = self.env["hr.employee"].search([("work_email", "=", email)])
						if not teacher.id:
							raise ValidationError(_("Teacher with email '%s' not found.") % email)
					else:
						teacher = self.env["hr.employee"].search([("schedule_import_code", "=", email)])
						if not teacher.id:
							teacher = self.env["hr.employee"].create({
								"name": _("Pending teacher (%s)") % email,
								"employee_type": "teacher",
								"schedule_import_code": email,
							})
					nodes.append((node, teacher))

				for node, teacher in nodes:
					entries = self._create_schedule(node, teacher, course_id)
					entries = [e for e in entries if not e["non_teaching"]]
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
			# is the safety net for a direct create() call that skipped the onchange.
			_co_teaching, space_conflicts = self.env['ems.attendance_template'].classify_external_conflicts(teacher_entries)
			if space_conflicts:
				raise ValidationError(_(
					"These existing sessions occupy the same space and time as what you're importing, "
					"for a different group/subject - fix the room conflict and try again: %s"
				) % "; ".join(self._conflict_lines(space_conflicts)))

			# NOTE: a teacher double-booked against their OWN existing schedule (e.g. two departments'
			# files scheduling them at the same time) is never caught above - classify_external_conflicts
			# only ever looks for OTHER teachers sharing the same space. Checked here too (not just in
			# the onchange preview) as the safety net for a direct create() call that skipped it.
			self_conflicts = self.env['ems.attendance_template'].find_self_conflicts(teacher_entries)
			if self_conflicts:
				raise ValidationError(_(
					"This teacher already has an overlapping session for a different subject/group - "
					"fix the schedule conflict and try again: %s"
				) % "; ".join(self._conflict_lines(self_conflicts)))
			self.env['ems.attendance_template'].sync_from_schedule_batch_fresh_import(teacher_entries)

		return super(models.Model, self).create(values)

	def _collect_xml_contents(self, item):
		"""Every XML source given for this wizard's 'create()' vals, decoded."""
		contents = []
		attachment_ids = _m2m_command_ids(item.get('attachment_ids'))
		for attachment in self.env['ir.attachment'].browse(attachment_ids):
			contents.append(base64.b64decode(attachment.datas))
		return contents

	def _create_schedule(self, xml_node, teacher, course_id):
		entries, attendance_ids = self._parse_schedule_entries(xml_node)

		name = "%s (%s)" % (teacher.name, course_id.name)
		schedule = self.env['resource.calendar'].search([('name', '=', name)]) or False
		if not schedule:
			# TODO: add a relation to current_course
			schedule = self.env['resource.calendar'].create({
				'name': "%s (%s)" % (teacher.name, course_id.name),
				'full_time_required_hours': 24
			})

		schedule.write({ 'attendance_ids': attendance_ids })
		teacher.write({ "resource_calendar_id": schedule })
		return entries

	def _parse_schedule_entries(self, xml_node):
		"""Parse a <Teacher> XML node into (entries, attendance_ids) — the flattened list of real
		(subject/non-teaching) slots plus the (0,0,{...})-command list ready for a resource.calendar's
		'attendance_ids', without writing anything. Pure parsing, split out of '_create_schedule' so it
		can be reused for a preview (e.g. the import wizard's onchange handlers, or conflict detection)
		without any side effect."""
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
					for full_name in acronyms:
						# NOTE: try the FULL attribute value first — a reinforcement group's name is
						# free-form and can contain spaces (e.g. "Reforç Programació"), so it must match
						# exactly as-is; the real planner export never appends anything to it. Only fall
						# back to the legacy "first word (+ trailing 'A')" heuristic below for the 'main'
						# groups' naming convention, where the planner names a level's only group "DAM1"
						# while EMS always stores it with a trailing letter ("DAM1A") — still not found
						# after both attempts means a genuine mismatch that needs manual review.
						group = self.env["ems.group"].search([("name", "=", full_name)], limit=1)
						if not group:
							acro = full_name.split(' ')[0]
							group = self.env["ems.group"].search([("name", "=", acro)], limit=1) \
								or self.env["ems.group"].search([("name", "=", acro + "A")], limit=1)
						if not group:
							# NOTE: for a study with a single course AND a single group, the planner
							# sometimes exports just the bare study acronym ("DEV", "AO"), omitting BOTH
							# the course number and the trailing group letter EMS always stores ("DEV1A",
							# "AO1A") — unlike the "DAM1" case above (course present, only the letter
							# missing), here neither is known upfront, so search by prefix and accept it
							# only if exactly one group matches (an ambiguous prefix is a genuine mismatch,
							# not a guess this heuristic should make).
							candidates = self.env["ems.group"].search([("name", "=like", acro + "%")])
							pattern = re.compile(r"^%s\d+[A-Za-z]$" % re.escape(acro))
							matches = candidates.filtered(lambda g: pattern.match(g.name or ""))
							if len(matches) == 1:
								group = matches
						if not group:
							raise ValidationError("Group with acronym '%s' not found." % full_name)
						groups |= group
					new_entry["group_ids"] = [(6, 0, groups.ids)]
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

