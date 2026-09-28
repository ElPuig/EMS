from datetime import date, datetime, time, timedelta

import pytz

from odoo.tests.common import TransactionCase

from .common import mock_outgoing_email


class TestPublicHoliday(TransactionCase):
    """models/employees/public_holiday.py (resource.calendar.leaves extension): a public holiday
    always applies to every working schedule, and a holiday or absence entered after the fact
    removes the "absence" technical attendances it made obsolete."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        cls.env.company.absence_management = True
        cls.teacher = cls.env['hr.employee'].create({
            'name': 'Test Public Holiday Teacher', 'employee_type': 'teacher',
        })
        # employee.create() already gave this teacher their own personal calendar: 09:00-14:00
        # every day of the week, so any date is a working day.
        cls.calendar = cls.teacher.resource_calendar_id
        cls.calendar.attendance_ids = [(5, 0, 0)] + [(0, 0, {
            'name': 'Test Slot', 'dayofweek': str(weekday), 'day_period': 'morning',
            'hour_from': 9.0, 'hour_to': 14.0,
        }) for weekday in range(7)]
        # The schedule a public holiday is most easily (and wrongly) tied to: the one whose
        # "Public Time Off" button it was created from.
        cls.other_calendar = cls.env['resource.calendar'].create({
            'name': 'Test Public Holiday Framework', 'is_framework': True,
        })
        cls.tz = pytz.timezone(cls.teacher._get_tz())
        cls.day = date(2031, 9, 24)
        cls.next_day = cls.day + timedelta(days=1)

    def _utc(self, day, hour=time.min):
        return self.tz.localize(datetime.combine(day, hour)).astimezone(pytz.utc).replace(tzinfo=None)

    def _holiday(self, day, hour_from=time.min, hour_to=time.max, **vals):
        return self.env['resource.calendar.leaves'].create({
            'name': 'Test Public Holiday',
            'date_from': self._utc(day, hour_from),
            'date_to': self._utc(day, hour_to).replace(microsecond=0),
            **vals,
        })

    def _technical_attendance(self, day):
        """What hr.attendance._cron_absence_detection() creates for a day nobody checked in."""
        check_in = self._utc(day)
        return self.env['hr.attendance'].create({
            'employee_id': self.teacher.id,
            'check_in': check_in,
            'check_out': check_in + timedelta(seconds=1),
            'in_mode': 'technical',
            'out_mode': 'technical',
        })

    def _overtime(self, day):
        return self.env['hr.attendance.overtime'].search([
            ('employee_id', '=', self.teacher.id), ('date', '=', day), ('adjustment', '=', False),
        ])

    def test_public_holiday_ignores_a_schedule(self):
        holiday = self._holiday(self.day, calendar_id=self.other_calendar.id)
        self.assertFalse(holiday.calendar_id)

    def test_public_holiday_ignores_the_schedule_from_the_context(self):
        """The "Public Time Off" smart button on a schedule's form sets default_calendar_id."""
        holiday = self.env['resource.calendar.leaves'].with_context(
            default_calendar_id=self.other_calendar.id,
        ).create({
            'name': 'Test Public Holiday',
            'date_from': self._utc(self.day),
            'date_to': self._utc(self.day, time(23, 59, 59)),
        })
        self.assertFalse(holiday.calendar_id)

    def test_public_holiday_cannot_be_tied_to_a_schedule_afterwards(self):
        holiday = self._holiday(self.day)
        holiday.calendar_id = self.other_calendar
        self.assertFalse(holiday.calendar_id)

    def test_personal_leave_keeps_its_schedule(self):
        leave = self._holiday(self.day, resource_id=self.teacher.resource_id.id)
        self.assertEqual(leave.calendar_id, self.calendar)

    def test_public_holiday_applies_to_a_personal_schedule(self):
        self._holiday(self.day, calendar_id=self.other_calendar.id)
        start = self.tz.localize(datetime.combine(self.day, time.min))
        self.assertFalse(self.teacher._get_expected_attendances(start, start + timedelta(days=1)))

    def test_holiday_entered_afterwards_removes_that_days_technical_attendance(self):
        absent = self._technical_attendance(self.day)
        absent_next_day = self._technical_attendance(self.next_day)
        self.assertLess(self._overtime(self.day).duration, 0)

        self._holiday(self.day)

        self.assertFalse(absent.exists())
        self.assertTrue(absent_next_day.exists(), "Only the holiday's own day is cleaned up.")
        self.assertFalse(self._overtime(self.day), "No negative overtime left on the holiday.")

    def test_holiday_tied_to_a_schedule_still_removes_the_technical_attendance(self):
        absent = self._technical_attendance(self.day)
        self._holiday(self.day, calendar_id=self.other_calendar.id)
        self.assertFalse(absent.exists())

    def test_real_attendance_on_a_holiday_is_kept(self):
        check_in = self._utc(self.day, time(9, 0))
        attendance = self.env['hr.attendance'].create({
            'employee_id': self.teacher.id,
            'check_in': check_in,
            'check_out': check_in + timedelta(hours=2),
        })
        self._holiday(self.day)
        self.assertTrue(attendance.exists())

    def test_partial_holiday_keeps_the_technical_attendance(self):
        """09:00-11:00 off still leaves 11:00-14:00 expected: the day is still a missed day."""
        absent = self._technical_attendance(self.day)
        self._holiday(self.day, hour_from=time(9, 0), hour_to=time(11, 0))
        self.assertTrue(absent.exists())

    def test_moving_a_holiday_cleans_up_its_new_day(self):
        absent_next_day = self._technical_attendance(self.next_day)
        holiday = self._holiday(self.day)
        self.assertTrue(absent_next_day.exists())

        holiday.write({
            'date_from': self._utc(self.next_day),
            'date_to': self._utc(self.next_day, time(23, 59, 59)),
        })

        self.assertFalse(absent_next_day.exists())

    def test_whole_day_personal_leave_removes_the_technical_attendance(self):
        """An absence approved after the fact becomes a personal leave covering that day."""
        absent = self._technical_attendance(self.day)
        self._holiday(self.day, resource_id=self.teacher.resource_id.id)
        self.assertFalse(absent.exists())

    def test_absence_detection_skips_a_holiday_entered_in_advance(self):
        """The native nightly job, run the day after a holiday entered in advance from a
        schedule's "Public Time Off" button, leaves no red attendance behind."""
        # The job's own notion of "yesterday" (datetime.today(), server time), so the test can't
        # drift a day from it around midnight.
        yesterday = datetime.today().date() - timedelta(days=1)
        self.env['resource.calendar.leaves'].with_context(
            default_calendar_id=self.other_calendar.id,
        ).create({
            'name': 'Test Public Holiday',
            'date_from': self._utc(yesterday),
            'date_to': self._utc(yesterday, time(23, 59, 59)),
        })

        self.env['hr.attendance']._cron_absence_detection()

        self.assertFalse(self.env['hr.attendance'].search([
            ('employee_id', '=', self.teacher.id), ('in_mode', '=', 'technical'),
        ]))
