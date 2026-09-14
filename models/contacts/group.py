# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import RedirectWarning, ValidationError

class EmsGroup(models.Model):
	_name = "ems.group"
	_description = "Groups: Where the students are assigned to."
	_inherit = ["mail.thread", "mail.activity.mixin"]
	_order = "name"

	active = fields.Boolean(default=True, help="A group that won't be used this course but may come back in a "
		"future one (e.g. a cycle not running this year) should be archived instead of deleted, so it can be "
		"reactivated later instead of being recreated as a duplicate.")
	group_type = fields.Selection(
		selection=[('main', 'Main'), ('reinforcement', 'Reinforcement')],
		string="Group Type", required=True, default="main",
		help="Main: the group a student is enrolled in (main_group_id), with a tutor, a delegate and a single study/level. "
			"Reinforcement: appears in the teaching schedule like any other group, but has no tutor/delegate and can mix "
			"students from different main groups and studies.")
	course = fields.Integer(string="Course")
	acronym = fields.Char(string="Acronym")
	external_id = fields.Char(string="External ID", help="Esfera (SAGA) group code, e.g. 'ESO LOEM101'.")
	name = fields.Char(string="Name", compute="_compute_name", store=True, readonly=False) #should not be edited manually for 'main' groups
	notes = fields.Text(string="Notes")

	level_id = fields.Many2one(string='Level', comodel_name='ems.level')
	study_id = fields.Many2one(string="Study", comodel_name="ems.study")
	tutor_id = fields.Many2one(string="Tutor", comodel_name="hr.employee", domain="[('employee_type', '=', 'teacher')]")

	delegate_id = fields.Many2one(string="Delegate", comodel_name="res.partner", domain="[('contact_type', '=', 'student'), ('main_group_id', '=', id)]")
	space_id = fields.Many2one(string="Reference classroom", comodel_name="ems.space")

	main_student_ids = fields.One2many(string="Students", comodel_name="res.partner", inverse_name="main_group_id", domain="[('contact_type', '=', 'student')]")
	enrolled_student_ids = fields.Many2many(string="Enrolled", comodel_name="res.partner", compute="_compute_enrolled_student_ids")
	enrollment_view_ids = fields.One2many(string="Enrollment", comodel_name="ems.enrollment_view", inverse_name="group_id", compute="_compute_enrollment_ids") # Contains the same data as enrolled_student_ids but filtered for the current group (sadly, it cannot be filtered on view...)
	shift = fields.Selection(selection=[('morning', 'Morning'),('afternoon', 'Afternoon'),],string="Shift",help="Morning or afternoon shift for this group.")
	# NOTE: issue #405 - see docs/en/developers/contacts/group.md's "Classroom change propagation"
	# section. Counts this group's 'resource.calendar.attendance' rows still flagged
	# 'space_pending_group_sync' (a room collision write() couldn't resolve on its own when the
	# group's own classroom last changed) - drives a persistent banner on the form with a button
	# opening 'ems.group_classroom_change_wizard', instead of a one-shot dialog that could be missed.
	pending_classroom_conflict_count = fields.Integer(string="Pending classroom conflicts", compute="_compute_pending_classroom_conflict_count")
	# NOTE: last deferred follow-up of issue #405 - see docs/en/developers/contacts/group.md's
	# "Classroom drift suggestion" section. 'space_id' can silently drift from where the group
	# actually meets (a collision gets resolved elsewhere but nobody updates the group's own
	# field) - this suggests the correct room whenever the CURRENT one has zero real teaching
	# hours. Computed, not stored (same reasoning as 'pending_classroom_conflict_count' above -
	# the real dependency runs through 'resource.calendar.attendance.group_ids', a reverse M2M
	# that @api.depends can't express cleanly); 'search=' is what still makes it usable in a list
	# filter despite not being stored - same pattern as 'ems.study.uses_enrollment_flow'.
	suggested_space_id = fields.Many2one(
		string="Suggested classroom", comodel_name="ems.space",
		compute="_compute_suggested_space_id", search="_search_suggested_space_id")
	# NOTE: issue #446 - same gate as 'hr.employee.can_edit_schedule' (drives the Edit/Import/New
	# buttons on the teacher's own Schedule tab), mirrored here so the group form's own Schedule
	# tab knows whether to show its inline topic/classroom edit affordance (see
	# 'ReadonlyScheduleGridField', schedule_grid_readonly_field.js). Not stored - a plain
	# per-request permission check, same as the teacher's own field.
	can_edit_schedule = fields.Boolean(string="Can edit schedule", compute="_compute_can_edit_schedule", compute_sudo=True)

	@api.depends("group_type", "study_id.acronym", "course", "acronym")
	def _compute_name(self):
		for group in self:
			#TODO: validate the uniqueness
			if group.group_type == "main":
				# 'study_id'/'course'/'acronym' can be transiently empty right after switching from
				# 'reinforcement' back to 'main' (before the user fills them in) — building the string
				# anyway would render literal "False"/"0" instead of a blank name.
				group.name = "%s%s%s" % (group.study_id.acronym, group.course, group.acronym) \
					if group.study_id and group.course and group.acronym else False
			elif not group.name:
				group.name = group.acronym or group.external_id or _("New Reinforcement Group")

	@api.onchange("group_type")
	def _onchange_group_type(self):
		# NOTE: only clears the group's OWN fields (visible to the user before Save, so nothing is lost
		# without them seeing it happen first). Existing 'main_student_ids' (other res.partner records
		# pointing here via main_group_id) are deliberately NOT touched here — see
		# '_check_group_type_fields' below, which blocks the switch instead of silently orphaning them.
		for group in self:
			if group.group_type == "reinforcement":
				group.level_id = False
				group.study_id = False
				group.course = False
				group.acronym = False
				group.tutor_id = False
				group.delegate_id = False

	@api.constrains("group_type", "level_id", "study_id", "course", "acronym", "tutor_id", "delegate_id")
	def _check_group_type_fields(self):
		for group in self:
			if group.group_type == "main":
				if not (group.level_id and group.study_id and group.course and group.acronym):
					raise ValidationError(_("A main group requires a level, a study, a course and an acronym."))
			elif group.group_type == "reinforcement":
				if group.level_id or group.study_id or group.tutor_id or group.delegate_id:
					raise ValidationError(_("A reinforcement group cannot have a level, a study, a tutor or a delegate: "
						"it is meant to mix students from different main groups and studies."))
				if group.main_student_ids:
					raise ValidationError(_("This group has %d student(s) enrolled as their main group. Reassign them to "
						"another group before converting this one to reinforcement.") % len(group.main_student_ids))

	def _compute_enrolled_student_ids(self):
		for group in self:
			group.enrolled_student_ids = self.env["ems.enrollment"].search([("group_id", "=", group.id)]).mapped("student_id") or False

	def _compute_enrollment_ids(self):
		# NOTE: deliberately a compute WITH side effects (delete + recreate ems.enrollment_view
		# rows) rather than a pure read — the only way found to expose "enrollment_view_ids
		# filtered to just this group" as a One2many, since Odoo can't filter a computed
		# relation server-side the way a stored inverse can. ems.enrollment_view is a
		# TransientModel (auto-vacuumed), so the churn is cheap, but this does mean every read
		# of an unset/stale enrollment_view_ids re-runs a delete+insert, not just a select —
		# worth knowing if this model's read patterns ever become a hot path.
		# sudo() (bug found 2026-09-06): this delete+recreate is internal scratch-data
		# bookkeeping for a computed field, not a real action the viewing user is taking - it
		# used to run as whoever opened the group's form, so a teacher/tutor (perm_create=0,
		# perm_unlink=0 on ems.enrollment_view - read-only by design) got an AccessError from
		# simply opening any group's form at all.
		EnrollmentView = self.env['ems.enrollment_view'].sudo()
		for group in self:
			EnrollmentView.search([('group_id', '=', group.id)]).unlink()
			group.enrollment_view_ids = False
			# Sources:
			# 	https://www.odoo.com/documentation/16.0/developer/reference/backend/orm.html?highlight=read_group#search-read
			#	https://www.cybrosys.com/odoo/odoo-books/odoo-15-development/ch15/grouped-data/
			for student in self.env['ems.enrollment'].read_group(domain=[('group_id', '=', group.id)], fields=['student_id'], groupby=['student_id']):
				sid = student['student_id'][0]
				subs = self.env["ems.enrollment"].search([("group_id", "=", group.id), ('student_id', '=', sid)]).mapped("subject_id")

				# Source: https://www.odoo.com/fi_FI/forum/apua-1/how-to-insert-value-to-a-one2many-field-in-table-with-create-method-28714
				EnrollmentView.create({
					"group_id": group.id,
					"student_id": sid,
					"subject_ids": subs,
				})

	def _compute_pending_classroom_conflict_count(self):
		Attendance = self.env['resource.calendar.attendance']
		for group in self:
			group.pending_classroom_conflict_count = Attendance.search_count([
				('group_ids', '=', group.id),
				('space_pending_group_sync', '=', True),
			])

	def _compute_can_edit_schedule(self):
		can_edit = self.env.user.has_group('ems.group_department_chief')
		for group in self:
			group.can_edit_schedule = can_edit

	@api.depends('space_id')
	def _compute_suggested_space_id(self):
		# NOTE: 'space_id' is the only real dependency Odoo's own cache invalidation can track -
		# the rest of the real dependency (every resource.calendar.attendance row referencing this
		# group) lives on a different model via a reverse M2M, which @api.depends can't express.
		# Declaring 'space_id' still matters: without it, applying a suggestion in the same
		# transaction (action_apply_suggested_space) would leave this field's cached value stale
		# (found the hard way - see tests/test_group_classroom_suggestion.py's own
		# test_apply_suggestion_updates_space_and_propagates). A caller that changes the calendar
		# elsewhere and needs a fresh read without reloading the record should still
		# invalidate_recordset() explicitly, same as 'pending_classroom_conflict_count' above.
		Attendance = self.env['resource.calendar.attendance']
		for group in self:
			blocks = Attendance.search([
				('group_ids', '=', group.id),
				('subject_id', '!=', False),
				('calendar_id.active', '=', True),
			])
			hours_by_space = {}
			for block in blocks.filtered('space_id'):
				hours_by_space[block.space_id] = hours_by_space.get(block.space_id, 0.0) \
					+ (block.hour_to - block.hour_from)
			if not hours_by_space or hours_by_space.get(group.space_id, 0.0) > 0:
				# Nothing to suggest: either the group has no real teaching anywhere yet, or its
				# own current room already accounts for at least some of its real hours (drift is
				# specifically "zero hours in the CURRENT room", not "not the majority room").
				group.suggested_space_id = False
				continue
			# Most hours wins; ties broken by room name then id, so the result is deterministic.
			group.suggested_space_id = sorted(
				hours_by_space.items(), key=lambda item: (-item[1], item[0].name or '', item[0].id)
			)[0][0]

	def _search_suggested_space_id(self, operator, value):
		if operator not in ('=', '!=') or value is not False:
			raise NotImplementedError(_("Unsupported search on suggested_space_id"))
		drifted = self.search([]).filtered('suggested_space_id')
		return [('id', 'in' if operator == '!=' else 'not in', drifted.ids)]

	def _sanitize_group_type_vals(self, vals):
		# NOTE: '_onchange_group_type' already does this client-side, purely so the user SEES the fields
		# clear before Save — it cannot be the only place this happens: it never runs for a write() that
		# doesn't go through this exact form (RPC, batch action, an import), and even in the form its
		# timing relative to other onchange/compute triggers isn't something to depend on. This is the
		# actual guarantee that '_check_group_type_fields' below never rejects a plain group_type switch.
		group_type = vals.get("group_type")
		if group_type == "reinforcement":
			for field in ("level_id", "study_id", "course", "acronym", "tutor_id", "delegate_id"):
				vals.setdefault(field, False)

	def _sync_tutor_role(self, employees):
		"""Keep 'employees' Tutor role and security groups in sync with whether they
		currently tutor at least one group. Shared by create() (a group created with
		tutor_id already set) and write() (tutor_id assigned/reassigned/cleared later) so
		both paths behave the same way instead of only write() doing the sync."""
		employees.update_tutor_role()
		employees._sync_security_groups()

	def _raise_if_archived_duplicate(self, groups):
		# 'name' (e.g. 'DAM1A') is the group's real-world identity and is confirmed unique in
		# practice: a group not running this course may well come back in a future one, so the
		# right move is to reactivate the existing (archived) record, not create a second one
		# with the same name. Raised from inside a savepoint (see create()/write() below), so
		# the offending create/rename never actually persists once this propagates out.
		for group in groups:
			archived = self.with_context(active_test=False).search([
				("name", "=", group.name), ("active", "=", False), ("id", "!=", group.id),
			], limit=1)
			if archived:
				raise RedirectWarning(
					_("A group named \"%s\" already exists but is archived. Reactivate it instead "
						"of creating a duplicate?") % group.name,
					self.env.ref("ems.action_server_group_reactivate").id,
					_("Reactivate"),
					{"active_model": self._name, "active_id": archived.id, "active_ids": archived.ids},
				)

	@api.model_create_multi
	def create(self, vals_list):
		for vals in vals_list:
			self._sanitize_group_type_vals(vals)
		with self.env.cr.savepoint():
			groups = super().create(vals_list)
			self._raise_if_archived_duplicate(groups)
		self._sync_tutor_role(groups.mapped('tutor_id'))
		return groups

	def _archive_confirmation_message(self):
		# Archiving is always allowed (it never removes/unenrolls anyone) - this only builds the
		# confirmation message when there's something worth confirming (at least one active
		# student). Shared by the write()-time safety net below and by
		# 'get_archive_confirmation_message()', which the client calls proactively so it can show
		# its OWN dialog (proper title, "Proceed"/"Cancel" labels) instead of ever letting Odoo's
		# generic RedirectWarning dialog ("Odoo Warning" title, no control over button styling) be
		# what the user actually sees.
		# 'main' groups: membership is main_group_id's inverse (main_student_ids), already
		# active_test-filtered by default. 'reinforcement' groups have no membership field of
		# their own since 'reinforcement_student_ids' was removed (2026-09-07, see group.md) -
		# 'enrolled_student_ids' (derived from ems.enrollment.group_id) is what a reinforcement
		# group's real members look like, and needs an explicit .filtered("active") since it's
		# built via mapped() rather than an inverse search. Counting BOTH fields for every group
		# (like a plain sum would) would double-count a 'main' group's students, who normally
		# also show up in 'enrolled_student_ids' via their own subject enrollments.
		count = 0
		for group in self:
			if group.group_type == "reinforcement":
				count += len(group.enrolled_student_ids.filtered("active"))
			else:
				count += len(group.main_student_ids)
		if not count:
			return False
		return "\n\n".join([
			_("This group still has %(count)s active student(s) as members.") % {"count": count},
			_("Archiving is allowed and will not remove or unenroll any student. The group's "
				"member list stays exactly as it is, they simply won't appear in the default "
				"(non-archived) views anymore."),
			_("If these students are still here because the end-of-course transition hasn't run "
				"yet, that process will move or clear them from this group when it does, the same "
				"as for any other group. Archiving this one now has no effect on that, and doesn't "
				"need to wait for it either."),
			_("Do you want to archive this group anyway?"),
		])

	def get_archive_confirmation_message(self):
		"""RPC-callable: returns the confirmation message (or False if none is needed) so
		EmsGroupFormController/EmsGroupListController can show their own dialog BEFORE ever
		calling archive - the normal, expected path. write()'s own guard below still exists as a
		safety net for anything that archives outside that UI (a direct ORM call, an import
		script, an RPC client), where it falls back to the plainer RedirectWarning dialog."""
		return self._archive_confirmation_message()

	def _raise_if_archiving_active_students(self):
		# Self-retriggering RedirectWarning, same pattern Odoo core uses for e.g.
		# account.account's Unmerge: the button re-runs this same write() with a context flag
		# that skips the check the second time, so declining (closing the dialog) leaves the
		# group untouched - nothing has been written yet at the point this raises.
		if self.env.context.get("ems_group_archive_confirmed"):
			return
		message = self._archive_confirmation_message()
		if not message:
			return
		raise RedirectWarning(
			message,
			self.env.ref("ems.action_server_group_confirm_archive").id,
			_("Proceed"),
			{"active_model": self._name, "active_ids": self.ids},
		)

	def write(self, vals):
		self._sanitize_group_type_vals(vals)
		if vals.get("active") is False:
			self._raise_if_archiving_active_students()
		old_tutor = self.tutor_id
		# NOTE: captured before super().write() - need each group's OWN previous room to detect who
		# actually changed and what to move away from (see _propagate_classroom_change below).
		old_space_by_group = {group.id: group.space_id for group in self} if 'space_id' in vals else {}
		name_affecting = vals.keys() & {"name", "course", "acronym", "study_id", "group_type", "external_id"}
		with self.env.cr.savepoint():
			res = super(EmsGroup, self).write(vals)
			if name_affecting:
				self._raise_if_archived_duplicate(self)
		new_tutor = self.tutor_id

		if 'tutor_id' in vals:
			# NOTE: tutor_id field changes when the tutor is assigned from the teacher form, but the old tutor's role
			# should be updated and must be done from here once changed.
			self._sync_tutor_role(old_tutor | new_tutor)
		if 'space_id' in vals:
			# NOTE: best-effort, issue #405 - deliberately AFTER super().write() has already fully
			# succeeded (see docs/en/developers/contacts/group.md's "Classroom change propagation"
			# section for why this never raises/rolls back: an earlier design used RedirectWarning
			# here and discarded every other field change made in the same save whenever a room
			# collision showed up, which is not acceptable).
			for group in self:
				old_space = old_space_by_group[group.id]
				if old_space and old_space != group.space_id:
					group._propagate_classroom_change(old_space, group.space_id)
		return res

	def action_reactivate(self):
		self.ensure_one()
		self.active = True
		return {
			"type": "ir.actions.act_window",
			"res_model": self._name,
			"res_id": self.id,
			"view_mode": "form",
			"target": "current",
		}

	def action_confirm_archive(self):
		self.with_context(ems_group_archive_confirmed=True).write({"active": False})
		return {
			"type": "ir.actions.client",
			"tag": "soft_reload",
		}

	def action_open_classroom_change_wizard(self):
		"""Opens 'ems.group_classroom_change_wizard' for this group's pending classroom conflicts
		(see 'pending_classroom_conflict_count' and the banner button on the form). Creates the
		wizard record here, before ever opening the form - see that model's own create() override
		for why its conflict lines must already be real, persisted records rather than staged via
		context defaults on a not-yet-created one."""
		self.ensure_one()
		wizard = self.env['ems.group_classroom_change_wizard'].create({'group_id': self.id})
		return {
			"type": "ir.actions.act_window",
			"res_model": "ems.group_classroom_change_wizard",
			"res_id": wizard.id,
			"view_mode": "form",
			"target": "new",
		}

	def action_apply_suggested_space(self):
		"""Applies 'suggested_space_id' to 'space_id' - a plain field write, relying entirely on
		write()'s own '_propagate_classroom_change' below to do the real work (a field assignment
		on a persisted record goes through write() the same way an external caller's write() call
		does). Provably conflict-free: 'suggested_space_id' is only ever set when the group's
		CURRENT room already has zero active teaching hours (see '_compute_suggested_space_id'),
		so '_propagate_classroom_change' will always find zero blocks left in the old room to
		move - it can never reach '_resolve_or_flag_pending_block's own conflict branch. See
		docs/en/developers/contacts/group.md's "Classroom drift suggestion" section."""
		self.ensure_one()
		if self.suggested_space_id:
			self.space_id = self.suggested_space_id

	def _propagate_classroom_change(self, old_space, new_space):
		"""Best-effort propagation of a group's classroom change to its own teaching schedule (issue
		#405) - moves every currently-active teaching block ('resource.calendar.attendance') still
		using 'old_space' to 'new_space' (see '_resolve_or_flag_pending_block'). NEVER raises - see
		write()'s own comment for why (nothing here may ever cause the group's own save to roll
		back). Guard-duty/break/meeting blocks ('non_teaching' set, 'subject_id' empty) are out of
		scope - the user-facing ask is specifically about "the classroom for some subject", not
		every use of a room."""
		self.ensure_one()
		blocks = self.env['resource.calendar.attendance'].search([
			('group_ids', '=', self.id),
			('subject_id', '!=', False),
			('space_id', '=', old_space.id),
			('calendar_id.active', '=', True),
		])
		for block in blocks:
			self._resolve_or_flag_pending_block(block, new_space)

	def _resolve_or_flag_pending_block(self, block, new_space):
		"""Thin wrapper for 'resource.calendar.attendance.relocate_or_flag_pending()' (moved there
		2026-09-12, issue #444's follow-up - the block being relocated and the pending flag itself
		both genuinely belong to that model, not this one; see that method's own docstring for the
		full behaviour). Kept here, unchanged in name/signature, since it's shared by
		'_propagate_classroom_change' (a block just left in 'old_space') and
		'ems.group_classroom_change_wizard' (re-checking an already-flagged block when the wizard
		opens, in case the collision it was flagged for has since resolved itself)."""
		self.ensure_one()
		return block.relocate_or_flag_pending(new_space)

	def _ems_equivalent_for_course(self, course):
		"""The group where a subject of a different `course` is actually taught for a
		student currently in this group: exact acronym (and shift, when this group has
		one) match in that course, else the first group of that study+course in the
		model's own order (see _order), so a subject genuinely pending from another
		course always lands somewhere concrete instead of being left unplaced. Empty
		only when that study+course has no group at all."""
		self.ensure_one()
		domain = [("study_id", "=", self.study_id.id), ("course", "=", course),
			("group_type", "=", "main")]
		Group = self.env["ems.group"]
		exact_domain = domain + [("acronym", "=", self.acronym)]
		if self.shift:
			exact_domain.append(("shift", "=", self.shift))
		return Group.search(exact_domain, limit=1) or Group.search(domain, order="name", limit=1)


class EmsEnrollmentView(models.TransientModel):
	_name = "ems.enrollment_view"
	_description = "Transient model for displaying enrollment data within groups but filtered (allows ems.group.enrollment_view_ids to work: contains the same data as enrolled_student_ids but filtered for the current group because it cannot be filtered on view...)."

	group_id = fields.Many2one(comodel_name="ems.group")
	student_id = fields.Many2one(comodel_name="res.partner")
	subject_ids = fields.Many2many(comodel_name="ems.subject")
	image_1920 = fields.Binary(string="Image", related='student_id.image_1920')