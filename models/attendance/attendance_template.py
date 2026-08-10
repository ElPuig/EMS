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
	_inherit = ['ems.base', 'ems.hex_color_mixin', 'mail.thread', 'mail.activity.mixin', 'ems.attendance_mixin']

	start_date = fields.Date(string="Start date", required=True)
	end_date = fields.Date(string="End date", required=True)
	color = fields.Char(string="Color", default="#3A8DDE", help="Free-pick display color, used to tell templates apart in the list view.")
	teacher_ids = fields.Many2many(string="Teachers", comodel_name="hr.employee", relation="ems_attendance_template_teacher_rel", domain="[('employee_type', '=', 'teacher')]", required=True, default=lambda self: self._default_teacher_ids())
	# NOTE: not required — a reinforcement ems.group (group_type == 'reinforcement') has no study
	# of its own, so a template built from one (see '_write_schedule_sync') leaves it empty.
	# Many2many since 2026-08-05: group_ids already allows several groups sharing one template
	# (co-teaching), and different groups can belong to different studies - a single study_id
	# couldn't represent that. 'level_id' was dropped entirely the same day: it never carried any
	# information study_ids/group_ids didn't already imply, and had zero real uses beyond
	# narrowing this same dropdown (see plans/attendance_template_multi_study.md).
	study_ids = fields.Many2many(string="Studies", comodel_name="ems.study")
	group_ids = fields.Many2many(string="Groups", comodel_name="ems.group", domain="[('study_id', 'in', study_ids)]")
	subject_id = fields.Many2one(
		string="Subject", comodel_name="ems.subject", domain="[('id', 'in', allowed_subject_ids)]", required=True)
	# NOTE: non-stored, view-domain-only - the subjects valid for EVERY selected study
	# (intersection), not just any one of them. A plain domain can't express an "ALL" condition
	# directly against a Many2many, so this is computed in Python and the view filters against it.
	allowed_subject_ids = fields.Many2many(string="Allowed subjects", comodel_name="ems.subject", compute="_compute_allowed_subject_ids", store=False)
	# NOTE: no longer the authoritative room - each 'ems.attendance_schedule' line carries its own
	# 'space_id' since 2026-08-01 (a one-off room reassignment can diverge from the group's
	# default). This field is now only a default/seed value: a schedule line created by hand
	# through this template's own form already defaults from it via Odoo's own 'default_<field>'
	# context convention (see the 'default_space_id' context on 'attendance_schedule_ids' in
	# views/attendance/attendance_template/form.xml) - no bespoke onchange needed for this.
	space_id = fields.Many2one(string="Session's default space", comodel_name="ems.space", required=True)

	# NOTE: 'copy=True' explicit - Odoo's One2many field defaults to 'copy=False' (fields.py:
	# "o2m are not copied by default"), which is normally the right call, but 'action_new_version'/
	# '_write_or_new_version' (ems.attendance_mixin) both rely on 'copy()' cascading these lines
	# onto the fresh clone (see their own docstrings) - without this, a correction on a template
	# WITH real session history silently produced a clone with NO schedule lines at all, undetected
	# because the only test exercising this path never asserted the clone actually had one. Each
	# line's own 'attendance_session_ids' stays 'copy=False' regardless (session history is never
	# duplicated either way).
	attendance_schedule_ids = fields.One2many(string="Sessions", comodel_name="ems.attendance_schedule", inverse_name="attendance_template_id", copy=True)
	student_ids = fields.Many2many(string="Students", comodel_name="res.partner", domain="[('contact_type', '=', 'student')]")

	# NOTE: this field is computed when loaded within a form or list
	read_only_user = fields.Boolean(default=lambda self:self._get_read_only_user(), store=False)

	# NOTE: drives the 'identity fields' lock (subject_id/group_ids/teacher_ids) - once real
	# attendance has been taken under this template, those fields must never change in place;
	# use action_new_version() (clone + archive) instead. Deliberately keyed on real usage, not
	# on the template merely existing, so a harmless typo can still be fixed by hand before any
	# attendance was ever taken.
	has_sessions = fields.Boolean(string="Has sessions", compute="_compute_has_sessions")

	@api.depends('attendance_schedule_ids.attendance_session_ids')
	def _compute_has_sessions(self):
		for template in self:
			template.has_sessions = bool(template.attendance_schedule_ids.attendance_session_ids)

	@api.depends('study_ids')
	def _compute_allowed_subject_ids(self):
		# NOTE: 'study_ids.ids' (not 'study_ids[0].id' etc.) - inside a still-unsaved form (this
		# compute must also run live in the form, not just once the template is saved),
		# 'study_ids' holds NewId-wrapped records; a NewId's own '.id' is a placeholder object,
		# not the real database id a search() domain needs, but the recordset's own '.ids'
		# correctly resolves each one back to its real origin id.
		for template in self:
			study_ids = template.study_ids.ids
			if not study_ids:
				template.allowed_subject_ids = self.env['ems.subject']
				continue
			subjects = self.env['ems.subject'].search([('study_ids', 'in', study_ids[0])])
			for study_id in study_ids[1:]:
				subjects &= self.env['ems.subject'].search([('study_ids', 'in', study_id)])
			template.allowed_subject_ids = subjects

	def action_new_version(self):
		"""Corrects a locked template's identity fields (subject_id/group_ids/study_ids/
		teacher_ids - see 'has_sessions') without disturbing its already-taken attendance history:
		archives the whole template (this model's own action_archive() override cascades to every
		schedule line too) and clones it - the copy starts with no session history, so every field
		is freely editable again. Already-taken sessions stay linked to the archived original,
		permanently accurate. A thin wrapper over 'ems.attendance_mixin's shared
		'_write_or_new_version()' (called with no field overrides, since this button only exists to
		unlock the record for a subsequent manual edit, not to apply a value itself) - the same
		method the schedule-sync pipeline uses to decide between updating in place and
		archiving+recreating. Always takes the archive+clone branch here in practice, since the view
		only shows this button once 'has_sessions' is already True. Archiving BEFORE copying
		(handled inside '_write_or_new_version') matters because copying while the original's lines
		are still active would collide with the clone's own identical lines via check_overlap - see
		'ems.attendance_schedule.action_new_version's own docstring for the same reasoning at the
		line level."""
		self.ensure_one()
		new_template = self._write_or_new_version({})
		# NOTE: 'copy()'s own o2m cascade (inside '_write_or_new_version') copies each schedule
		# line's CURRENT field values, 'active' included - since the source lines were just
		# archived by that same call, the freshly created lines would otherwise silently come back
		# archived too. 'with_context(active_test=False)' is required here: a default read of this
		# O2M already filters out the (still inactive at this point) copied lines, so a plain
		# '.attendance_schedule_ids.action_unarchive()' would silently operate on an empty
		# recordset and never actually flip them back to active.
		new_template.with_context(active_test=False).attendance_schedule_ids.action_unarchive()
		return {
			'type': 'ir.actions.act_window',
			'res_model': 'ems.attendance_template',
			'res_id': new_template.id,
			'view_mode': 'form',
			'target': 'current',
		}

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

	@api.constrains('subject_id', 'study_ids')
	def _check_subject_valid_for_all_studies(self):
		# NOTE: the view's own domain (allowed_subject_ids) already keeps a user from picking an
		# invalid subject in practice - this is the real, server-side guarantee behind it.
		for template in self:
			if template.study_ids and template.subject_id not in template.allowed_subject_ids:
				missing_studies = template.study_ids.filtered(
					lambda study: template.subject_id not in study.subject_ids)
				raise ValidationError(_(
					"The subject '%(subject)s' is not available in the following selected "
					"studies: %(studies)s (template for group(s) %(groups)s, teacher(s) "
					"%(teachers)s). Either remove those studies from this template or pick a "
					"subject taught in all of them."
				) % {
					'subject': template.subject_id.display_name,
					'studies': ", ".join(missing_studies.mapped('display_name')),
					'groups': ", ".join(template.group_ids.mapped('display_name')) or _("(none)"),
					'teachers': ", ".join(template.teacher_ids.mapped('display_name')) or _("(none)"),
				})

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
		as another live edit (see '_reconcile_teacher_groups'). NOT used by the XML importer any more
		(see 'sync_from_schedule_batch_fresh_import' below) - a live edit genuinely describes that one
		teacher's ENTIRE schedule right now, which is exactly the assumption this path relies on."""
		self.sync_from_schedule_batch([(teacher, entries)], start_date=start_date)

	def sync_from_schedule_batch(self, teacher_entries, start_date=None):
		"""Sync one or several teachers at once **assuming each submitting teacher's entries describe
		their ENTIRE schedule right now** — used by sync_from_schedule() for the Schedule tab's live,
		single-teacher edit. Do NOT call this from the XML importer (see
		'sync_from_schedule_batch_fresh_import' instead) - a batch file only ever describes ONE SLICE
		of the centre's schedule (e.g. one department), and reusing this method there silently archived
		a teacher's OTHER, already-imported department as "dropped" the moment they appeared in a
		second file (found 2026-08-01: two incremental department imports sharing one teacher wiped the
		first department's schedule for that teacher — see '_reconcile_teacher_groups's own
		'touched_templates' step, which is exactly the correct behavior for a live edit and exactly
		wrong for a partial batch import).

		'teacher_entries' is a list of (teacher, entries) pairs. First reconciles co-teaching:
		'_reconcile_teacher_groups' merges the freshly submitted entries against whatever ALREADY
		exists in the DB for the same (subject, group-set) combinations, at the exact (weekday,
		hour_from, hour_to) slot level, producing one (teachers, entries) group per distinct
		combination of subject+groups+exact-teacher-set — see that method's docstring for the full
		reasoning, including how a solo edit by one teacher can retroactively split another teacher's
		existing template.

		Then archives every resulting group's stale schedule lines FIRST, across the WHOLE batch,
		before writing ANY group's fresh ones — doing this one group at a time can raise a false
		check_overlap() collision when two groups share a classroom: the first group's fresh line would
		be checked against the second group's still-active STALE line, since that second group hasn't
		been re-synced yet at that point."""
		merged_groups, vacated = self._reconcile_teacher_groups(teacher_entries)
		vacated.action_archive()
		self._run_schedule_sync_plans(merged_groups, start_date=start_date)

	def sync_from_schedule_batch_fresh_import(self, teacher_entries, start_date=None):
		"""The XML importer's own batch write path - use this, never 'sync_from_schedule_batch', from
		'ems.working_schedules_import_wizard'. 'teacher_entries' is a list of (teacher, entries) pairs,
		same shape as the method above.

		The difference: '_reconcile_fresh_import' only ever looks at (subject, group-set)
		combinations actually present in THIS batch's own entries - it never considers any OTHER
		template a submitting teacher already owns for a combination this file doesn't mention, so
		nothing is ever silently archived as "dropped". A batch file only ever describes part of the
		centre's schedule (one department, one level...), imported incrementally alongside others over
		time, and a teacher can legitimately appear in more than one - unlike the Schedule tab's live
		editor, where a single submission genuinely IS that one teacher's whole schedule right now.

		Still correctly merges legitimate co-teaching with an EXTERNAL teacher's already-active
		session for the exact same (subject, group-set, slot) - see '_reconcile_fresh_import'. A
		genuine room conflict (different subject/group, same space/time) is expected to already have
		been caught by 'classify_external_conflicts' before this is ever called."""
		merged_groups, vacated = self._reconcile_fresh_import(teacher_entries)
		vacated.action_archive()
		self._run_schedule_sync_plans(merged_groups, start_date=start_date)

	def _run_schedule_sync_plans(self, merged_groups, start_date=None):
		"""Shared archive-then-write pass for both batch sync entry points above - see
		'sync_from_schedule_batch' for why the archive phase must run for every group before the write
		phase for any of them."""
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

	def _reconcile_fresh_import(self, teacher_entries):
		"""Like '_reconcile_teacher_groups' above, for the XML importer's own batch write path
		('sync_from_schedule_batch_fresh_import') instead of the Schedule tab's live single-teacher
		edit. Deliberately does NOT include that method's 'touched_templates' step (every OTHER active
		template a submitting teacher already owns, regardless of subject/group): a batch file only
		ever describes ONE SLICE of the centre's schedule, imported incrementally alongside others
		(e.g. one department today, another next week) - a teacher shared between two such files must
		never have the first file's combo silently treated as "dropped" just because the second file
		submits something for them. Only combinations actually present in THIS batch's own entries are
		ever reconsidered here; anything else a submitting teacher owns is left completely untouched
		(found 2026-08-01: reusing '_reconcile_teacher_groups' here wiped a shared teacher's
		already-imported department the moment a second department's file was imported).

		Still correctly merges legitimate co-teaching: if an EXTERNAL teacher (not in this batch)
		already holds the exact same (subject, group-set, slot) an entry submits now, that external
		teacher's slot is folded into the same resulting group exactly like
		'_reconcile_teacher_groups' does - the only thing missing here is the "also archive whatever
		this teacher used to teach but stopped submitting" half, which is precisely what must NOT
		happen for a partial batch import.

		Returns (merged, vacated), same shapes as '_reconcile_teacher_groups' - 'vacated' IS still
		needed here (found the hard way 2026-08-01: dropping it entirely broke co-teaching merges,
		since the external teacher's OLD solo template never got superseded/archived, leaving a
		duplicate that then collided with the new merged one via check_overlap's own same_teacher
		check). The key difference from '_reconcile_teacher_groups' is narrower than "no vacated at
		all": only a (subject, group-set) key that's ACTUALLY present in 'by_key_submitted' (i.e.
		mentioned by this batch, whether as a submitting teacher or as the external co-teacher being
		merged into) can ever produce a 'vacated' template - a combo this batch doesn't mention AT ALL
		never enters 'by_key_submitted' in the first place (no 'touched_templates' pre-scan), so it can
		never be vacated either."""
		submitting_teacher_ids = {teacher.id for teacher, _entries in teacher_entries}
		by_key_submitted = dict()
		for teacher, entries in teacher_entries:
			for entry in entries:
				if not entry.get('group_ids'):
					continue  # non-teaching entries carry no group, hence no co-teaching to reconcile
				key = (entry['subject_id'], tuple(sorted(entry['group_ids'])))
				by_key_submitted.setdefault(key, []).append((teacher, entry))

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
				# Teachers of this template NOT submitting THIS COMBO now: their slots are preserved
				# as-is, unless a submitting teacher lands on the exact same slot (merged below).
				untouched = template.teacher_ids.filtered(lambda teacher: teacher.id not in submitting_teacher_ids)
				if not untouched:
					continue  # every teacher of this template is (re-)submitting this same combo now
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
			# matches it EXACTLY (see '_reconcile_teacher_groups' for the full reasoning) - e.g. an
			# external teacher's solo template gets superseded here once co-teaching merges them into
			# a bigger teacher-set, and must be archived so the new group's own create()/write() below
			# doesn't collide with it via check_overlap's same_teacher check.
			result_teacher_sets = set(by_teacher_set.keys())
			for template in existing_templates:
				if frozenset(template.teacher_ids.ids) not in result_teacher_sets:
					vacated |= template

			for teacher_ids, slot_entries in by_teacher_set.items():
				merged.append((self.env['hr.employee'].browse(teacher_ids), slot_entries))
		return merged, vacated

	def classify_external_conflicts(self, teacher_entries):
		"""Given [(teacher, entries), ...] (same shape as sync_from_schedule_batch), find every
		currently active ems.attendance_schedule belonging to a teacher NOT part of this batch that
		overlaps (same space, weekday, time) with one of the new entries, and split the results into
		(co_teaching, space_conflicts):

		- co_teaching: same subject, sharing at least one group with the new entry (see
		  ems.attendance_schedule.is_co_teaching_with) — the SAME class session, now taught by more
		  than one teacher. Not an error: the batch importer leaves these alone and lets
		  sync_from_schedule_batch's own reconciliation (_reconcile_teacher_groups) fold the new
		  teacher into the same shared template, since it already merges any (subject, group-set)
		  combination touched by a submitting teacher against the full current DB state.
		- space_conflicts: anything else sharing the same space/time — a genuine double-booking the
		  importer cannot resolve on its own; the caller must stop and surface it instead of guessing.

		The XML importer never writes on top of an already-populated schedule for its own scope (see
		docs/en/developers/employees/working_schedule.md — groups are reused across academic years,
		but their attendance templates are archived by the course transition wizard before the next
		import), so an external overlap found here is always either legitimate co-teaching or a real
		problem to resolve, never something to archive automatically."""
		teacher_ids = {teacher.id for teacher, _entries in teacher_entries}
		co_teaching = self.env['ems.attendance_schedule']
		space_conflicts = self.env['ems.attendance_schedule']
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
				overlapping = candidates.filtered(
					lambda candidate, entry=entry: candidate.ranges_overlap(
						candidate.start_time, candidate.end_time, entry['hour_from'], entry['hour_to'])
				)
				for candidate in overlapping:
					same_subject_group = (
						candidate.attendance_template_id.subject_id.id == entry.get('subject_id')
						and set(candidate.attendance_template_id.group_ids.ids) & set(entry.get('group_ids') or [])
					)
					if same_subject_group:
						co_teaching |= candidate
					else:
						space_conflicts |= candidate
		return co_teaching, space_conflicts

	def find_self_conflicts(self, teacher_entries):
		"""Given [(teacher, entries), ...], find every currently active ems.attendance_schedule
		belonging to one of THESE SAME teachers that overlaps in weekday/time with one of their own
		new entries, but for a DIFFERENT (subject, group-set) combination - i.e. that one teacher
		double-booked across two separate imports (e.g. scheduled at the same time by two different
		departments' files). 'classify_external_conflicts' cannot see this: it only ever searches for
		OTHER teachers occupying the same space, and a self double-booking can happen in any two
		spaces, not necessarily the same one.

		A candidate sharing the (subject, group-set) combination with one of this same teacher's own
		submitted entries is never a conflict, however its time or space differs - that is just this
		exact combination being moved/updated in place, which '_reconcile_fresh_import' already
		handles correctly by refreshing the existing template's schedule lines.

		Note: this only catches conflicts against already-written DB data, i.e. across separate
		imports - it does not catch two overlapping entries for the same teacher within the single
		batch being submitted right now (a malformed source file), which still surfaces as a raw
		check_overlap ValidationError at write time."""
		conflicts = self.env['ems.attendance_schedule']
		for teacher, entries in teacher_entries:
			submitted_combos = {
				(entry['subject_id'], tuple(sorted(entry['group_ids'])))
				for entry in entries if entry.get('group_ids')
			}
			for entry in entries:
				if not entry.get('group_ids'):
					continue
				candidates = self.env['ems.attendance_schedule'].search([
					('weekday', '=', entry['dayofweek']),
					('attendance_template_id.teacher_ids', 'in', teacher.id),
				])
				overlapping = candidates.filtered(
					lambda candidate, entry=entry: candidate.ranges_overlap(
						candidate.start_time, candidate.end_time, entry['hour_from'], entry['hour_to'])
				)
				conflicts |= overlapping.filtered(
					lambda candidate: (
						candidate.attendance_template_id.subject_id.id,
						tuple(sorted(candidate.attendance_template_id.group_ids.ids)),
					) not in submitted_combos
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

		# NOTE: precompute the per-line breakdown for every persisting key ONCE here, so
		# '_archive_stale_schedule_sync' and '_write_schedule_sync' both read the exact same
		# match instead of each recomputing it independently and risking disagreement.
		line_sync = dict()
		for key, templates in old_items.items():
			if key in grouped_entries:
				first_group = self.env['ems.group'].browse(grouped_entries[key][0]["group_ids"][0])
				line_sync[key] = self._match_schedule_lines(templates[0], grouped_entries[key], first_group.space_id.id)

		return {
			'teachers': teachers,
			'old_items': old_items,
			'grouped_entries': grouped_entries,
			'line_sync': line_sync,
			'start_date': start_date,
			'end_date': end_date,
		}

	def _match_schedule_lines(self, survivor, group_entries, space_id):
		"""Matches 'survivor's current active schedule lines against 'group_entries' (this sync's
		freshly reconciled slots for the same key) by (weekday, start_time, end_time) - a line's own
		identity within a template. Returns {'stale_lines', 'lines_to_rewrite', 'fresh_entries'}:
		- 'stale_lines': lines with no matching entry at all - genuinely gone, always archived
		  outright regardless of 'has_sessions' (archiving is never locked, only in-place field
		  edits are - see 'ems.attendance_mixin').
		- 'lines_to_rewrite': (line, entry) pairs whose matched entry wants a different 'space_id' -
		  handled per 'has_sessions' by the two callers below (write in place, or archive+recreate).
		- 'fresh_entries': entries with no matching existing line - a genuinely new schedule line.
		A line whose matched entry is identical in every synced field (including 'space_id') is left
		out of all three entirely - not even a no-op archive+recreate."""
		lines_by_slot = {(line.weekday, line.start_time, line.end_time): line for line in survivor.attendance_schedule_ids}
		matched_slots = set()
		lines_to_rewrite = []
		fresh_entries = []
		for entry in group_entries:
			slot = (entry["dayofweek"], entry["hour_from"], entry["hour_to"])
			line = lines_by_slot.get(slot)
			if line is None:
				fresh_entries.append(entry)
				continue
			matched_slots.add(slot)
			if line.space_id.id != entry.get("space_id", space_id):
				lines_to_rewrite.append((line, entry))
		stale_lines = survivor.attendance_schedule_ids.filtered(
			lambda line: (line.weekday, line.start_time, line.end_time) not in matched_slots)
		return {'stale_lines': stale_lines, 'lines_to_rewrite': lines_to_rewrite, 'fresh_entries': fresh_entries}

	def _schedule_line_vals(self, entry, space_id):
		"""Plain create/write vals for one schedule line built from a parsed XML/grid entry -
		'space_id' is the group-derived fallback - an entry carrying its own 'space_id' (e.g. a
		room reassignment resolved by the import wizard) always takes priority over it, so a
		one-off divergence from the group's default room survives this sync instead of being
		silently overwritten."""
		return {
			'start_time': entry["hour_from"],
			'end_time': entry["hour_to"],
			'weekday': entry["dayofweek"],
			'space_id': entry.get("space_id", space_id),
		}

	def _schedule_lines(self, group_entries, space_id):
		"""(0, 0, {...}) create-commands for a BRAND NEW template's 'attendance_schedule_ids' -
		see '_schedule_line_vals' for the shared per-entry shape."""
		return [(0, 0, self._schedule_line_vals(entry, space_id)) for entry in group_entries]

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
				# NOTE: if more than one active template shares this key (duplicates from past
				# imports), only 'templates[0]' survives (see '_write_schedule_sync') — fully
				# archive the rest here rather than just their schedule lines.
				survivor, duplicates = templates[0], templates[1:]
				if duplicates:
					duplicates.action_archive()
				line_sync = plan['line_sync'][key]
				line_sync['stale_lines'].action_archive()
				# NOTE: a changed line only needs archiving here if it has real session history -
				# 'has_sessions' doesn't depend on 'active', so '_write_schedule_sync' below reads
				# the same predicate independently without needing to track "was archived" state.
				for line, _entry in line_sync['lines_to_rewrite']:
					if line.has_sessions:
						line.action_archive()

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
				line_sync = plan['line_sync'][key]
				new_lines = [
					(0, 0, self._schedule_line_vals(entry, first_group.space_id.id))
					for entry in line_sync['fresh_entries']
				]
				for line, entry in line_sync['lines_to_rewrite']:
					vals = self._schedule_line_vals(entry, first_group.space_id.id)
					if line.has_sessions:
						# NOTE: already archived in '_archive_stale_schedule_sync' above - create
						# its replacement here, same shape as any other fresh line.
						new_lines.append((0, 0, vals))
					else:
						# NOTE: left untouched (not archived) in the pass above - safe to update in
						# place, same "no sessions yet" reasoning as
						# 'ems.attendance_mixin._write_or_new_version'.
						line.write(vals)
				survivor.write({
					'space_id': first_group.space_id.id,
					'attendance_schedule_ids': new_lines,
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
			groups = self.env['ems.group'].browse(group_entries[0]["group_ids"])
			first_group = groups[:1]
			templates[key] = {
				'start_date': plan['start_date'],
				'end_date': plan['end_date'],
				'color': TEMPLATE_COLOR_PALETTE[(color_offset + len(templates)) % len(TEMPLATE_COLOR_PALETTE)],
				'teacher_ids': [(6, 0, plan['teachers'].ids)],
				'subject_id': group_entries[0]["subject_id"],
				'group_ids': [(6, 0, group_entries[0]["group_ids"])],
				# NOTE: every involved group's own study, not just the first one's - a template can
				# cover groups from different studies (co-teaching/"desdoble" across studies).
				'study_ids': [(6, 0, groups.mapped('study_id').ids)],
				'space_id': first_group.space_id.id,
				'attendance_schedule_ids': self._schedule_lines(group_entries, first_group.space_id.id),
			}

		new_templates = self.env['ems.attendance_template'].create(list(templates.values()))
		for template in new_templates:
			template.fill_students()