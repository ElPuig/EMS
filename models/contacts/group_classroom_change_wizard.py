# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class EmsGroupClassroomChangeWizard(models.TransientModel):
	_name = "ems.group_classroom_change_wizard"
	_description = "Resolve schedule blocks left pending after a classroom change (issue #405, #444's follow-up)."

	# NOTE: exactly one of 'group_id'/'employee_id' is set, depending on which action opened this
	# wizard - 'ems.group.action_open_classroom_change_wizard()' (a group-wide classroom change,
	# issue #405) or 'hr.employee.action_open_classroom_change_wizard()' (a single teacher's own
	# pending room changes, issue #444's follow-up, 2026-09-12). Neither is 'required' at the
	# model level since the OTHER one legitimately covers the "no group" / "no employee" case -
	# both actions always set one before ever calling create().
	group_id = fields.Many2one(string="Group", comodel_name="ems.group", readonly=True)
	employee_id = fields.Many2one(string="Teacher", comodel_name="hr.employee", readonly=True)
	conflict_line_ids = fields.One2many(
		string="Pending conflicts", comodel_name="ems.group_classroom_change_wizard_conflict_line", inverse_name="wizard_id")
	# NOTE: same "two mutually-exclusive buttons" pattern as the import wizard's own
	# 'continue_disabled' (views/community/working_schedules/import_wizard.xml) - Odoo's button
	# widget has no direct way to render a computed boolean as a literal HTML 'disabled' attribute,
	# so the view shows either the real 'action_confirm' button or an inert decoy depending on this.
	confirm_disabled = fields.Boolean(compute="_compute_confirm_disabled")

	@api.depends('conflict_line_ids.resolution', 'conflict_line_ids.left_space_id', 'conflict_line_ids.right_space_id')
	def _compute_confirm_disabled(self):
		for wizard in self:
			wizard.confirm_disabled = bool(wizard.conflict_line_ids.filtered(lambda line: not line._resolution_is_valid()))

	@api.model_create_multi
	def create(self, vals_list):
		"""Populates 'conflict_line_ids' server-side, from 'group_id'/'employee_id', for any vals
		that doesn't already supply it - rather than a 'default_get' override. This wizard's whole
		record must already be PERSISTED (a real id) by the time its conflict-line pickers are
		edited in the browser: those edits go through onchange round-trips that, for a still-
		virtual (not yet created) parent's o2m children, only preserve the fields the list view
		itself declares - this line model's own required 'left_attendance_id'/'right_schedule_id'
		aren't among them (kept out of the view on purpose, same as the import wizard's own
		equivalent fields), so a virtual line would silently lose them the moment a room picker
		changes. Reached both by 'ems.group.action_open_classroom_change_wizard()' and
		'hr.employee.action_open_classroom_change_wizard()' (creates before ever opening the form)
		and directly in tests."""
		wizards = super().create(vals_list)
		for wizard in wizards:
			if wizard.conflict_line_ids:
				continue
			if wizard.group_id:
				pending_blocks = self.env['resource.calendar.attendance'].search([
					('group_ids', '=', wizard.group_id.id), ('space_pending_group_sync', '=', True),
				])
				fallback_space = wizard.group_id.space_id
			elif wizard.employee_id:
				pending_blocks = self.env['resource.calendar.attendance'].search([
					('calendar_id', '=', wizard.employee_id.resource_calendar_id.id), ('space_pending_group_sync', '=', True),
				])
				fallback_space = self.env['ems.space']
			else:
				continue
			wizard.conflict_line_ids = wizard._build_conflict_lines(pending_blocks, fallback_space)
		return wizards

	def action_confirm(self):
		self.ensure_one()
		for line in self.conflict_line_ids:
			if not line._resolution_is_valid():
				raise ValidationError(_(
					"The resolution chosen for \"%(left)s\" is not valid yet - pick a room for both "
					"sides (different from each other) when reassigning, or a different resolution."
				) % {'left': line.left_label})
		for line in self.conflict_line_ids:
			# NOTE: 'line.exists()' - two lines can legitimately share the exact same
			# 'right_schedule_id' (a co-taught class flags EACH co-teacher's own block
			# independently, see '_apply_resolution's own "clear siblings" note) - required M2O
			# fields default to 'ondelete=cascade' (see odoo/fields.py's Many2one.setup_nonrelated),
			# so resolving the FIRST line can delete 'right_schedule_id' (e.g. 'prevail_left'
			# archiving a session down to zero blocks - 'ems.attendance_template._archive_or_
			# delete' then deletes it outright), which cascade-deletes every OTHER still-unprocessed
			# line referencing that same schedule right along with it. The underlying calendar
			# block behind a line vanishing this way is still correctly resolved - by the FIRST
			# line's own sibling-clearing pass, not by this now-gone line - so skipping it here is
			# safe, not a silently-dropped resolution.
			if line.exists():
				line._apply_resolution()
		return {"type": "ir.actions.act_window_close"}

	def _build_conflict_lines(self, pending_blocks, fallback_space):
		"""One (0, 0, {...}) command per still-unresolved pending block. Re-checks every pending
		block against its own 'pending_new_space_id' (falling back to 'fallback_space' only for a
		block flagged before that field existed - see 'resource.calendar.attendance.
		relocate_or_flag_pending', issue #444's follow-up) rather than trusting the flag alone -
		the collision it was flagged for may have resolved itself since (e.g. the other session
		was independently archived), in which case 'relocate_or_flag_pending' moves it straight
		away and it never becomes a line here at all. 'pending_blocks' is origin-agnostic (a
		group's own pending blocks, or a single teacher's own calendar's) - both origins populate
		'pending_new_space_id' identically, so this method doesn't need to know which one it's
		building for."""
		commands = []
		for block in pending_blocks:
			target_space = block.pending_new_space_id or fallback_space
			for other, _same_teacher in block.relocate_or_flag_pending(target_space):
				commands.append((0, 0, {
					'left_attendance_id': block.id,
					'right_schedule_id': other.id,
					'kind': 'plain_conflict',
					'resolution': 'reassign_rooms',
					'left_label': self._block_label(block),
					'right_label': other.display_name,
					'left_group_key': "%s - %s" % (block.employee_id.display_name, block.subject_id.display_name),
					'left_space_id': target_space.id,
					'right_space_id': target_space.id,
				}))
		return commands

	def _block_label(self, block):
		weekday_label = dict(block._fields['dayofweek'].selection).get(block.dayofweek)
		return "%s - %s - %s (%s %s)" % (
			block.employee_id.display_name, block.subject_id.display_name,
			", ".join(block.group_ids.mapped('display_name')), weekday_label, self._format_hour_range(block))

	def _format_hour_range(self, block):
		return "%s-%s" % (self._format_hour(block.hour_from), self._format_hour(block.hour_to))

	def _format_hour(self, hour):
		return "%02d:%02d" % (int(hour), round((hour % 1) * 60))


