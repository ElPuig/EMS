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
		domain="[('id', 'in', allowed_schedule_ids)]")
	# NOTE: the session picker's choices, computed rather than a plain domain on 'group_id': with no
	# group picked yet, such a domain offered every group's sessions, and picking another group's
	# session left the row pointing at a class that doesn't exist (red).
	allowed_schedule_ids = fields.Many2many(string="Allowed sessions", comodel_name="ems.attendance_schedule",
		compute="_compute_allowed_schedule_ids")
	space_id = fields.Many2one(string="Space", comodel_name="ems.space", compute="_compute_attendance_schedule_id")
	state = fields.Selection(string="Status", selection=[('ok', "OK"), ('broken', "Not taught")],
		compute="_compute_attendance_schedule_id")

	@api.depends('enrollment_id.group_id', 'enrollment_id.subject_id', 'student_id.main_group_id')
	def _compute_allowed_group_ids(self):
		"""The groups the UI offers: those of the allowed level that actually have a class of this
		subject right now. Stricter than '_check_group_level' on purpose - a slot whose group stops
		teaching the subject must turn 'broken', not block later writes (e.g. moving the slots to a
		new enrollment when the main group changes)."""
		for slot in self:
			teaching = self.env['ems.attendance_template'].sudo().search([
				('active', '=', True), ('subject_id', '=', slot.subject_id.id),
			]).group_ids
			slot.allowed_group_ids = slot._ems_allowed_groups() & teaching

	@api.depends('subject_id', 'group_id', 'weekday', 'start_time', 'end_time')
	def _compute_attendance_schedule_id(self):
		for slot in self:
			line = slot._ems_matching_lines()[:1]
			slot.attendance_schedule_id = line
			slot.space_id = line.space_id
			slot.state = 'ok' if line else 'broken'

	@api.onchange('attendance_schedule_id')
	def _onchange_attendance_schedule_id(self):
		"""Picking a session sets the whole key, its group included, so the two can never disagree."""
		for slot in self:
			line = slot.attendance_schedule_id
			if line:
				slot.update({**self._ems_key_vals(line), 'group_id': slot._ems_group_of(line, slot.group_id)})

	@api.depends('subject_id', 'group_id', 'allowed_group_ids')
	def _compute_allowed_schedule_ids(self):
		"""The active sessions of the subject taught to the chosen group - or, before one is chosen,
		to any group the picker allows."""
		for slot in self:
			groups = slot.group_id or slot.allowed_group_ids
			slot.allowed_schedule_ids = self.env['ems.attendance_schedule'].sudo().with_context(active_test=True).search([
				('attendance_template_id.active', '=', True),
				('attendance_template_id.subject_id', '=', slot.subject_id.id),
				('attendance_template_id.group_ids', 'in', groups.ids),
			]) if slot.subject_id and groups else self.env['ems.attendance_schedule']

	@api.constrains('enrollment_id', 'group_id')
	def _check_group_level(self):
		for slot in self:
			if slot.group_id not in slot._ems_allowed_groups():
				raise ValidationError(_(
					"The group %(group)s can't be used for %(subject)s: only groups of the same level as the "
					"student's enrollment, or reinforcement groups, can.",
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
		"""The enrollment's own group, every group of its level (any study) - the student's main
		group's level when the enrollment's group has none - and every reinforcement group, which
		belongs to no level or study (the enrollment's own group can be one too)."""
		self.ensure_one()
		group = self.enrollment_id.group_id
		level = group.level_id or self.student_id.main_group_id.level_id
		domain = [('group_type', '=', 'reinforcement')]
		if level:
			domain = ['|', ('level_id', '=', level.id)] + domain
		return group | self.env['ems.group'].sudo().search(domain)

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
			group = self.env['ems.group'].browse(vals.get('group_id') or self[:1].group_id.id)
			vals = {
				**{key: value for key, value in vals.items() if key not in ('weekday', 'start_time', 'end_time')},
				**self._ems_key_vals(line),
				'group_id': self._ems_group_of(line, group).id,
			}
		return vals

	@api.model
	def _ems_group_of(self, line, group):
		"""'group' if 'line' is taught to it, otherwise the line's own group (the first one of a
		co-taught template)."""
		groups = line.attendance_template_id.group_ids
		return group if group in groups else groups[:1]

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
