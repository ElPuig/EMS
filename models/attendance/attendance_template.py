# -*- coding: utf-8 -*-

from datetime import date, datetime

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from ..shared.attendance_mixin import EMS_BYPASS_TEMPLATE_LOCK_KEY

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

	# NOTE: 'copy=True' explicit - Odoo's One2many field defaults to 'copy=False' (fields.py:
	# "o2m are not copied by default"), which is normally the right call, but
	# '_write_or_new_version' (ems.attendance_mixin) relies on 'copy()' cascading these lines onto
	# the fresh clone (see its own docstring) - without this, a correction on a template WITH real
	# session history silently produced a clone with NO schedule lines at all, undetected because
	# the only test exercising this path never asserted the clone actually had one. Each line's own
	# 'attendance_session_ids' stays 'copy=False' regardless (session history is never duplicated
	# either way).
	attendance_schedule_ids = fields.One2many(string="Sessions", comodel_name="ems.attendance_schedule", inverse_name="attendance_template_id", copy=True)

	# NOTE: this field is computed when loaded within a form or list
	read_only_user = fields.Boolean(default=lambda self:self._get_read_only_user(), store=False)

	# NOTE: drives the 'identity fields' lock (subject_id/group_ids/teacher_ids) - once real
	# attendance has been taken under this template, those fields must never change in place. The
	# manual "Edit" button (action_new_version) that used to let an admin/teacher correct this by
	# hand was removed 2026-08-11 (see plans/calendar_driven_attendance_templates.md, point 3) -
	# obsolete now that the calendar is the only legitimate source of change; a correction happens
	# by editing the teacher's working schedule instead. Deliberately keyed on real usage, not
	# on the template merely existing, so a harmless typo can still be fixed by hand before any
	# attendance was ever taken.
	has_sessions = fields.Boolean(string="Has sessions", compute="_compute_has_sessions")

	@api.depends('attendance_schedule_ids.attendance_session_ids')
	def _compute_has_sessions(self):
		for template in self:
			template.has_sessions = bool(template.attendance_schedule_ids.attendance_session_ids)

	@api.depends('study_ids')
	def _compute_allowed_subject_ids(self):
		for template in self:
			template.allowed_subject_ids = template.study_ids._subjects_common_to_all()

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

	@api.constrains('teacher_ids', 'group_ids', 'subject_id', 'active')
	def _check_unique_teaching_assignment(self):
		"""No two ACTIVE templates may share the exact same (subject_id, teacher_ids-as-set,
		group_ids-as-set) triple - see plans/calendar_driven_attendance_templates.md, point 2.
		Deliberately EXACT-match, not "any group overlap": verified against this dev DB
		(2026-08-11) that a real, legitimate pattern already exists where the SAME teacher teaches
		the SAME subject to a group on its own AND to that group combined with another, in
		different templates with genuinely different (not identical) 'group_ids' sets - e.g. group
		A alone Monday, group B alone Tuesday, A+B together Wednesday. That's a real pedagogical
		"desdoble" pattern this data model can only express as separate templates (group_ids has
		no per-line override), not a duplicate to reject. A plain SQL UNIQUE can't express this
		either way since 'teacher_ids'/'group_ids' are Many2many - hence a Python check. The sync
		pipeline's own reconciliation (_reconcile_teacher_groups,
		'_plan_schedule_sync's own old_items keying) already normally prevents this exact-match
		case from happening in practice; this constraint is the explicit guard for the ONE path
		that bypasses it - a direct manual create()/write() through the UI or API."""
		for template in self:
			if not template.active:
				continue
			teacher_ids = frozenset(template.teacher_ids.ids)
			group_ids = frozenset(template.group_ids.ids)
			candidates = self.search([
				('id', '!=', template.id),
				('subject_id', '=', template.subject_id.id),
				('active', '=', True),
			])
			duplicate = candidates.filtered(
				lambda candidate: frozenset(candidate.teacher_ids.ids) == teacher_ids
				and frozenset(candidate.group_ids.ids) == group_ids
			)
			if duplicate:
				raise ValidationError(_(
					"An active template already exists for this exact teaching assignment "
					"(%(subject)s, teacher(s) %(teachers)s, group(s) %(groups)s) - correct it "
					"through the teacher's working schedule instead of creating a new one."
				) % {
					'subject': template.subject_id.display_name,
					'teachers': ", ".join(template.teacher_ids.mapped('display_name')),
					'groups': ", ".join(template.group_ids.mapped('display_name')),
				})

	@api.constrains("color")
	def _check_color_format(self):
		self._check_hex_color('color')

	@api.depends('subject_id', 'group_ids')
	def _compute_display_name(self):
		for template in self:
			groups = ", ".join(template.group_ids.mapped('name'))
			template.display_name = "%s (%s)" % (template.subject_id.display_name, groups)

	# NOTE: every field here except 'color' is an identity/logistics concern that only ever comes
	# from the teacher's calendar (see plans/calendar_driven_attendance_templates.md, point 3 and
	# its 2026-08-11 refinement) - 'active' was the original, narrower lock; extended to the rest
	# of the template's own fields after the developer found admin/teacher could still freely
	# rewrite 'teacher_ids'/'subject_id'/etc. directly, risking exactly the inconsistency-with-the-
	# calendar this whole design exists to prevent. 'space_id' was removed from the model entirely
	# rather than added here - it only ever existed as a default-value source for manually adding a
	# schedule line, itself no longer possible either (see ems.attendance_schedule's own lock).
	_LOCKED_FIELDS = {'active', 'teacher_ids', 'subject_id', 'group_ids', 'study_ids', 'start_date', 'end_date'}

	def write(self, vals):
		if (set(vals) & self._LOCKED_FIELDS) and not self.env.context.get(EMS_BYPASS_TEMPLATE_LOCK_KEY):
			raise UserError(_(
				"This can only change as a consequence of editing the teacher's working "
				"schedule - update the schedule instead of editing this template directly."
			))
		return super().write(vals)

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
		"""Sync a single teacher's schedule from 'entries' — the employee 'Schedule' tab's grid
		widget (a live mid-course edit) is the main caller, always with this teacher's ENTIRE
		current schedule. Internally delegates to sync_from_schedule_batch() wrapping its single
		(teacher, entries) pair, so a solo edit goes through the exact same co-teaching
		reconciliation as any other caller of that method (see '_reconcile_teacher_groups')."""
		self.sync_from_schedule_batch([(teacher, entries)], start_date=start_date)

	def sync_from_schedule_batch(self, teacher_entries, start_date=None):
		"""Sync one or several teachers at once **assuming each submitting teacher's entries describe
		their ENTIRE schedule right now**. Used by sync_from_schedule() for the Schedule tab's live,
		single-teacher edit, and by the XML importer
		(`ems.working_schedules_import_wizard._apply_import`) once it has finished writing this
		batch's calendar rows: `_write_teacher_schedule` writes each affected teacher's CORRECT
		final calendar state (respecting the wizard's own `import_mode` - see that method's own
		docstring), so reading it straight back
		(`hr.employee._teaching_entries_from_calendar()`) already reflects the teacher's whole
		current schedule, satisfying this method's own assumption by construction rather than by
		the caller having to hand-pick a scope. One reconciliation method now serves both callers -
		until 2026-09-02 the importer had its own separate, near-duplicate pair
		(`sync_from_schedule_batch_fresh_import`/`_reconcile_fresh_import`, deleted), built back
		when the importer's own calendar write couldn't yet be trusted to reflect the whole truth
		(see plans/calendar_pipeline_simplification.md for the fuller history).

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
		vacated.with_context(**{EMS_BYPASS_TEMPLATE_LOCK_KEY: True}).action_archive()
		self._run_schedule_sync_plans(merged_groups, start_date=start_date)
		self._link_calendar_attendance(merged_groups)

	def regenerate_all_from_calendars(self, teachers=None):
		"""Archive every active template outright, then rebuild an equivalent, fully calendar-backed
		set from scratch out of every teacher's CURRENT resource.calendar.attendance rows - see
		plans/calendar_driven_attendance_templates.md's "Production migration sequencing" section,
		step 1 (developer's own design, 2026-08-11). Deliberately does not try to classify old data
		as "orphan" vs. "legitimate" first (an earlier draft of this migration attempted exactly
		that, one exact-duplicate pair at a time, and hit a real double-booking conflict on its
		first production-snapshot test) - once the calendar is authoritative (points 1-4), archiving
		everything and resyncing from the same source of truth naturally reconstructs a clean,
		non-duplicated set, since 'sync_from_schedule_batch' groups by (subject, group-set,
		teacher-set) and can never produce two templates for the same exact combination by
		construction. A calendar row with a genuine, unresolved conflict (e.g. two different teachers
		double-booked in the same room) still raises via 'check_overlap', exactly like any other
		sync - a real data problem this must surface, never silently resolve (confirmed against this
		dev DB, 2026-08-11: 'Eric Bautista'/'Christian Escobar' both currently hold a Friday
		16:00-17:00 slot in the same room - a genuine pre-existing conflict this method would abort
		on if run unscoped here today).

		'teachers' (optional): scopes both the archive and the rebuild to this recordset only,
		instead of every teacher in the database - lets a caller (a test, or a future partial/
		admin-triggered regeneration) regenerate a known subset without touching or depending on
		every other teacher's real, unrelated schedule data. Defaults to every teacher with a real,
		non-framework 'resource_calendar_id' when not given - the real migration call site never
		passes this, since a production rollout genuinely means everyone.

		Safe to archive unconditionally: archiving never touches a template's real attendance-session
		history (see "Archiving never cascades to sessions" in
		docs/en/developers/attendance/attendance_schedule.md) - past attendance stays intact and
		queryable against the archived template, exactly like a normal correction.

		Intended to run once per invocation (e.g. from this version's own migration, right after
		module data reloads and before the Odoo service becomes reachable by any user) - the
		archive+rebuild is never actually visible as a service gap when run that way. An employee
		without a real working schedule loaded onto their calendar ends up with zero active
		templates, matching the new rule that a template only exists as a consequence of a real
		working schedule (see plans/calendar_driven_attendance_templates.md, point 3): this IS a
		breaking change for any teacher whose schedule was never (re)loaded - they will not be able
		to take attendance until it is.

		Returns a list of dicts describing every entry dropped by '_drop_unresolved_conflicts' (see
		that method) - callers (the migration, in particular) are expected to report this clearly so
		a human can review and fix the underlying calendars by hand; nothing here guesses which side
		was "really" the reinforcement teacher (developer's own call, 2026-08-11 - see
		plans/calendar_driven_attendance_templates.md).

		Also resyncs 'ems.teaching' for every teacher in scope, from the same calendar entries -
		added 2026-09-01 (see plans/course_transition_stale_teacher_assignments.md). Templates and
		teachings are two independent, parallel readers of the same calendar truth (see
		'ems_working_schedule.apply_schedule_changes', which already syncs both side by side for a
		live single-teacher edit) - this method previously only ever rebuilt the template side,
		leaving 'ems.teaching' to drift indefinitely stale for anyone it touched."""
		if teachers is None:
			teachers = self.env['hr.employee'].search([
				('employee_type', '=', 'teacher'),
				('resource_calendar_id', '!=', False),
				('resource_calendar_id.is_framework', '=', False),
			])

		self.search([
			('active', '=', True), ('teacher_ids', 'in', teachers.ids),
		]).with_context(**{EMS_BYPASS_TEMPLATE_LOCK_KEY: True}).action_archive()

		# ems.teaching is resynced for EVERY teacher in scope, not just those ending up with
		# 'teacher_entries' below - a teacher whose calendar has gone back to zero teaching
		# entries must still have their stale ems.teaching rows dropped (2026-09-01: this exact
		# gap - ems.teaching never resynced by this method at all - is what let a departed/
		# reassigned teacher's old teaching links (and, via ems.teaching.unlink()'s own tutor
		# cleanup, their group's stale tutor_id) survive indefinitely; see
		# plans/course_transition_stale_teacher_assignments.md). Uses the FULL entries (before
		# '_drop_unresolved_conflicts' below strips anything), since a room/slot conflict that
		# blocks TEMPLATE creation is not a reason to also deny the teacher genuinely still
		# teaches that subject/group.
		teacher_entries = []
		for teacher in teachers:
			entries = teacher._teaching_entries_from_calendar()
			self.env['ems.teaching'].sync_from_schedule(teacher, entries)
			if entries:
				teacher_entries.append((teacher, entries))

		teacher_entries, skipped = self._drop_unresolved_conflicts(teacher_entries)
		if teacher_entries:
			self.sync_from_schedule_batch(teacher_entries, start_date=fields.Date.today())

		# NOTE: scoped the same way as the archive step above - every currently active line
		# belonging to one of 'teachers' was, by construction, JUST created by the sync above (this
		# same set was archived a moment ago). Refilling from live enrollment here (rather than
		# trying to preserve whatever roster the archived lines happened to have) is deliberate: the
		# roster is meant to always reflect current enrollment, and this is the same mechanism a
		# teacher/admin would otherwise trigger by hand via "Reload students" on each line.
		self.env['ems.attendance_schedule'].search([
			('active', '=', True), ('attendance_template_id.teacher_ids', 'in', teachers.ids),
		]).fill_students()
		return skipped

	def _entry_dates_overlap(self, entry_a, entry_b):
		"""Mirrors 'ems.attendance_schedule.check_overlap's own template-date-range filter, at the
		entry-dict level (before any template exists to read dates from) - two entries whose own
		'date_from'/'date_to' (core Odoo's own field names on resource.calendar.attendance, see that
		model's own NOTE; plans/calendar_driven_attendance_templates.md's "Mid-course subject
		handoff" refinement) don't overlap were never going to collide once synced into templates
		either, so '_drop_unresolved_conflicts' must not treat them as a conflict. Falls back to the
		same full-course-year default '_plan_schedule_sync' itself uses when an entry carries no
		explicit dates, so an unset date range still compares consistently against an explicit one."""
		now = datetime.now()
		default_start, default_end = date(now.year, 9, 1), date(now.year + 1, 7, 1)
		start_a = entry_a.get('date_from') or default_start
		end_a = entry_a.get('date_to') or default_end
		start_b = entry_b.get('date_from') or default_start
		end_b = entry_b.get('date_to') or default_end
		return start_a <= end_b and end_a >= start_b

	def _drop_unresolved_conflicts(self, teacher_entries):
		"""Finds every pair of teaching entries in 'teacher_entries' (same shape
		'regenerate_all_from_calendars' builds: [(teacher, entries), ...]) that would collide - same
		room+weekday+overlapping time, different teacher - and are NOT legitimate co-teaching under
		'ems.attendance_schedule.is_co_teaching_with's own definition (same subject_id AND a shared
		group): a real, recurring pattern in this centre's data is a support/reinforcement teacher
		recorded under their OWN subject_id, physically present in the same room/slot as the group's
		main teacher (confirmed with the developer, 2026-08-11 - see
		plans/calendar_driven_attendance_templates.md) - which 'is_co_teaching_with' can't recognise
		since the subject genuinely differs. Deliberately does NOT widen 'is_co_teaching_with' itself
		(used by the general-purpose 'check_overlap', not just this one-time regeneration) - that
		would blunt its ability to catch the far more common REAL double-booking mistake (two
		unrelated teachers accidentally sharing a room/slot for the same group). Instead, since
		leaving BOTH sides in would make 'sync_from_schedule_batch' abort the whole batch on
		'check_overlap', one side of each unresolved pair is dropped here BEFORE the sync ever runs,
		so the batch completes and every OTHER entry still regenerates cleanly.

		Which side is dropped is arbitrary (whichever is reached second, in 'teachers'/'attendance_
		ids' iteration order) - deliberately no attempt to guess which one is "really" the
		reinforcement teacher (developer's own call: "la que creemos que es de refuerzo, o una de las
		dos sin más"). The dropped entry is not created at all (no template/schedule line, and the
		underlying resource.calendar.attendance row is untouched either way) - the caller is expected
		to report every skipped entry clearly (teacher, subject, slot, and what it conflicted with) so
		a human can review and fix it by hand via the Schedule tab, the same "breaking change, needs
		manual follow-up" contract already documented on this method for a teacher with no schedule
		at all.

		Returns (kept_teacher_entries, skipped) - 'skipped' is a list of
		{'teacher', 'entry', 'conflicts_with_teacher', 'conflicts_with_entry'} dicts."""
		flat = [
			(teacher, entry) for teacher, entries in teacher_entries for entry in entries
			if entry.get('group_ids')
		]

		dropped_ids = set()
		skipped = []
		for index, (teacher_a, entry_a) in enumerate(flat):
			if id(entry_a) in dropped_ids:
				continue
			for teacher_b, entry_b in flat[index + 1:]:
				if id(entry_b) in dropped_ids or teacher_a == teacher_b:
					continue
				if entry_a['space_id'] != entry_b['space_id'] or entry_a['dayofweek'] != entry_b['dayofweek']:
					continue
				if not self.env['ems.datetime_utils'].ranges_overlap(
					entry_a['hour_from'], entry_a['hour_to'], entry_b['hour_from'], entry_b['hour_to']
				):
					continue
				if not self._entry_dates_overlap(entry_a, entry_b):
					continue  # non-overlapping date ranges - never a conflict, see check_overlap's own filter
				if entry_a['subject_id'] == entry_b['subject_id'] and set(entry_a['group_ids']) & set(entry_b['group_ids']):
					continue  # legitimate co-teaching (is_co_teaching_with's own definition) - keep both
				dropped_ids.add(id(entry_b))
				skipped.append({
					'teacher': teacher_b, 'entry': entry_b,
					'conflicts_with_teacher': teacher_a, 'conflicts_with_entry': entry_a,
				})

		kept = []
		for teacher, entries in teacher_entries:
			remaining = [entry for entry in entries if id(entry) not in dropped_ids]
			if remaining:
				kept.append((teacher, remaining))
		return kept, skipped

	def _run_schedule_sync_plans(self, merged_groups, start_date=None):
		"""Shared archive-then-write pass for both batch sync entry points above - see
		'sync_from_schedule_batch' for why the archive phase must run for every group before the write
		phase for any of them."""
		plans = [self._plan_schedule_sync(teachers, entries, start_date=start_date) for teachers, entries in merged_groups]
		for plan in plans:
			self._archive_stale_schedule_sync(plan)
		for plan in plans:
			self._write_schedule_sync(plan)

	def _link_calendar_attendance(self, merged_groups):
		"""Points every teacher's resource.calendar.attendance row at the ems.attendance_schedule
		line it now represents (see plans/calendar_driven_attendance_templates.md, point 4, and
		docs/en/developers/attendance/attendance_schedule.md's own section on this field) - called
		right after '_run_schedule_sync_plans' writes the schedule lines for this same sync, using
		'merged_groups' (not the raw 'teacher_entries' a caller submitted) so an UNTOUCHED
		co-teacher whose slot survives, merged, still gets their own already-existing calendar row
		re-pointed at the new/updated line - the same reason '_run_schedule_sync_plans' itself
		reads 'merged_groups' rather than the raw submission.

		For each (teachers, entries) group, matches each entry's own (dayofweek, hour_from,
		hour_to) against that teacher's CURRENT resource.calendar.attendance rows (already
		rewritten by the same import/live-edit call that led here) to find the calendar row, then
		reuses 'find_schedule_lines_for_teaching' (ems.attendance_mixin) to find the schedule line
		it now maps to. Reusing that same inference here - rather than avoiding it - is deliberate:
		at this exact point the inference is trustworthy in a way a later, independent call never
		can be, since '_run_schedule_sync_plans' just consolidated/archived every stale or
		duplicate line for these exact entries, so there's nothing left to be ambiguous about. If a
		match is still ambiguous ('!= 1' line, or no calendar row at all - e.g. a test that calls
		sync_from_schedule* directly without first writing anything onto the calendar, see
		tests/test_attendance_template.py) the FK is simply left as-is rather than guessed - same
		"leave it blank rather than guess" convention '_backfill_calendar_employee_and_course'
		(migrations/18.0.0.22.0/post-migrate.py) already established for this same model."""
		for teachers, entries in merged_groups:
			for teacher in teachers:
				calendar_attendances = teacher.resource_calendar_id.attendance_ids
				for entry in entries:
					calendar_attendance = calendar_attendances.filtered(
						lambda attendance, entry=entry: (
							attendance.dayofweek == entry['dayofweek']
							and attendance.hour_from == entry['hour_from']
							and attendance.hour_to == entry['hour_to']
						)
					)
					if not calendar_attendance:
						continue
					subject = self.env['ems.subject'].browse(entry['subject_id'])
					groups = self.env['ems.group'].browse(entry['group_ids'])
					lines = self.env['ems.attendance_schedule'].find_schedule_lines_for_teaching(
						teacher, subject, groups, entry['dayofweek'], entry['hour_from'], entry['hour_to'])
					if len(lines) == 1:
						calendar_attendance.attendance_schedule_id = lines.id

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
		exact combination being moved/updated in place, which '_reconcile_teacher_groups' already
		handles correctly by refreshing the existing template's schedule lines.

		Called from 'ems.working_schedules_import_wizard._apply_import' as a last-resort safety net
		only (2026-09-02) - the normal path already resolves this same kind of clash interactively,
		earlier, on the 'db_conflicts' screen (`_find_external_conflicts`'s own 'self_candidates'
		branch, defaulting to the new import winning); this only ever fires for a genuine race (the
		DB changed after that screen ran), not the everyday case. **Only called in 'combine' mode**
		(2026-09-06) - in 'replace' mode this method's own read of 'ems.attendance_schedule' is
		guaranteed stale at this point in the flow (not yet brought in sync with the calendar write
		that already happened), so any hit would be a false positive, not a genuine race - see the
		call site's own comment in '_apply_import'.

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
		can run the archive phase for every group before the write phase for any of them.

		'entries' is already reconciled for a single (subject, group-set, teacher-set) key at this
		point (see 'sync_from_schedule_batch*'), so every entry in it shares the same identity - an
		explicit 'date_from'/'date_to' on the FIRST entry (core Odoo's own field names on
		'resource.calendar.attendance', see that model's own NOTE; plans/
		calendar_driven_attendance_templates.md's "Mid-course subject handoff" refinement) wins over
		the caller-supplied default, same "first entry/group wins" convention already used for
		'space_id' elsewhere in this file - a calendar block explicitly scoped to part of the year is
		what lets two different subjects share the exact same weekday/time/room slot without colliding
		(ems.attendance_schedule.check_overlap already excludes non-overlapping template date ranges
		from its own candidates). Entry dict key matches the raw cell/DB field name directly, same
		convention already used for 'dayofweek'/'hour_from'/'hour_to'/'space_id' - not a separate
		'start_date'/'end_date' naming, so a live-edit entry (built straight from the JS grid's own
		cell dicts, see 'apply_schedule_changes') and a regenerate_all_from_calendars() entry (read
        straight off an 'ems.attendance_schedule' ORM record) both carry the SAME key without either
		needing a translation step."""
		now = datetime.now()
		entry_dates = entries[0] if entries else {}
		start_date = entry_dates.get('date_from') or start_date or datetime(now.year, 9, 1)
		end_date = entry_dates.get('date_to') or datetime(now.year + 1, 7, 1)

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
				templates.with_context(**{EMS_BYPASS_TEMPLATE_LOCK_KEY: True}).action_archive()
			else:
				# NOTE: if more than one active template shares this key (duplicates from past
				# imports), only 'templates[0]' survives (see '_write_schedule_sync') — fully
				# archive the rest here rather than just their schedule lines.
				survivor, duplicates = templates[0], templates[1:]
				if duplicates:
					duplicates.with_context(**{EMS_BYPASS_TEMPLATE_LOCK_KEY: True}).action_archive()
				line_sync = plan['line_sync'][key]
				line_sync['stale_lines'].with_context(**{EMS_BYPASS_TEMPLATE_LOCK_KEY: True}).action_archive()
				# NOTE: a changed line only needs archiving here if it has real session history -
				# 'has_sessions' doesn't depend on 'active', so '_write_schedule_sync' below reads
				# the same predicate independently without needing to track "was archived" state.
				for line, _entry in line_sync['lines_to_rewrite']:
					if line.has_sessions:
						line.with_context(**{EMS_BYPASS_TEMPLATE_LOCK_KEY: True}).action_archive()

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
						# its replacement here, same shape as any other fresh line. Carries the
						# archived line's OWN roster forward explicitly - this is a room-only
						# correction (see 'has_sessions'), not a fresh slot, so the student roster
						# must survive it untouched rather than starting empty (see
						# plans/calendar_driven_attendance_templates.md, point 1).
						new_lines.append((0, 0, {**vals, 'student_ids': [(6, 0, line.student_ids.ids)]}))
					else:
						# NOTE: left untouched (not archived) in the pass above - safe to update in
						# place, same "no sessions yet" reasoning as
						# 'ems.attendance_mixin._write_or_new_version'. 'student_ids' is not in
						# 'vals' at all here, so the line's own roster is naturally untouched too.
						line.with_context(**{EMS_BYPASS_TEMPLATE_LOCK_KEY: True}).write(vals)
				# NOTE: sudo() - 'new_lines' contains (0, 0, {...}) create commands, and create() is
				# revoked for every group on ems.attendance_schedule (see this same lock refinement) -
				# a schedule line only ever comes into existence as a consequence of this sync.
				survivor.with_context(**{EMS_BYPASS_TEMPLATE_LOCK_KEY: True}).sudo().write({
					'attendance_schedule_ids': new_lines,
				})
				# NOTE: only the genuinely NEW slots ('fresh_entries') need fill_students() - a
				# rewritten line (has_sessions or not) already carries or keeps its own roster
				# untouched above, and blindly filling every line here would silently overwrite a
				# teacher's manual per-line roster customization on every resync, defeating the
				# whole point of point 1 in plans/calendar_driven_attendance_templates.md.
				fresh_slots = {(entry["dayofweek"], entry["hour_from"], entry["hour_to"]) for entry in line_sync['fresh_entries']}
				if fresh_slots:
					survivor.attendance_schedule_ids.filtered(
						lambda line, fresh_slots=fresh_slots: (line.weekday, line.start_time, line.end_time) in fresh_slots
					).fill_students()

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
				'attendance_schedule_ids': self._schedule_lines(group_entries, first_group.space_id.id),
			}

		# NOTE: sudo() - create() is revoked for every group on ems.attendance_template (see
		# plans/calendar_driven_attendance_templates.md, point 3): a template only ever comes into
		# existence as a consequence of this sync, never directly, regardless of which user (even
		# an admin) triggered the schedule edit/import that led here.
		new_templates = self.env['ems.attendance_template'].sudo().create(list(templates.values()))
		# NOTE: every line of a BRAND NEW template is itself brand new - see
		# plans/calendar_driven_attendance_templates.md, point 1.
		new_templates.attendance_schedule_ids.fill_students()