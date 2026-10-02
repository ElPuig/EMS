# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from ..attendance.attendance_schedule import EmsAttendanceSchedule

# Context key: the caller already takes care of the rosters itself (see
# 'ems.enrollment._ems_move_group'), so a slot write must not resync them on its own.
EMS_SKIP_SLOT_RESYNC = 'ems_skip_slot_resync'


class EmsEnrollmentSlot(models.Model):
	"""One weekly slot a student attends for an enrolled subject - only stored for a CUSTOM
	enrollment (issue #534). An enrollment with no slot follows its group; see
	'ems.enrollment._ems_attends' and docs/en/developers/contacts/enrollment_slot.md."""
	_name = "ems.enrollment.slot"
	_description = "Enrollment slot: a weekly session a student attends for an enrolled subject"
	_order = 'student_id, subject_id, weekday, start_time'
	_sql_constraints = [
		('unique_enrollment_slot', 'UNIQUE(enrollment_id, group_id, weekday, start_time)',
		 'This student already attends this slot for this subject.'),
	]

	enrollment_id = fields.Many2one(string="Enrollment", comodel_name="ems.enrollment", required=True, ondelete='cascade', index=True)
	student_id = fields.Many2one(string="Student", related="enrollment_id.student_id", store=True, index=True)
	subject_id = fields.Many2one(string="Subject", related="enrollment_id.subject_id", store=True)
	group_id = fields.Many2one(string="Group", comodel_name="ems.group", required=True, ondelete='cascade',
		domain="[('id', 'in', allowed_group_ids)]")
	allowed_group_ids = fields.Many2many(string="Allowed groups", comodel_name="ems.group", compute="_compute_allowed_group_ids")

	# NOTE: the slot's key is (subject, group, weekday, start_time, end_time), never a foreign key to
	# 'ems.attendance_schedule' - the sync pipeline archives and clones schedule lines all the time,
	# while the key stays valid for as long as the class is still taught at that time.
	weekday = fields.Selection(string="Weekday", selection=EmsAttendanceSchedule.weekdays_selection, required=True)
	start_time = fields.Float(string="Start Time", required=True)
	end_time = fields.Float(string="End Time", required=True)

	# NOTE: not stored, both of them - they describe the CURRENT calendar, which changes without
	# this model ever being written. Picking a line in the UI only copies its key (see create/write).
	attendance_schedule_id = fields.Many2one(string="Session", comodel_name="ems.attendance_schedule",
		compute="_compute_attendance_schedule_id", readonly=False,
		domain="[('attendance_template_id.subject_id', '=', subject_id), ('attendance_template_id.group_ids', 'in', group_id)]")
	space_id = fields.Many2one(string="Space", comodel_name="ems.space", compute="_compute_attendance_schedule_id")
	state = fields.Selection(string="Status", selection=[('ok', "OK"), ('broken', "Not taught")],
		compute="_compute_attendance_schedule_id")

	@api.depends('enrollment_id.group_id', 'student_id.main_group_id')
	def _compute_allowed_group_ids(self):
		for slot in self:
			slot.allowed_group_ids = slot._ems_allowed_groups()

	@api.depends('subject_id', 'group_id', 'weekday', 'start_time', 'end_time')
	def _compute_attendance_schedule_id(self):
		for slot in self:
			line = slot._ems_matching_lines()[:1]
			slot.attendance_schedule_id = line
			slot.space_id = line.space_id
			slot.state = 'ok' if line else 'broken'

	@api.onchange('attendance_schedule_id')
	def _onchange_attendance_schedule_id(self):
		for slot in self:
			if slot.attendance_schedule_id:
				slot.update(self._ems_key_vals(slot.attendance_schedule_id))

	@api.constrains('enrollment_id', 'group_id')
	def _check_group_level(self):
		for slot in self:
			if slot.group_id not in slot._ems_allowed_groups():
				raise ValidationError(_(
					"The group %(group)s can't be used for %(subject)s: only groups of the same level as the "
					"student's enrollment can.",
					group=slot.group_id.display_name, subject=slot.subject_id.display_name,
				))

	@api.constrains('group_id', 'weekday', 'start_time', 'end_time')
	def _check_slot_is_taught(self):
		# NOTE: only checked when the key itself is written - a slot that stops matching later, because
		# a teacher's schedule changed, is expected to turn 'broken' instead of blocking that change.
		for slot in self:
			if not slot._ems_matching_lines():
				raise ValidationError(_(
					"The group %(group)s has no class of %(subject)s at that time.",
					group=slot.group_id.display_name, subject=slot.subject_id.display_name,
				))

	@api.model_create_multi
	def create(self, vals_list):
		vals_list = [self._ems_resolve_line_vals(vals) for vals in vals_list]
		previous = self._ems_snapshot_lines(self.env['ems.enrollment'].browse(
			{vals['enrollment_id'] for vals in vals_list if vals.get('enrollment_id')}))
		slots = super().create(vals_list)
		self._ems_resync(previous)
		return slots

	def write(self, vals):
		vals = self._ems_resolve_line_vals(vals)
		enrollments = self.enrollment_id
		if vals.get('enrollment_id'):
			enrollments |= self.env['ems.enrollment'].browse(vals['enrollment_id'])
		previous = self._ems_snapshot_lines(enrollments)
		res = super().write(vals)
		self._ems_resync(previous)
		return res

	def unlink(self):
		previous = self._ems_snapshot_lines(self.enrollment_id)
		res = super().unlink()
		self._ems_resync(previous)
		return res

	def _ems_allowed_groups(self):
		"""The enrollment's own group, plus every group of its level (any study) - the student's main
		group's level when the enrollment's group has none (a reinforcement group)."""
		self.ensure_one()
		group = self.enrollment_id.group_id
		level = group.level_id or self.student_id.main_group_id.level_id
		allowed = group
		if level:
			allowed |= self.env['ems.group'].sudo().search([('level_id', '=', level.id)])
		return allowed

	def _ems_matching_lines(self):
		"""The ACTIVE schedule lines this slot's key points at (normally one)."""
		self.ensure_one()
		if not (self.subject_id and self.group_id and self.weekday):
			return self.env['ems.attendance_schedule']
		return self.env['ems.attendance_schedule'].sudo().with_context(active_test=True).search([
			('attendance_template_id.active', '=', True),
			('attendance_template_id.subject_id', '=', self.subject_id.id),
			('attendance_template_id.group_ids', 'in', self.group_id.id),
			('weekday', '=', self.weekday),
			('start_time', '=', self.start_time),
			('end_time', '=', self.end_time),
		])

	@api.model
	def _ems_key_vals(self, line):
		return {'weekday': line.weekday, 'start_time': line.start_time, 'end_time': line.end_time}

	@api.model
	def _ems_resolve_line_vals(self, vals):
		"""'attendance_schedule_id' is how the UI picks a slot, but only its key is stored. 'student_id'
		comes along when the slot is created from the student's form (it is that One2many's inverse),
		but it is always the enrollment's own student."""
		vals = dict(vals)
		vals.pop('student_id', None)
		line_id = vals.pop('attendance_schedule_id', False)
		if line_id:
			line = self.env['ems.attendance_schedule'].sudo().browse(line_id)
			vals = {**self._ems_key_vals(line), **{key: value for key, value in vals.items() if key not in ('weekday', 'start_time', 'end_time')}}
		return vals

	@api.model
	def _ems_snapshot_lines(self, enrollments):
		"""{(student, subject): lines the student attends right now} for every pair 'enrollments'
		touches - taken before a change, so '_ems_resync' knows which lines to drop them from."""
		if self.env.context.get(EMS_SKIP_SLOT_RESYNC):
			return {}
		Enrollment = self.env['ems.enrollment'].sudo()
		return {
			(student, subject): Enrollment._ems_student_subject_enrollments(student, subject)._ems_attended_lines()
			for student, subject in {(enrollment.student_id, enrollment.subject_id) for enrollment in enrollments}
		}

	@api.model
	def _ems_resync(self, previous):
		Enrollment = self.env['ems.enrollment']
		for (student, subject), lines in previous.items():
			Enrollment._ems_resync_student_lines(student, subject, lines)
