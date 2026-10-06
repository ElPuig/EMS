# -*- coding: utf-8 -*-

from datetime import timedelta

import pytz

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

# How many days ahead a "next" moment is looked for before falling back (a tutor on long leave,
# a tutor without schedule...).
REPORT_LOOKAHEAD_DAYS = 14
# Moments at the end of the day the reported data belongs to; the others are the next one after now.
END_OF_DAY_MOMENTS = ('teacher_end', 'students_end')
# States of a report job that has not started yet, so a new issue can still join it.
PENDING_JOB_STATES = ('wait_dependencies', 'pending')


class EmsAttendanceReportUsers(models.Model):
    """When a tutor receives their attendance issues report: every issue not reported yet goes in
    the next one, whatever the moment chosen. See docs/en/developers/attendance/attendance_issue.md."""
    _inherit = 'res.users'

    ems_attendance_report_moment = fields.Selection(
        selection=[
            ('teacher_end', "When my working day ends"),
            ('students_end', "When my students' day ends"),
            ('teacher_start', "When my next working day starts"),
            ('fixed_time', "At a fixed time"),
        ],
        string="Attendance issues report", default='teacher_end', required=True,
        help="When you receive, as a tutor, the email with your students' attendance issues. Each "
             "email includes every issue recorded since the previous one.")
    ems_attendance_report_time = fields.Float(
        string="Attendance issues report time",
        default=lambda self: self.env.company.attendance_issue_tutor_default,
        help="Every working day of the centre, at this time.")
    # Whether the user actually tutors a group: the report only concerns them. Not the
    # ems.group_tutor role, which Department Chiefs, Heads of Studies and the Director also get.
    ems_is_tutor = fields.Boolean(string="Is a group tutor", compute='_compute_ems_is_tutor', compute_sudo=True)

    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS + ['ems_attendance_report_moment', 'ems_attendance_report_time', 'ems_is_tutor']

    @property
    def SELF_WRITEABLE_FIELDS(self):
        return super().SELF_WRITEABLE_FIELDS + ['ems_attendance_report_moment', 'ems_attendance_report_time']

    def _compute_ems_is_tutor(self):
        tutors = self.env['ems.group'].search([('tutor_id.user_id', 'in', self.ids)]).tutor_id.user_id
        for user in self:
            user.ems_is_tutor = user in tutors

    @api.constrains('ems_attendance_report_time')
    def _check_ems_attendance_report_time(self):
        for user in self:
            if not 0 <= user.ems_attendance_report_time < 24:
                raise ValidationError(_("The attendance issues report time must be between 00:00 and 23:59."))

    def write(self, vals):
        res = super().write(vals)
        if {'ems_attendance_report_moment', 'ems_attendance_report_time'} & set(vals):
            self.sudo().employee_ids._ems_reschedule_attendance_report()
        return res


class EmsAttendanceReportEmployee(models.Model):
    """The moment a tutor's attendance issues report is due, from their user's preference."""
    _inherit = 'hr.employee'

    def _ems_attendance_report_eta(self, issue_date):
        """Naive UTC moment the tutor's next report is due, for issues of issue_date: always after
        now. A roll-call taken once that day's moment has passed waits for the next one: due now,
        each roll-call click went out in its own email (issue #588)."""
        self.ensure_one()
        now = fields.Datetime.now()
        moment = self.user_id.ems_attendance_report_moment or 'teacher_end'
        if moment in END_OF_DAY_MOMENTS:
            due = (self._ems_attendance_report_moment_on(moment, issue_date)
                   or self._ems_attendance_report_fallback(issue_date))
            if due > now:
                return due
        today = self.env['ems.datetime_utils'].utc_datetime_to_local(pytz.utc.localize(now)).date()
        days = [today + timedelta(days=offset) for offset in range(REPORT_LOOKAHEAD_DAYS)]
        candidates = (self._ems_attendance_report_moment_on(moment, day) for day in days)
        due = next((candidate for candidate in candidates if candidate and candidate > now), None)
        # The fallback always finds one: the company's default time, tomorrow at the latest.
        return due or next(fallback for fallback in map(self._ems_attendance_report_fallback, days) if fallback > now)

    def _ems_attendance_report_moment_on(self, moment, day):
        """Naive UTC moment of 'moment' on 'day', or None when there is none that day (no
        working day for the tutor, no class for their students, no school day)."""
        datetime_utils = self.env['ems.datetime_utils']
        if moment == 'fixed_time':
            if not self.company_id._ems_default_framework_intervals(day):
                return None
            return datetime_utils.datetime_to_odoo(
                datetime_utils.time_float_to_utc_datetime(day, self.user_id.ems_attendance_report_time))
        if moment == 'students_end':
            hour_to = self._ems_students_day_end(day)
            if hour_to is None:
                return None
            return datetime_utils.datetime_to_odoo(datetime_utils.time_float_to_utc_datetime(day, hour_to))
        intervals = self._ems_workday_intervals(day)
        if not intervals:
            return None
        edge = max(end for _start, end in intervals) if moment == 'teacher_end' else min(start for start, _end in intervals)
        return edge.astimezone(pytz.utc).replace(tzinfo=None)

    def _ems_students_day_end(self, day):
        """Local float hour the last class of the tutor's students ends on 'day', from each
        student's own schedule (a subject taken in another group counts), or None."""
        Attendance = self.env['resource.calendar.attendance']
        weekday = str(day.weekday())
        week_type = str(Attendance.get_week_type(day))
        students = self.env['res.partner'].sudo().search([('contact_type', '=', 'student'), ('tutor_id', '=', self.id)])
        hours = [
            attendance.hour_to
            for student in students
            for attendance in student._ems_teaching_attendances()
            if attendance.dayofweek == weekday and not attendance.display_type
            and not (attendance.two_weeks_calendar and attendance.week_type != week_type)
        ]
        return max(hours) if hours else None

    def _ems_attendance_report_fallback(self, day):
        """When the chosen moment can't be found: the end of the centre's day, or the company's
        attendance_issue_tutor_default time without a schedule framework for that day."""
        intervals = self.company_id._ems_default_framework_intervals(day)
        if intervals:
            return max(end for _start, end in intervals).astimezone(pytz.utc).replace(tzinfo=None)
        datetime_utils = self.env['ems.datetime_utils']
        return datetime_utils.datetime_to_odoo(datetime_utils.time_float_to_utc_datetime(
            day, self.company_id.attendance_issue_tutor_default))

    def _ems_reschedule_attendance_report(self):
        """Moves the tutors' pending report to their (new) preferred moment."""
        IssueTutor = self.env['ems.attendance_issue_tutor'].sudo()
        for employee in self:
            issues = IssueTutor.search([('tutor_id', '=', employee.id), ('notification_id.state', 'in', PENDING_JOB_STATES)])
            for job in issues.notification_id:
                first_day = min(issues.filtered(lambda issue: issue.notification_id == job).mapped('issue_date'))
                job.eta = employee._ems_attendance_report_eta(first_day)
