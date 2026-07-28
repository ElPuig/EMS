# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class EmsAttendanceSchedule(models.Model):
    _name = "ems.attendance_schedule"
    _description = "Attendance schedule: concretes the weekdays data."
    _order = 'name asc'
    _inherit = ['ems.base', 'ems.datetime_utils']

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
    attendance_session_ids = fields.One2many(
        string="Sessions", comodel_name="ems.attendance_session_header", inverse_name="attendance_schedule_id")

    # Used only for permission filtering purposes (see security/rules/attendance.xml).
    teacher_ids = fields.Many2many(string='Teachers', related="attendance_template_id.teacher_ids", store=False)

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
        'ems.attendance_template.find_external_conflicts' (which mirrors this same logic against a
        not-yet-created entry dict, since one side isn't a record yet)."""
        self.ensure_one()
        other.ensure_one()
        template, other_template = self.attendance_template_id, other.attendance_template_id
        return template.subject_id == other_template.subject_id and bool(
            set(template.group_ids.ids) & set(other_template.group_ids.ids)
        )

    def unlink(self):
        if len(self.attendance_session_ids) > 0:
            raise ValidationError(_(
                "This schedule have been already used to check the student's attendances and cannot be deleted. "
                "Please, update its data instead or archive the entire template and create a new one with the "
                "correct data."))
        return super().unlink()
