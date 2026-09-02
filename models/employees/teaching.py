# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class EmsTeaching(models.Model):
	_name = "ems.teaching"
	_description = "Teaching: ternary relation between teacher-group-subject."
	_inherit = ['ems.base']
	_order = "subject_id, group_id"

	teacher_id = fields.Many2one(string="Teacher", comodel_name="hr.employee", ondelete='cascade', required=True, domain="[('employee_type', '=', 'teacher')]")
	group_id = fields.Many2one(string="Group", comodel_name="ems.group", ondelete='cascade', required=True)
	subject_id = fields.Many2one(string="Subject", comodel_name="ems.subject", ondelete='cascade', required=True)
	# TODO: course_id should be added!

	# This field is used to filter the availabe groups within the view (avoiding the selection of repeated groups for the same subject in teaching form).
	# Note: compute_sudo is needed for read-only access.
	inuse_group_ids = fields.Many2many('ems.group', compute='_compute_inuse_group_ids', compute_sudo=True, store=False)

	@api.depends('subject_id')
	def _compute_inuse_group_ids(self):
		for teaching in self:
			groups = []
			for other in teaching.teacher_id.teaching_ids:
				if other.subject_id == teaching.subject_id and other.group_id.id != False:
					groups.append(other.group_id.id)
			teaching.inuse_group_ids = [(6, 0, groups)]

	@api.depends('subject_id')
	def _compute_display_name(self):
		for teaching in self:
			teaching.display_name = "%s" % teaching.subject_id.display_name

	@api.constrains('teacher_id', 'group_id', 'subject_id')
	def _check_unique_active(self):
		for teaching in self:
			domain = [
				('id', '!=', teaching.id),
				('teacher_id', '=', teaching.teacher_id.id),
				('group_id', '=', teaching.group_id.id),
				('subject_id', '=', teaching.subject_id.id),
				('active', '=', True),
			]

			# TODO: add the current course!
			if self.search_count(domain) > 0:
				raise ValidationError(_("There's another active entry for the same 'teacher / group / subject' ternary. Archive it first."))

	def unlink(self):
		"""Clears a group's stale 'tutor_id' whenever the teaching that backed it goes away -
		the single choke point every removal path already goes through (sync_from_schedule()'s
		own 'replace=True' drop, a direct admin unlink, and the calendar-driven resync added to
		course transition/regenerate_all_from_calendars()). A tutoring assignment is itself
		recorded as an ordinary ems.teaching row, on the group's own tutoring subject
		(subject_id.is_tutorship) - deliberately never wired to 'ems.group.tutor_id' by a stored
		relation, since that field predates this model's own calendar-driven sync and is set
		directly on the group form. Captured BEFORE the actual unlink (fields are unreadable
		once the row is gone), then only cleared if 'tutor_id' still matches - a manual
		reassignment in between must never be clobbered by a stale unlink running late."""
		stale_tutorships = {
			(teaching.group_id, teaching.teacher_id)
			for teaching in self.filtered(lambda teaching: teaching.subject_id.is_tutorship)
		}
		result = super().unlink()
		for group, teacher in stale_tutorships:
			if group.tutor_id == teacher:
				group.tutor_id = False
		return result

	def sync_from_schedule(self, teacher, entries, replace=True):
		"""Sync 'teacher.teaching_ids' from the (subject_id, group_ids) pairs found in 'entries'
		(dicts with a 'subject_id' and a 'group_ids' list), keeping any entry that is unchanged and
		only creating what's actually new.

		'replace' controls whether a pair NOT found in 'entries' gets unlinked:
		- True (default) - the employee 'Schedule' tab's grid widget, where 'entries' genuinely IS
		  that one teacher's ENTIRE schedule right now, so anything missing was deliberately dropped.
		- False - the working-schedule XML importer's batch path, where 'entries' only ever
		  describes ONE FILE's slice of the centre's schedule (e.g. one department), imported
		  incrementally alongside others over time; unlinking here would silently destroy a teacher's
		  already-imported assignments from a DIFFERENT file the moment they appear in this one too
		  (found 2026-08-01: a teacher shared between two department imports lost the first
		  department's teaching assignments when the second was imported)."""
		old_items = dict()
		for teaching in teacher.teaching_ids.filtered('active'):
			old_items["%s.%s" % (teaching.subject_id.id, teaching.group_id.id)] = teaching

		new_teaching = []
		new_items = dict()
		for entry in entries:
			for group_id in entry["group_ids"]:
				key = "%s.%s" % (entry["subject_id"], group_id)
				value = {'group_id': group_id, 'subject_id': entry["subject_id"]}

				if key not in new_items:
					new_items[key] = value

				if key not in old_items:
					item = [0, 0, value]
					if item not in new_teaching:
						new_teaching.append(item)

		if replace:
			for key, teaching in old_items.items():
				if key not in new_items:
					# NOTE: unlink (not archive) so the schedule editor stays the single source of truth.
					teaching.unlink()

		teacher.write({'teaching_ids': new_teaching})