from datetime import date, datetime, time, timedelta
from unittest.mock import patch

import pytz

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase

from .common import create_level_study, create_role_employee, create_role_user, mock_outgoing_email, next_student_id


# A fixed Wednesday: 'now' is frozen around it, so the fixtures never depend on when the suite runs.
REPORT_DAY = date(2030, 1, 9)
WEDNESDAY = str(REPORT_DAY.weekday())
THURSDAY = str((REPORT_DAY + timedelta(days=1)).weekday())
FRIDAY = str((REPORT_DAY + timedelta(days=2)).weekday())


class TestAttendanceReportSchedule(TransactionCase):
    """When a tutor's attendance issues report is due (res.users.ems_attendance_report_moment,
    models/attendance/attendance_report_schedule.py). See
    docs/en/developers/attendance/attendance_issue.md."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        cls.tutor_user = create_role_user(cls, 'tutor', 'report_tutor', email='report.tutor@example.com')
        cls.tutor = create_role_employee(cls, cls.tutor_user)
        # employee.create() already gave the tutor their own personal (empty) calendar.
        cls._add_slot(cls.tutor.resource_calendar_id, WEDNESDAY, 9.0, 14.0)
        cls._add_slot(cls.tutor.resource_calendar_id, FRIDAY, 10.0, 13.0)
        # The centre: Wednesday and Thursday only, so "next school day" is easy to tell apart.
        cls.env.company.default_schedule_framework_id = cls._calendar([(WEDNESDAY, 8.0, 21.5), (THURSDAY, 8.0, 21.5)])

        cls.level, cls.study = create_level_study(cls, 'TARS', study={
            'name': 'Test Study (Attendance Report)', 'date': REPORT_DAY,
        }, level={'name': 'Test Level (Attendance Report)'})
        cls.group = cls.env['ems.group'].create({
            'course': 2, 'acronym': 'TARS', 'level_id': cls.level.id, 'study_id': cls.study.id,
            'tutor_id': cls.tutor.id,
        })
        cls.first_year_group = cls.env['ems.group'].create({
            'course': 1, 'acronym': 'TARS', 'level_id': cls.level.id, 'study_id': cls.study.id,
        })
        cls.subject = cls.env['ems.subject'].create({
            'code': 'TARS001', 'acronym': 'TARS1', 'name': 'Test Subject (Attendance Report)',
            'study_ids': [(6, 0, [cls.study.id])],
        })
        cls.first_year_subject = cls.env['ems.subject'].create({
            'code': 'TARS002', 'acronym': 'TARS2', 'name': 'Test 1st-year Subject (Attendance Report)',
            'study_ids': [(6, 0, [cls.study.id])],
        })
        cls.student = cls.env['res.partner'].create({
            'name': 'Report Student', 'contact_type': 'student', 'student_id': next_student_id(),
            'main_group_id': cls.group.id,
        })

    @classmethod
    def _add_slot(cls, calendar, dayofweek, hour_from, hour_to):
        cls.env['resource.calendar.attendance'].create({
            'calendar_id': calendar.id, 'name': 'Report Slot', 'dayofweek': dayofweek,
            'hour_from': hour_from, 'hour_to': hour_to, 'day_period': 'morning',
        })

    @classmethod
    def _calendar(cls, slots):
        """A calendar whose only periods are 'slots' - (dayofweek, hour_from, hour_to)."""
        return cls.env['resource.calendar'].create({
            'name': 'Report Test Calendar',
            'attendance_ids': [(0, 0, {
                'name': 'Report Period', 'dayofweek': dayofweek, 'day_period': 'morning',
                'hour_from': hour_from, 'hour_to': hour_to,
            }) for dayofweek, hour_from, hour_to in slots],
        })

    def _utc(self, hour_float, day=REPORT_DAY):
        """Naive UTC datetime of a local (company timezone) hour on 'day'."""
        tz = pytz.timezone(self.env['ems.datetime_utils'].company_tz_name())
        hour, minute = int(hour_float), round((hour_float % 1) * 60)
        return tz.localize(datetime.combine(day, time(hour, minute))).astimezone(pytz.utc).replace(tzinfo=None)

    def _eta(self, now_hour, now_day=REPORT_DAY, issue_date=REPORT_DAY):
        with patch.object(fields.Datetime, 'now', return_value=self._utc(now_hour, now_day)):
            return self.tutor._ems_attendance_report_eta(issue_date)

    def _choose(self, moment, report_time=None):
        vals = {'ems_attendance_report_moment': moment}
        if report_time is not None:
            vals['ems_attendance_report_time'] = report_time
        self.tutor_user.write(vals)

    def _teach(self, group, subject, dayofweek, hour_from, hour_to):
        """A class of 'subject' in 'group', taught by a teacher of its own, with the student enrolled."""
        teacher = self.env['hr.employee'].create({'name': f'Report Teacher {group.course} {dayofweek}', 'employee_type': 'teacher'})
        teacher.resource_calendar_id.apply_schedule_changes([{
            'dayofweek': dayofweek, 'hour_from': hour_from, 'hour_to': hour_to, 'day_period': 'morning',
            'subject_id': subject.id, 'group_ids': [group.id], 'name': 'Report class',
        }])
        self.env['ems.enrollment'].create({'student_id': self.student.id, 'group_id': group.id, 'subject_id': subject.id})

    # --- the default: when the tutor's own working day ends ---------------------------------

    def test_default_is_end_of_own_working_day(self):
        self.assertEqual(self.tutor_user.ems_attendance_report_moment, 'teacher_end')
        self.assertEqual(self._eta(10.0), self._utc(14.0))

    def test_end_of_day_already_past_is_now(self):
        """A roll-call taken after that day's moment (or for a past day) is reported straight away."""
        self.assertEqual(self._eta(16.0), self._utc(16.0))
        self.assertEqual(self._eta(10.0, issue_date=REPORT_DAY - timedelta(days=7)), self._utc(10.0))

    def test_without_working_day_falls_back_to_end_of_centre_day(self):
        """Thursday: the tutor doesn't work, the centre does (until 21:30)."""
        thursday = REPORT_DAY + timedelta(days=1)
        self.assertEqual(self._eta(10.0, thursday, thursday), self._utc(21.5, thursday))

    # --- when the tutor's students' day ends ------------------------------------------------

    def test_students_end_counts_subjects_taken_in_another_group(self):
        """2nd-year student taking a 1st-year subject: their day ends with that group's class,
        later than their own group's."""
        self._choose('students_end')
        self._teach(self.group, self.subject, WEDNESDAY, 9.0, 13.0)
        self.assertEqual(self._eta(10.0), self._utc(13.0))
        self._teach(self.first_year_group, self.first_year_subject, WEDNESDAY, 15.0, 17.0)
        self.student.invalidate_recordset(['schedule_attendance_ids'])
        self.assertEqual(self._eta(10.0), self._utc(17.0))

    def test_students_end_ignores_other_weekdays(self):
        self._choose('students_end')
        self._teach(self.group, self.subject, WEDNESDAY, 9.0, 13.0)
        self._teach(self.first_year_group, self.first_year_subject, THURSDAY, 15.0, 20.0)
        self.assertEqual(self._eta(10.0), self._utc(13.0))

    # --- when the tutor's next working day starts -------------------------------------------

    def test_teacher_start_is_next_own_working_day(self):
        """Wednesday at noon: the next start is Friday's (Thursday is not a working day for them)."""
        self._choose('teacher_start')
        friday = REPORT_DAY + timedelta(days=2)
        self.assertEqual(self._eta(12.0), self._utc(10.0, friday))

    def test_teacher_start_before_own_start_is_same_day(self):
        self._choose('teacher_start')
        self.assertEqual(self._eta(8.0), self._utc(9.0))

    def test_teacher_start_on_long_leave_falls_back_to_end_of_centre_day(self):
        """No working day for them in the next two weeks: the report doesn't wait for their return."""
        self._choose('teacher_start')
        self.tutor.resource_calendar_id.attendance_ids.unlink()
        self.assertEqual(self._eta(12.0), self._utc(21.5))

    # --- at a fixed time ---------------------------------------------------------------------

    def test_fixed_time_today_or_next_school_day(self):
        self._choose('fixed_time', 21 + 20 / 60)
        self.assertEqual(self._eta(10.0), self._utc(21 + 20 / 60))
        thursday = REPORT_DAY + timedelta(days=1)
        self.assertEqual(self._eta(22.0), self._utc(21 + 20 / 60, thursday))

    def test_fixed_time_skips_days_without_school(self):
        """Thursday night: Friday to Tuesday have no school in this centre, so next Wednesday."""
        self._choose('fixed_time', 8.0)
        thursday = REPORT_DAY + timedelta(days=1)
        self.assertEqual(self._eta(22.0, thursday, thursday), self._utc(8.0, REPORT_DAY + timedelta(days=7)))

    def test_fixed_time_must_be_a_time_of_day(self):
        with self.assertRaises(ValidationError):
            self._choose('fixed_time', 24.0)

    # --- the preference -----------------------------------------------------------------------

    def test_tutor_sets_own_preference_from_profile(self):
        self.tutor_user.with_user(self.tutor_user).write({
            'ems_attendance_report_moment': 'fixed_time', 'ems_attendance_report_time': 21.5,
        })
        self.assertEqual(self.tutor_user.ems_attendance_report_moment, 'fixed_time')
        self.assertEqual(self.tutor_user.ems_attendance_report_time, 21.5)

    def test_only_group_tutors_are_tutors(self):
        """The ems.group_tutor role isn't enough: a Department Chief gets it without tutoring."""
        self.assertTrue(self.tutor_user.ems_is_tutor)
        chief = create_role_user(self, 'department_chief', 'report_chief')
        create_role_employee(self, chief)
        self.assertTrue(chief.has_group('ems.group_tutor'))
        self.assertFalse(chief.ems_is_tutor)

    def test_changing_preference_moves_pending_report(self):
        issue = self.env['ems.attendance_issue_tutor'].create({'tutor_id': self.tutor.id, 'issue_date': REPORT_DAY})
        with patch.object(fields.Datetime, 'now', return_value=self._utc(10.0)):
            issue._schedule_tutor_report()
            self.assertEqual(issue.notification_id.eta, self._utc(14.0))
            self._choose('fixed_time', 20.0)
        self.assertEqual(issue.notification_id.eta, self._utc(20.0))
