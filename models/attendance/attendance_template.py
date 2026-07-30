# -*- coding: utf-8 -*-

from datetime import datetime

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

TEMPLATE_COLOR_PALETTE = [
	'#EE2D2D', '#DC8534', '#E8BB1D', '#5794DD', '#9F628F', '#DB8865',
	'#41A9A2', '#304BE0', '#EE2F8A', '#61C36E', '#9872E6', '#A2A2A2',
]

class EmsAttendanceTemplate(models.Model):
	_name = "ems.attendance_template"
	_description = "Attendance template: contains the basic attendance data (who teaches what, where and for whom)"
	_inherit = ['ems.base', 'ems.hex_color_mixin']

	start_date = fields.Date(string="Start date", required=True)
	end_date = fields.Date(string="End date", required=True)
	color = fields.Char(string="Color", default="#3A8DDE", help="Free-pick display color, used to tell templates apart in the list view.")
	teacher_ids = fields.Many2many(string="Teachers", comodel_name="hr.employee", relation="ems_attendance_template_teacher_rel", domain="[('employee_type', '=', 'teacher')]", required=True, default=lambda self: self._default_teacher_ids())
	# NOTE: not required — a reinforcement ems.group (group_type == 'reinforcement') has no level/study
	# of its own, so a template built from one (see '_write_schedule_sync') leaves both False.
	level_id = fields.Many2one(string="Level", comodel_name="ems.level")
	study_id = fields.Many2one(string="Study", comodel_name="ems.study", domain="[('level_id', '=', level_id)]")
	group_ids = fields.Many2many(string="Groups", comodel_name="ems.group", domain="[('study_id', '=', study_id)]")
	subject_id = fields.Many2one(string="Subject", comodel_name="ems.subject", domain="[('study_ids', 'in', study_id)]", required=True)
	space_id = fields.Many2one(string="Space", comodel_name="ems.space", required=True)
	
	attendance_schedule_ids = fields.One2many(string="Sessions", comodel_name="ems.attendance_schedule", inverse_name="attendance_template_id")			
	student_ids = fields.Many2many(string="Students", comodel_name="res.partner", domain="[('contact_type', '=', 'student')]")	

	# NOTE: this field is computed when loaded within a form or list
	read_only_user = fields.Boolean(default=lambda self:self._get_read_only_user(), store=False)
	
	def _get_read_only_user(self):
		return not (self.id == False or self.get_user_is_admin() or bool(self.teacher_ids.filtered(lambda teacher: teacher.user_id.id == self.env.uid)) or self.create_uid == self.env.uid)

	def _default_teacher_ids(self):
		teacher = self.env["hr.employee"].search([("user_id", "=", self.env.uid), ("employee_type", "=", "teacher")])
		return [(6, 0, teacher.ids)]

	@api.constrains('group_ids')
	def _check_group_ids(self):
		for template in self:
			if not template.group_ids:
				raise ValidationError(_("At least one group must be selected."))

	@api.constrains('teacher_ids')
	def _check_teacher_ids(self):
		for template in self:
			if not template.teacher_ids:
				raise ValidationError(_("At least one teacher must be selected."))

	@api.constrains('teacher_ids', 'start_date', 'end_date', 'active')
	def _check_schedule_overlap(self):
		# NOTE: @api.constrains does not support dotted paths through relations, so changes to
		# these template fields must re-trigger the check owned by ems.attendance_schedule.
		for template in self:
			template.attendance_schedule_ids.check_overlap()

	@api.constrains("color")
	def _check_color_format(self):
		self._check_hex_color('color')

	@api.depends('subject_id', 'group_ids')
	def _compute_display_name(self):
		for template in self:
			groups = ", ".join(template.group_ids.mapped('name'))
			template.display_name = "%s (%s)" % (template.subject_id.display_name, groups)

	@api.onchange("group_ids")
	def _onchange_group_ids(self):
		for template in self:
			if template.group_ids:
				template.space_id = template.group_ids[0].space_id

	@api.onchange("subject_id", "group_ids")
	def _fill_students(self):
		for template in self:
			template.fill_students()

	def fill_students(self):
		students = self.env['ems.enrollment'].search([
			('group_id', 'in', self.group_ids.ids),
			('subject_id', '=', self.subject_id.id)
		]).mapped('student_id')
		self.student_ids = [(6, 0, students.ids)]

	def reload_students(self):
		self.student_ids = [(5)]
		self.fill_students()

	def action_archive(self):
		super().action_archive()
		for sch in self.attendance_schedule_ids:
			sch.action_archive()

	def unlink(self):
		for sch in self.attendance_schedule_ids:
			if len(sch.attendance_session_ids) > 0:
				raise ValidationError(_("This template have been already used to check the student's attendances and cannot be deleted. Please, archive it instead."))
		return super().unlink()

	def sync_from_schedule(self, teacher, entries, start_date=None):
		"""Sync a single teacher's schedule — the employee 'Schedule' tab's grid widget (a live
		mid-course edit). Internally delegates to sync_from_schedule_batch() wrapping its single
		(teacher, entries) pair, so a solo edit goes through the exact same co-teaching reconciliation
		as the XML importer's multi-teacher batch (see '_reconcile_teacher_groups')."""
		self.sync_from_schedule_batch([(teacher, entries)], start_date=start_date)

	def sync_from_schedule_batch(self, teacher_entries, start_date=None):
		"""Sync one or several teachers at once — the XML importer's normal case (one planner file
		typically describes many teachers), and also used by sync_from_schedule() for a single live
		edit. 'teacher_entries' is a list of (teacher, entries) pairs.

		First reconciles co-teaching: '_reconcile_teacher_groups' merges the freshly submitted entries
		against whatever ALREADY exists in the DB for the same (subject, group-set) combinations, at
		the exact (weekday, hour_from, hour_to) slot level, producing one (teachers, entries) group per
		distinct combination of subject+groups+exact-teacher-set — see that method's docstring for the
		full reasoning, including how a solo edit by one teacher can retroactively split another
		teacher's existing template.

		Then archives every resulting group's stale schedule lines FIRST, across the WHOLE batch,
		before writing ANY group's fresh ones — doing this one group at a time can raise a false
		check_overlap() collision when two groups share a classroom: the first group's fresh line would
		be checked against the second group's still-active STALE line, since that second group hasn't
		been re-synced yet at that point."""
		merged_groups, vacated = self._reconcile_teacher_groups(teacher_entries)
		vacated.action_archive()
		plans = [self._plan_schedule_sync(teachers, entries, start_date=start_date) for teachers, entries in merged_groups]
		for plan in plans:
			self._archive_stale_schedule_sync(plan)
		for plan in plans:
			self._write_schedule_sync(plan)

	def _reconcile_teacher_groups(self, teacher_entries):
		"""teacher_entries: [(teacher, entries), ...] — teachers submitting fresh data RIGHT NOW (just
		one for the 'Schedule' tab's live editor, several for the XML importer). For every (subject,
		group-set) combination they touch, reconciles against the FULL current state in the DB —
		including the slots already held by OTHER teachers for that same combination who are NOT
		submitting data in this call — at the exact (weekday, hour_from, hour_to) slot level, so that:
		- a slot only ever held by teachers submitting data now ends up solo-owned by them,
		- a slot that now matches EXACTLY (day+time) with a non-submitting teacher's existing slot gets
		  merged into a shared group with both,
		- a slot belonging to a non-submitting teacher that nobody submitting now touches is left alone.

		This is what lets a single teacher's live edit correctly SPLIT another teacher's template: if
		teacher A already has Monday+Wednesday and teacher B (submitting alone) now also teaches that
		exact Wednesday slot, Wednesday becomes a new shared (A, B) group while Monday stays a solo A
		group — without needing separate logic for the live-editor vs. the batch importer. It also
		covers a submitting teacher simply DROPPING a subject+group combo they used to teach (submitting
		zero entries for it): the combo is still reconciled (against a search below, not just the
		submitted entries), so a template belonging solely to that teacher ends up in 'vacated' instead
		of silently surviving untouched.

		Returns (merged, vacated): 'merged' is a list of (teachers_recordset, entries) pairs, same shape
		'_plan_schedule_sync' already consumes; 'vacated' is a recordset of templates whose every slot
		was superseded by this call with no surviving teacher left for that (subject, group) combination
		— to be archived outright, since nothing replaces them."""
		submitting_teacher_ids = {teacher.id for teacher, _entries in teacher_entries}
		by_key_submitted = dict()
		for teacher, entries in teacher_entries:
			for entry in entries:
				if not entry.get('group_ids'):
					continue  # non-teaching entries carry no group, hence no co-teaching to reconcile
				key = (entry['subject_id'], tuple(sorted(entry['group_ids'])))
				by_key_submitted.setdefault(key, []).append((teacher, entry))

		# NOTE: also reconcile (subject, group) combos a submitting teacher used to teach but is not
		# submitting anything for anymore in this call — otherwise a dropped combo belonging solely to
		# that teacher would never be reconsidered at all (see 'vacated' above).
		touched_templates = self.env['ems.attendance_template'].search([
			('teacher_ids', 'in', list(submitting_teacher_ids)), ('active', '=', True),
		])
		for template in touched_templates:
			key = (template.subject_id.id, tuple(sorted(template.group_ids.ids)))
			by_key_submitted.setdefault(key, [])

		merged = []
		vacated = self.env['ems.attendance_template']
		for (subject_id, group_ids), submitted in by_key_submitted.items():
			existing_templates = self.env['ems.attendance_template'].search([
				('subject_id', '=', subject_id),
				('group_ids', 'in', list(group_ids)),
				('active', '=', True),
			]).filtered(lambda template, group_ids=group_ids: set(template.group_ids.ids) == set(group_ids))

			by_slot = dict()
			for template in existing_templates:
				# Teachers of this template NOT submitting data now: their slots are preserved as-is,
				# unless a submitting teacher lands on the exact same slot (merged below).
				untouched = template.teacher_ids.filtered(lambda teacher: teacher.id not in submitting_teacher_ids)
				if not untouched:
					continue  # every teacher of this template is submitting now: fully superseded
				for line in template.attendance_schedule_ids:
					slot_key = (line.weekday, line.start_time, line.end_time)
					by_slot.setdefault(slot_key, {'teacher_ids': set(), 'entry': {
						'subject_id': subject_id,
						'group_ids': list(group_ids),
						'dayofweek': line.weekday,
						'hour_from': line.start_time,
						'hour_to': line.end_time,
					}})
					by_slot[slot_key]['teacher_ids'].update(untouched.ids)

			for teacher, entry in submitted:
				slot_key = (entry['dayofweek'], entry['hour_from'], entry['hour_to'])
				by_slot.setdefault(slot_key, {'teacher_ids': set(), 'entry': entry})
				by_slot[slot_key]['teacher_ids'].add(teacher.id)

			by_teacher_set = dict()
			for slot in by_slot.values():
				by_teacher_set.setdefault(frozenset(slot['teacher_ids']), []).append(slot['entry'])

			# NOTE: an existing template survives, as-is, only if some resulting group's teacher-set
			# matches it EXACTLY (picked up later by '_plan_schedule_sync's own exact-match lookup, which
			# refreshes its schedule lines from 'slot_entries'). Any existing template whose teacher-set
			# split into different group(s) above — whether it shrank (a co-teacher dropped out, as
			# above) or vanished entirely (by_teacher_set is empty for this key) — has no such match and
			# must be archived outright here, since nothing else will ever catch it: '_plan_schedule_sync'
			# only ever looks for an EXACT teacher-set match to update, never a partial/superset one.
			result_teacher_sets = set(by_teacher_set.keys())
			for template in existing_templates:
				if frozenset(template.teacher_ids.ids) not in result_teacher_sets:
					vacated |= template

			for teacher_ids, slot_entries in by_teacher_set.items():
				merged.append((self.env['hr.employee'].browse(teacher_ids), slot_entries))
		return merged, vacated

	def find_external_conflicts(self, teacher_entries):
		"""Given [(teacher, entries), ...] (same shape as sync_from_schedule_batch), find every
		currently active ems.attendance_schedule belonging ONLY to teachers NOT part of this batch —
		that would collide (same space, weekday, overlapping time) with one of the new entries. A batch
		only ever cleans up its own teachers' stale data (see '_archive_stale_schedule_sync'); a
		teacher who simply isn't in this particular file can still be left with an old schedule line in
		a classroom the new import now also wants at an overlapping time. Used both to preview what the
		import wizard is about to archive (before the user confirms) and, at actual import time, to
		archive those lines so the fresh ones can be written without a false check_overlap() — the
		returned lines, not their whole templates, since the rest of that external teacher's schedule is
		presumably still correct."""
		teacher_ids = {teacher.id for teacher, _entries in teacher_entries}
		conflicts = self.env['ems.attendance_schedule']
		for _teacher, entries in teacher_entries:
			for entry in entries:
				if not entry.get('group_ids'):
					continue  # non-teaching entries carry no group, hence no space to collide on
				space_id = self.env['ems.group'].browse(entry['group_ids'][0]).space_id.id
				candidates = self.env['ems.attendance_schedule'].search([
					('weekday', '=', entry['dayofweek']),
					('space_id', '=', space_id),
					('attendance_template_id.teacher_ids', 'not in', list(teacher_ids)),
				])
				conflicts |= candidates.filtered(
					lambda candidate, entry=entry: (
						candidate.ranges_overlap(candidate.start_time, candidate.end_time, entry['hour_from'], entry['hour_to'])
						# NOTE: same subject, sharing at least one group — the SAME class session
						# co-taught by another teacher (see ems.attendance_schedule.is_co_teaching_with),
						# not a genuine room double-booking to archive.
						and not (
							candidate.attendance_template_id.subject_id.id == entry.get('subject_id')
							and set(candidate.attendance_template_id.group_ids.ids) & set(entry.get('group_ids') or [])
						)
					)
				)
		return conflicts

	def _plan_schedule_sync(self, teachers, entries, start_date=None):
		"""Compute what a sync means for a single (teachers, entries) reconciled group without writing
		anything yet: which currently active templates sharing this exact (subject, group-set,
		teacher-set) combination are stale (gone, or persisting with different lines) and what the
		freshly reconciled entries, grouped by (subject, group-set) key, look like. Consumed by
		'_archive_stale_schedule_sync'/'_write_schedule_sync' — split out so 'sync_from_schedule_batch'
		can run the archive phase for every group before the write phase for any of them."""
		now = datetime.now()
		start_date = start_date or datetime(now.year, 9, 1)
		end_date = datetime(now.year + 1, 7, 1)

		# NOTE: maps to a RECORDSET, not a single template — the same (subject, group-set, teacher-set)
		# combination can have more than one active template (a pre-existing data-quality issue:
		# repeated past imports created a new template instead of matching the existing one). Keying by
		# a single template here would silently drop every duplicate but the last one seen, leaving them
		# forever un-synced — see '_archive_stale_schedule_sync'/'_write_schedule_sync' for how
		# duplicates get consolidated into a single survivor.
		old_items = dict()
		candidates = self.env['ems.attendance_template'].search([
			('subject_id', 'in', list({entry["subject_id"] for entry in entries})),
			('active', '=', True),
		])
		for template in candidates:
			if set(template.teacher_ids.ids) != set(teachers.ids):
				continue
			key = "%s.%s" % (template.subject_id.id, ",".join(str(g) for g in sorted(template.group_ids.ids)))
			old_items[key] = old_items.get(key, self.env['ems.attendance_template']) | template

		grouped_entries = dict()
		for entry in entries:
			key = "%s.%s" % (entry["subject_id"], ",".join(str(g) for g in sorted(entry["group_ids"])))
			grouped_entries.setdefault(key, []).append(entry)

		return {
			'teachers': teachers,
			'old_items': old_items,
			'grouped_entries': grouped_entries,
			'start_date': start_date,
			'end_date': end_date,
		}

	def _schedule_lines(self, group_entries, space_id):
		return [
			(0, 0, {
				'start_time': entry["hour_from"],
				'end_time': entry["hour_to"],
				'weekday': entry["dayofweek"],
				'space_id': space_id,
			})
			for entry in group_entries
		]

	def _archive_stale_schedule_sync(self, plan):
		"""First pass: archive every schedule line about to be removed or replaced by '_write_schedule_sync'.
		Must run for every plan in a batch before any plan's '_write_schedule_sync' — see
		'sync_from_schedule_batch' for why."""
		for key, templates in plan['old_items'].items():
			if key not in plan['grouped_entries']:
				# NOTE: archive (not unlink) so past attendance-taking history is preserved. Archives
				# every duplicate sharing this key, not just one.
				templates.action_archive()
			else:
				# NOTE: the subject+group combo persists across imports, but its actual weekly times
				# (and possibly its classroom) may have changed since the last import — archive (not
				# unlink, same history-preserving reasoning as above) the stale lines, recreated by
				# '_write_schedule_sync' from the freshly imported entries, mirroring
				# resource.calendar.apply_schedule_changes's own unlink-then-recreate approach for the
				# same underlying problem. If more than one active template shares this key (duplicates
				# from past imports), only 'templates[0]' survives (see '_write_schedule_sync') — fully
				# archive the rest here rather than just their schedule lines.
				survivor, duplicates = templates[0], templates[1:]
				if duplicates:
					duplicates.action_archive()
				survivor.attendance_schedule_ids.action_archive()

	def _write_schedule_sync(self, plan):
		"""Second pass: refresh persisting templates and create genuinely new ones from 'plan'."""
		old_items = plan['old_items']
		grouped_entries = plan['grouped_entries']

		for key, templates in old_items.items():
			if key in grouped_entries:
				# NOTE: same survivor as '_archive_stale_schedule_sync' picked (same recordset, same
				# order) — any other duplicate sharing this key was already fully archived there.
				survivor = templates[0]
				first_group = self.env['ems.group'].browse(grouped_entries[key][0]["group_ids"][0])
				survivor.write({
					'space_id': first_group.space_id.id,
					'attendance_schedule_ids': self._schedule_lines(grouped_entries[key], first_group.space_id.id),
				})

		# NOTE: offset by the count of every template ever created (not just this batch), so
		# consecutive sync calls keep rotating through the palette instead of every batch
		# independently restarting at index 0 - which, since most batches create only one new
		# template, would otherwise leave nearly every template the same color (see the "all red"
		# issue this replaced). Includes archived records so the rotation never goes backwards.
		color_offset = self.with_context(active_test=False).search_count([])
		templates = dict()
		for key, group_entries in grouped_entries.items():
			if key in old_items:
				continue
			# TODO: define default start and end date for subjects within settings.
			first_group = self.env['ems.group'].browse(group_entries[0]["group_ids"][0])
			templates[key] = {
				'start_date': plan['start_date'],
				'end_date': plan['end_date'],
				'color': TEMPLATE_COLOR_PALETTE[(color_offset + len(templates)) % len(TEMPLATE_COLOR_PALETTE)],
				'teacher_ids': [(6, 0, plan['teachers'].ids)],
				'subject_id': group_entries[0]["subject_id"],
				'group_ids': [(6, 0, group_entries[0]["group_ids"])],
				'level_id': first_group.level_id.id,
				'study_id': first_group.study_id.id,
				'space_id': first_group.space_id.id,
				'attendance_schedule_ids': self._schedule_lines(group_entries, first_group.space_id.id),
			}

		new_templates = self.env['ems.attendance_template'].create(list(templates.values()))
		for template in new_templates:
			template.fill_students()