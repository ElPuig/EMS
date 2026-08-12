# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

from ..shared.attendance_mixin import EMS_BYPASS_TEMPLATE_LOCK_KEY

class EmsAttendanceSchedule(models.Model):
    _name = "ems.attendance_schedule"
    _description = "Attendance schedule: concretes the weekdays data."
    _order = 'name asc'
    _inherit = ['ems.base', 'ems.datetime_utils', 'ems.attendance_mixin']

    # Note: today.weekday() returns this values, do not alter!
    weekdays_selection = [
        ("0", "Monday"),
        ("1", "Tuesday"),
        ("2", "Wednesday"),
        ("3", "Thursday"),
        ("4", "Friday"),
        ("5", "Saturday"),
        ("6", "Sunday"),
    ]

    # Used to sort the dropdown within the session form, otherwise the SQL sort won't work.
    name = fields.Char(string="Name", compute="_compute_name", store=True)
    weekday = fields.Selection(string="Weekday", selection=weekdays_selection, default="1", required=True)

    start_time = fields.Float(string="Start Time", required=True)
    end_time = fields.Float(string="End Time", required=True)

    # Stored as datetimes (not floats alone) because timezone conversion needs a real date.
    start_date = fields.Datetime(compute="_compute_start_date", store=True)
    end_date = fields.Datetime(compute="_compute_end_date", store=True)

    space_id = fields.Many2one(string="Space", comodel_name="ems.space", required=True)
    attendance_template_id = fields.Many2one(
        string="Template", comodel_name="ems.attendance_template", ondelete='cascade', required=True)
    # NOTE: moved here from ems.attendance_template 2026-08-11 (see
    # plans/calendar_driven_attendance_templates.md, point 1) - the roster is a per-session-slot
    # concern (a specific day/time can genuinely have a different attendee list, e.g. someone
    # absent that day or an extra student sitting in), not a template-wide one. Domain/semantics
    # unchanged from the template's own former field - see 'fill_students'/'reload_students' below.
    student_ids = fields.Many2many(string="Students", comodel_name="res.partner", domain="[('contact_type', '=', 'student')]")
    # NOTE: copy=False - real attendance-taking history must never be duplicated when this line
    # (or its parent template, which drags its lines along) is cloned via '_write_or_new_version'.
    attendance_session_ids = fields.One2many(
        string="Sessions", comodel_name="ems.attendance_session_header", inverse_name="attendance_schedule_id",
        copy=False)

    # Used only for permission filtering purposes (see security/rules/attendance.xml).
    teacher_ids = fields.Many2many(string='Teachers', related="attendance_template_id.teacher_ids", store=False)

    # NOTE: drives this line's own lock (space_id/weekday/start_time/end_time) - once real
    # attendance has been taken for this specific line, those fields must never change in place.
    # The manual "Edit" button (action_new_version) that used to let an admin/teacher correct a
    # locked line by hand was removed 2026-08-11 (see
    # plans/calendar_driven_attendance_templates.md, point 3) - obsolete now that the calendar is
    # the only legitimate source of change; a correction happens by editing the teacher's working
    # schedule, and 'ems.attendance_mixin._write_or_new_version()' (still used internally by the
    # import wizard's own room-reassignment resolution, see working_schedule.py) applies it.
    has_sessions = fields.Boolean(string="Has sessions", compute="_compute_has_sessions")

    # NOTE: moved here from ems.attendance_template alongside 'student_ids' (2026-08-11, see
    # plans/calendar_driven_attendance_templates.md, point 1) - the "Students" tab now lives on
    # this model's own form, so it needs the same permission check the template's version had
    # (only an admin, one of the template's own teachers, or the record's creator can edit it).
    # Computed when loaded within a form or list, same as the template's own field.
    read_only_user = fields.Boolean(default=lambda self: self._get_read_only_user(), store=False)

    @api.depends('attendance_session_ids')
    def _compute_has_sessions(self):
        for schedule in self:
            schedule.has_sessions = bool(schedule.attendance_session_ids)

    def _get_read_only_user(self):
        return not (self.id == False or self.get_user_is_admin() or bool(self.teacher_ids.filtered(lambda teacher: teacher.user_id.id == self.env.uid)) or self.create_uid == self.env.uid)

    def action_open_form(self):
        """Opens this line's own full form as a dialog - a full class roster (a full group can be
        25-30 students) needs this model's own richer form (image/name/email/tutor columns), reached
        from this button instead of a cramped inline row on the parent template's embedded list
        (views/attendance/attendance_template/form.xml, itself read-only for logistics fields since
        the 2026-08-11 calendar-lock refinement). Added 2026-08-11 alongside 'student_ids' moving
        here - see plans/calendar_driven_attendance_templates.md, point 1."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'ems.attendance_schedule',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    time_range = fields.Char(compute="_compute_time_range", store=True)
    notes = fields.Text(string="Notes")

    @api.depends("start_time", "end_time")
    def _compute_time_range(self):
        for schedule in self:
            end = schedule.utc_datetime_to_local(schedule.end_date)
            start = schedule.utc_datetime_to_local(schedule.start_date)
            schedule.time_range = "%02d:%02d - %02d:%02d" % (start.hour, start.minute, end.hour, end.minute)

    @api.depends("start_time", "attendance_template_id.start_date")
    def _compute_start_date(self):
        for schedule in self:
            local = schedule.time_float_to_local_datetime(schedule.attendance_template_id.start_date, schedule.start_time)
            utc = schedule.local_datetime_to_utc(local)
            schedule.start_date = schedule.datetime_to_odoo(utc)

    @api.depends("end_time", "attendance_template_id.end_date")
    def _compute_end_date(self):
        for schedule in self:
            local = schedule.time_float_to_local_datetime(schedule.attendance_template_id.end_date, schedule.end_time)
            utc = schedule.local_datetime_to_utc(local)
            schedule.end_date = schedule.datetime_to_odoo(utc)

    @api.depends("attendance_template_id", "attendance_template_id.start_date", "attendance_template_id.end_date",
                 "weekday", "start_time", "end_time")
    def _compute_name(self):
        for schedule in self:
            weekday_str = dict(self.weekdays_selection).get(schedule.weekday)
            schedule.name = "%s | %s | %s" % (schedule.attendance_template_id.display_name, weekday_str, schedule.time_range)
            schedule.display_name = schedule.name

    @api.constrains('weekday', 'start_time', 'end_time', 'space_id')
    def check_overlap(self):
        for schedule in self:
            template = schedule.attendance_template_id
            if not template.active or not (template.start_date and template.end_date):
                continue

            candidates = self.search([
                ('id', '!=', schedule.id),
                ('weekday', '=', schedule.weekday),
                ('attendance_template_id.active', '=', True),
                ('attendance_template_id.start_date', '<=', template.end_date),
                ('attendance_template_id.end_date', '>=', template.start_date),
                '|',
                    ('teacher_ids', 'in', template.teacher_ids.ids),
                    ('space_id', '=', schedule.space_id.id),
            ])

            for other in candidates:
                if not schedule.ranges_overlap(schedule.start_time, schedule.end_time, other.start_time, other.end_time):
                    continue

                same_teacher = bool(set(other.teacher_ids.ids) & set(template.teacher_ids.ids))
                if not same_teacher and schedule.is_co_teaching_with(other):
                    # NOTE: same subject, sharing at least one group, different teacher, same room/time
                    # — this is the SAME class session co-taught by more than one teacher, a legitimate
                    # setup, not a genuine double-booking of the room by two unrelated sessions.
                    continue

                reason = _("the same teacher") if same_teacher else _("the same space")
                raise ValidationError(_(
                    "This session (%(this)s — %(this_teacher)s, %(this_space)s, %(this_time)s) overlaps with "
                    "another one (%(other)s — %(other_teacher)s, %(other_space)s, %(other_time)s): both fall on "
                    "%(weekday)s with overlapping times for %(reason)s.",
                    this=template.display_name,
                    this_teacher=", ".join(schedule.teacher_ids.mapped('display_name')),
                    this_space=schedule.space_id.display_name,
                    this_time=schedule.time_range,
                    other=other.attendance_template_id.display_name,
                    other_teacher=", ".join(other.teacher_ids.mapped('display_name')),
                    other_space=other.space_id.display_name,
                    other_time=other.time_range,
                    weekday=dict(schedule.weekdays_selection).get(schedule.weekday),
                    reason=reason,
                ))

    def is_co_teaching_with(self, other):
        """True if 'self' and 'other' represent the SAME class session co-taught by more than one
        teacher — same subject, sharing at least one group — rather than two unrelated sessions that
        happen to double-book the same room. Used by 'check_overlap' (here) and
        'ems.attendance_template.classify_external_conflicts' (which mirrors this same logic against
        a not-yet-created entry dict, since one side isn't a record yet)."""
        self.ensure_one()
        other.ensure_one()
        template, other_template = self.attendance_template_id, other.attendance_template_id
        return template.subject_id == other_template.subject_id and bool(
            set(template.group_ids.ids) & set(other_template.group_ids.ids)
        )

    def fill_students(self):
        """Reset 'student_ids' from this line's own template's current (subject_id, group_ids)
        enrollments - moved here from 'ems.attendance_template' 2026-08-11 (see
        plans/calendar_driven_attendance_templates.md, point 1). Subject/groups still live on the
        template (co-teaching/room stay template- and line-level concerns respectively - only the
        roster itself became per-line), so this reads them via 'attendance_template_id' rather than
        duplicating them here."""
        for schedule in self:
            template = schedule.attendance_template_id
            students = self.env['ems.enrollment'].search([
                ('group_id', 'in', template.group_ids.ids),
                ('subject_id', '=', template.subject_id.id)
            ]).mapped('student_id')
            schedule.student_ids = [(6, 0, students.ids)]

    def reload_students(self):
        self.student_ids = [(5)]
        self.fill_students()

    # NOTE: every field here except 'student_ids' is an identity/logistics concern that only ever
    # comes from the teacher's calendar (see plans/calendar_driven_attendance_templates.md, point 3
    # and its 2026-08-11 refinement) - a line's own weekday/time/room/template must never change by
    # hand, admin included; only the roster (add/remove students) is a genuine per-line, teacher-
    # editable concern. 'name' is a compute+store field with no inverse (already not writable via a
    # plain vals dict), so it isn't listed here.
    _LOCKED_FIELDS = {'active', 'weekday', 'start_time', 'end_time', 'space_id', 'attendance_template_id', 'notes'}

    def write(self, vals):
        if (set(vals) & self._LOCKED_FIELDS) and not self.env.context.get(EMS_BYPASS_TEMPLATE_LOCK_KEY):
            raise UserError(_(
                "This can only change as a consequence of editing the teacher's working "
                "schedule - update the schedule instead of editing this session directly."
            ))
        return super().write(vals)

    def unlink(self):
        if len(self.attendance_session_ids) > 0:
            raise ValidationError(_(
                "This schedule have been already used to check the student's attendances and cannot be deleted. "
                "Please, update its data instead or archive the entire template and create a new one with the "
                "correct data."))
        return super().unlink()
