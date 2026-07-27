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

	def sync_from_schedule(self, teacher, entries):
		"""Replace 'teacher.teaching_ids' so it matches the (subject_id, group_ids) pairs found in
		'entries' (dicts with a 'subject_id' and a 'group_ids' list), keeping any entry that is
		unchanged and only creating/unlinking what actually differs. Shared by the working schedule's
		XML importer and the employee 'Schedule' tab's grid widget, so the teaching assignation always
		stays derived from the schedule instead of being maintained by hand in two places."""
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

		for key, teaching in old_items.items():
			if key not in new_items:
				# NOTE: unlink (not archive) so the schedule editor stays the single source of truth.
				teaching.unlink()

		teacher.write({'teaching_ids': new_teaching})