from datetime import datetime, timedelta, timezone

from odoo.tests.common import TransactionCase


class TestEmployeeAutocheckout(TransactionCase):
    """models/employees/employee_autocheckout.py (hr.attendance extension) — previously
    entirely untested despite real business consequences (auto-closing attendance,
    notifying managers)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.teacher = cls.env['hr.employee'].create({
            'name': 'Test Autocheckout Teacher', 'employee_type': 'teacher',
        })
        # employee.create() already gave this teacher their own personal calendar.
        cls.calendar = cls.teacher.resource_calendar_id
        cls.today = datetime.now(timezone.utc).date()
        cls.weekday = str(cls.today.weekday())

    def _add_slot(self, hour_from, hour_to, dayofweek=None):
        return self.env['resource.calendar.attendance'].create({
            'calendar_id': self.calendar.id,
            'name': 'Test Slot',
            'dayofweek': dayofweek or self.weekday,
            'hour_from': hour_from,
            'hour_to': hour_to,
            'day_period': 'morning',
        })

    def test_get_last_working_hour_none_without_calendar(self):
        employee = self.env['hr.employee'].create({
            'name': 'Test No Calendar Employee', 'employee_type': 'asp',
        })
        employee.resource_calendar_id = False
        attendance_model = self.env['hr.attendance']
        self.assertIsNone(attendance_model._get_last_working_hour(employee, self.today))

    def test_get_last_working_hour_none_without_slots_that_day(self):
        attendance_model = self.env['hr.attendance']
        self.assertIsNone(attendance_model._get_last_working_hour(self.teacher, self.today))

    def test_get_last_working_hour_returns_latest_slot(self):
        self._add_slot(8.0, 10.0)
        self._add_slot(10.0, 13.5)
        attendance_model = self.env['hr.attendance']
        result = attendance_model._get_last_working_hour(self.teacher, self.today)
        utils = self.env['ems.datetime_utils']
        expected = utils.datetime_to_odoo(utils.time_float_to_utc_datetime(self.today, 13.5))
        self.assertEqual(result, expected)

    def test_auto_close_attendance_closes_after_scheduled_hour(self):
        self._add_slot(0.0, 0.02)  # ~1 minute after midnight, already passed
        check_in = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=2)
        attendance = self.env['hr.attendance'].create({
            'employee_id': self.teacher.id, 'check_in': check_in,
        })

        closed = attendance._auto_close_attendance()

        self.assertTrue(closed)
        self.assertTrue(attendance.check_out)
        self.assertEqual(attendance.out_mode, 'auto_check_out')

    def test_auto_close_attendance_waits_for_scheduled_hour(self):
        far_future_hour = 23.9
        self._add_slot(0.0, far_future_hour)
        attendance = self.env['hr.attendance'].create({
            'employee_id': self.teacher.id,
            'check_in': datetime.now(timezone.utc).replace(tzinfo=None),
        })

        closed = attendance._auto_close_attendance()

        self.assertFalse(closed)
        self.assertFalse(attendance.check_out)

    def test_auto_close_attendance_false_without_schedule(self):
        attendance = self.env['hr.attendance'].create({
            'employee_id': self.teacher.id,
            'check_in': datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=2),
        })

        closed = attendance._auto_close_attendance()

        self.assertFalse(closed)
        self.assertFalse(attendance.check_out)

    def test_auto_close_attendance_fallback_when_scheduled_before_checkin(self):
        # Scheduled hour already passed relative to check_in itself (e.g. checked in very
        # late) — falls back to check_in + 1h instead of a check_out before check_in.
        self._add_slot(0.0, 0.02)
        check_in = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=3)
        attendance = self.env['hr.attendance'].create({
            'employee_id': self.teacher.id, 'check_in': check_in,
        })

        closed = attendance._auto_close_attendance()

        self.assertTrue(closed)
        self.assertAlmostEqual(
            (attendance.check_out - check_in).total_seconds(), 3600, delta=5,
        )

    def test_create_auto_closes_stale_open_attendance(self):
        self.env.company.auto_check_out = True
        self.calendar.flexible_hours = False
        stale_check_in = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=1)
        self._add_slot(0.0, 0.02, dayofweek=str(stale_check_in.weekday()))
        stale = self.env['hr.attendance'].create({
            'employee_id': self.teacher.id, 'check_in': stale_check_in,
        })
        self.assertFalse(stale.check_out)

        self.env['hr.attendance'].create({
            'employee_id': self.teacher.id,
            'check_in': datetime.now(timezone.utc).replace(tzinfo=None),
        })

        self.assertTrue(stale.check_out)

    def test_create_leaves_stale_attendance_when_auto_check_out_disabled(self):
        # With auto_check_out off, EMS never auto-closes the stale attendance, so Odoo's
        # own "already checked in" validation blocks the second check-in — same as it
        # would for any employee with no EMS auto-checkout configured at all.
        self.env.company.auto_check_out = False
        self._add_slot(0.0, 0.02)
        stale = self.env['hr.attendance'].create({
            'employee_id': self.teacher.id,
            'check_in': datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=1),
        })

        with self.assertRaises(Exception):
            self.env['hr.attendance'].create({
                'employee_id': self.teacher.id,
                'check_in': datetime.now(timezone.utc).replace(tzinfo=None),
            })

        self.assertFalse(stale.check_out)
