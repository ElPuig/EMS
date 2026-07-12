# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime

class ems_attendance_template(models.Model):
	_name = "ems.attendance_template"
	_description = "Attendance template: contains the basic attendance data (who teaches what, where and for whom)"
	_inherit = ['ems.base']

	start_date = fields.Date(string="Start date", required=True)
	end_date = fields.Date(string="End date", required=True)
	color = fields.Integer(string="Color", help="Field to store the color that will be used for calendar view")   

	teacher_id = fields.Many2one(string="Teacher", comodel_name="hr.employee", domain="[('employee_type', '=', 'teacher')]", required=True, default=lambda self: self._default_teacher_id(), store=True, ondelete='cascade')
	level_id = fields.Many2one(string="Level", comodel_name="ems.level", required=True)
	study_id = fields.Many2one(string="Study", comodel_name="ems.study", domain="[('level_id', '=', level_id)]", required=True)
	group_ids = fields.Many2many(string="Groups", comodel_name="ems.group", domain="[('study_id', '=', study_id)]")
	subject_id = fields.Many2one(string="Subject", comodel_name="ems.subject", domain="[('study_ids', 'in', study_id)]", required=True)
	space_id = fields.Many2one(string="Space", comodel_name="ems.space", required=True)
	
	attendance_schedule_ids = fields.One2many(string="Sessions", comodel_name="ems.attendance_schedule", inverse_name="attendance_template_id")			
	student_ids = fields.Many2many(string="Students", comodel_name="res.partner", domain="[('contact_type', '=', 'student')]")	

	# NOTE: this field is computed when loaded within a form or list
	read_only_user = fields.Boolean(default=lambda self:self._get_read_only_user(), store=False)
	
	def _get_read_only_user(self):
		return not (self.id == False or self.get_user_is_admin() or self.teacher_id.user_id.id == self.env.uid or self.create_uid == self.env.uid)

	def _default_teacher_id(self):
		return self.env["hr.employee"].search([("user_id", "=", self.env.uid), ("employee_type", "=", "teacher")]) or False

	@api.constrains('group_ids')
	def _check_group_ids(self):
		for rec in self:
			if not rec.group_ids:
				raise ValidationError(_("At least one group must be selected."))

	@api.constrains('teacher_id', 'start_date', 'end_date', 'active')
	def _check_schedule_overlap(self):
		# NOTE: @api.constrains does not support dotted paths through relations, so changes to
		# these template fields must re-trigger the check owned by ems.attendance_schedule.
		for rec in self:
			rec.attendance_schedule_ids.check_overlap()

	@api.depends('subject_id', 'group_ids')
	def _compute_display_name(self):
		for rec in self:
			groups = ", ".join(rec.group_ids.mapped('name'))
			rec.display_name = "%s (%s)" % (rec.subject_id.display_name, groups)

	@api.onchange("group_ids")
	def _onchange_group_ids(self):
		for rec in self:
			if rec.group_ids:
				rec.space_id = rec.group_ids[0].space_id

	@api.onchange("subject_id", "group_ids")
	def _fill_students(self):
		for rec in self:
			rec.fill_students()

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
		"""Replace 'teacher.attendance_template_ids' (and their per-weekday 'attendance_schedule_ids')
		so they match the (subject_id, group_ids, hour_from, hour_to, dayofweek) slots found in
		'entries' — one template per distinct (subject, group-set) combination. Templates no longer
		present are archived (attendance history is kept); newly created ones are auto-filled with the
		group's currently enrolled students. Shared by the working schedule's XML importer (a fresh
		full-course import, so 'start_date' defaults to the course's start) and the employee 'Schedule'
		tab's grid widget (a live mid-course edit, which passes today's date instead)."""
		now = datetime.now()
		start_date = start_date or datetime(now.year, 9, 1)
		end_date = datetime(now.year + 1, 7, 1)

		old_items = dict()
		for template in teacher.attendance_template_ids.filtered('active'):
			old_items["%s.%s" % (template.subject_id.id, ",".join(str(g) for g in sorted(template.group_ids.ids)))] = template

		templates = dict()
		new_items = dict()
		for entry in entries:
			key = "%s.%s" % (entry["subject_id"], ",".join(str(g) for g in sorted(entry["group_ids"])))

			if key not in new_items:
				new_items[key] = entry

			if key not in old_items:
				if key in templates:
					template_vals = templates[key]
				else:
					# TODO: define default start and end date for subjects within settings.
					first_group = self.env['ems.group'].browse(entry["group_ids"][0])
					template_vals = {
						'start_date': start_date,
						'end_date': end_date,
						'color': len(templates) + 1,
						'teacher_id': teacher.id,
						'subject_id': entry["subject_id"],
						'group_ids': [(6, 0, entry["group_ids"])],
						'level_id': first_group.level_id.id,
						'study_id': first_group.study_id.id,
						'space_id': first_group.space_id.id,
						'attendance_schedule_ids': [],
					}
					templates[key] = template_vals

				template_vals["attendance_schedule_ids"].append(
					[0, 0, {
						'start_time': entry["hour_from"],
						'end_time': entry["hour_to"],
						'weekday': entry["dayofweek"],
						'space_id': template_vals["space_id"],
					}]
				)

		for key, template in old_items.items():
			if key not in new_items:
				# NOTE: archive (not unlink) so past attendance-taking history is preserved.
				template.action_archive()

		new_templates = self.env['ems.attendance_template'].create(list(templates.values()))
		for template in new_templates:
			template.fill_students()