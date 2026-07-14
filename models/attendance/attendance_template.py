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
		present are archived (attendance history is kept); templates whose combination persists have
		their (possibly stale) schedule lines and space_id refreshed from 'entries' instead of being
		left frozen at whatever they were the first time that combination was imported — otherwise a
		since-changed bell schedule for a subject/group that's still taught can silently collide with a
		genuinely new one at check_overlap() time. Newly created templates are auto-filled with the
		group's currently enrolled students. Shared by the employee 'Schedule' tab's grid widget (a
		live mid-course edit for a single teacher — see sync_from_schedule_batch() for the XML
		importer's own multi-teacher case)."""
		plan = self._plan_schedule_sync(teacher, entries, start_date=start_date)
		self._archive_stale_schedule_sync(plan)
		self._write_schedule_sync(plan)

	def sync_from_schedule_batch(self, teacher_entries, start_date=None):
		"""Same as sync_from_schedule(), but for several teachers at once — the XML importer's normal
		case, since one planner file typically describes many teachers. 'teacher_entries' is a list of
		(teacher, entries) pairs, one per teacher, same shape as sync_from_schedule()'s own arguments.

		Archives every teacher's stale schedule lines FIRST, across the WHOLE batch, before writing ANY
		teacher's fresh ones — doing this one teacher at a time (i.e. just calling sync_from_schedule()
		per teacher) can raise a false check_overlap() collision when two teachers share a classroom:
		the first teacher's fresh line would be checked against the second teacher's still-active STALE
		line, since that second teacher hasn't been re-synced yet at that point."""
		plans = [self._plan_schedule_sync(teacher, entries, start_date=start_date) for teacher, entries in teacher_entries]
		for plan in plans:
			self._archive_stale_schedule_sync(plan)
		for plan in plans:
			self._write_schedule_sync(plan)

	def find_external_conflicts(self, teacher_entries):
		"""Given [(teacher, entries), ...] (same shape as sync_from_schedule_batch), find every
		currently active ems.attendance_schedule belonging to a DIFFERENT teacher — one NOT part of
		this batch — that would collide (same space, weekday, overlapping time) with one of the new
		entries. A batch only ever cleans up its own teachers' stale data (see
		'_archive_stale_schedule_sync'); a teacher who simply isn't in this particular file can still be
		left with an old schedule line in a classroom the new import now also wants at an overlapping
		time. Used both to preview what the import wizard is about to archive (before the user
		confirms) and, at actual import time, to archive those lines so the fresh ones can be written
		without a false check_overlap() — the returned lines, not their whole templates, since the rest
		of that external teacher's schedule is presumably still correct."""
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
					('attendance_template_id.teacher_id', 'not in', list(teacher_ids)),
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

	def _plan_schedule_sync(self, teacher, entries, start_date=None):
		"""Compute what a sync belongs to a single teacher without writing anything yet: which of the
		teacher's current templates are stale (gone, or persisting with different lines) and what the
		freshly imported entries, grouped by (subject, group-set) key, look like. Consumed by
		'_archive_stale_schedule_sync'/'_write_schedule_sync' — split out so 'sync_from_schedule_batch'
		can run the archive phase for every teacher before the write phase for any of them."""
		now = datetime.now()
		start_date = start_date or datetime(now.year, 9, 1)
		end_date = datetime(now.year + 1, 7, 1)

		# NOTE: maps to a RECORDSET, not a single template — a teacher can have more than one active
		# template for the same (subject, group-set) combo (a pre-existing data-quality issue: repeated
		# past imports created a new template instead of matching the existing one). Keying by a single
		# template here would silently drop every duplicate but the last one seen, leaving them forever
		# un-synced — see '_archive_stale_schedule_sync'/'_write_schedule_sync' for how duplicates get
		# consolidated into a single survivor.
		old_items = dict()
		for template in teacher.attendance_template_ids.filtered('active'):
			key = "%s.%s" % (template.subject_id.id, ",".join(str(g) for g in sorted(template.group_ids.ids)))
			old_items[key] = old_items.get(key, self.env['ems.attendance_template']) | template

		grouped_entries = dict()
		for entry in entries:
			key = "%s.%s" % (entry["subject_id"], ",".join(str(g) for g in sorted(entry["group_ids"])))
			grouped_entries.setdefault(key, []).append(entry)

		return {
			'teacher': teacher,
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

		templates = dict()
		for key, group_entries in grouped_entries.items():
			if key in old_items:
				continue
			# TODO: define default start and end date for subjects within settings.
			first_group = self.env['ems.group'].browse(group_entries[0]["group_ids"][0])
			templates[key] = {
				'start_date': plan['start_date'],
				'end_date': plan['end_date'],
				'color': len(templates) + 1,
				'teacher_id': plan['teacher'].id,
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