class EmsGroupClassroomChangeWizardConflictLine(models.TransientModel):
	_name = "ems.group_classroom_change_wizard_conflict_line"
	_inherit = ["ems.working_schedules_import_wizard.conflict_mixin"]
	_description = "Group classroom-change wizard: room-conflict line for one pending teaching block."

	wizard_id = fields.Many2one(
		string="Wizard", comodel_name="ems.group_classroom_change_wizard", required=True, ondelete="cascade")
	# NOTE: 'left' is always the pending block belonging to the group whose classroom just changed;
	# 'right' is always the already-active 'ems.attendance_schedule' line it collides with - same
	# "left = the side that moved, right = the side that was already there" convention as the import
	# wizard's own 'external_conflict_line' (models/employees/working_schedule.py).
	left_attendance_id = fields.Many2one(
		string="Pending block", comodel_name="resource.calendar.attendance", required=True, readonly=True)
	right_schedule_id = fields.Many2one(
		string="Existing session", comodel_name="ems.attendance_schedule", required=True, readonly=True)

	def _apply_resolution(self):
		"""Applies this line's chosen 'resolution', then clears 'space_pending_group_sync' on
		'left_attendance_id' regardless of which one was picked - either way the admin has now made
		an explicit, informed decision about this block, so it stops being "pending".

		Bottom-up sync redesign, Phase 6 (2026-09-08): both sides now write ONLY
		'resource.calendar.attendance' (the pending block directly here; the existing session via
		'ems.attendance_schedule._relocate_via_calendar_blocks'/'_archive_via_calendar_blocks') and let
		the automatic hook keep 'ems.attendance_schedule'/'ems.attendance_template' correctly in
		sync as a consequence - this is exactly what fixes the real bug found on SMX1D/SMX2D
		(writing the schedule directly left the teacher's own calendar silently pointing at the old
		room), now fixed at the source instead of patched here."""
		self.ensure_one()
		block = self.left_attendance_id
		existing = self.right_schedule_id
		# NOTE: 'pending_new_space_id' (issue #444's follow-up) is what a single teacher's own
		# room change actually asked for; the group-wide flow (issue #405) populates it
		# identically via 'relocate_or_flag_pending', with 'wizard.group_id.space_id' kept only as
		# a fallback for a block flagged before that field existed.
		new_space = block.pending_new_space_id or self.wizard_id.group_id.space_id
		if self.resolution == 'reassign_rooms':
			# NOTE: 'existing' moves FIRST - unlike the import wizard's own 'reassign_rooms' (whose
			# left side is still an unsaved node_cache entry, so only the right side ever touches the
			# DB), here BOTH sides are already real, active records: moving 'block' into
			# 'left_space_id' before 'existing' has vacated it would trip 'check_overlap' on a purely
			# transient state, even though the end result (both moved) is perfectly valid.
			if existing.space_id != self.right_space_id:
				existing._relocate_via_calendar_blocks(self.right_space_id)
			block.space_id = self.left_space_id.id
			resolved_space = self.left_space_id
		elif self.resolution == 'prevail_left':
			# The pending block takes the group's new classroom; the session it collided with is
			# archived - same handling as the import wizard's own 'prevail_left' on an external
			# conflict (models/employees/working_schedule.py's '_continue_from_db_conflicts').
			existing._archive_via_calendar_blocks()
			block.space_id = new_space.id
			resolved_space = new_space
		else:
			# 'prevail_right': the pending block keeps its current classroom for this slot - a
			# deliberate, accepted divergence from the group's own room from now on. Nothing to
			# write on 'block' itself.
			resolved_space = block.space_id
		block.space_pending_group_sync = False
		block.pending_new_space_id = False
		# NOTE: issue #444's THIRD follow-up (2026-09-12) - a co-taught class's room change flags
		# EVERY co-teacher's own calendar block sharing the exact slot (see 'ems.attendance_
		# template._flag_room_change_pending'), since it's genuinely the same collision from each
		# of their own calendars' point of view. Found the hard way: resolving it from only ONE
		# teacher's own wizard (hr.employee.action_open_classroom_change_wizard, scoped to just
		# their own calendar) left the CO-TEACHER's own sibling block stuck pending forever - the
		# group's own banner kept showing it even though the room had already converged correctly
		# via the automatic sync hook this same write triggers. Every sibling still flagged pending
		# for this exact slot gets the SAME outcome applied here, regardless of which wizard
		# (group-scoped or employee-scoped) this resolution came from.
		siblings = self.env['resource.calendar.attendance'].search([
			('id', '!=', block.id),
			('subject_id', '=', block.subject_id.id),
			('dayofweek', '=', block.dayofweek),
			('hour_from', '=', block.hour_from),
			('hour_to', '=', block.hour_to),
			('space_pending_group_sync', '=', True),
		])
		if siblings:
			siblings.write({
				'space_id': resolved_space.id,
				'space_pending_group_sync': False,
				'pending_new_space_id': False,
			})
