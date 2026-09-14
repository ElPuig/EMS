from datetime import datetime, time, timedelta, timezone
from unittest.mock import patch

import pytz

from odoo.tests.common import TransactionCase

from .common import mock_outgoing_email


class TestEmployeeAutocheckout(TransactionCase):
    """models/employees/employee_autocheckout.py (hr.attendance extension) — previously
    entirely untested despite real business consequences (auto-closing attendance,
    notifying managers)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Approving an absence posts to the chatter and notifies its followers - see CLAUDE.md's
        # 'Email safety in tests'.
        mock_outgoing_email(cls)
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

    def _expected_utc(self, hour_float):
        """The naive UTC datetime '_get_last_working_hour' itself would produce for a plain
        local hour on 'self.today', as a fixed point of comparison for these tests.

        Deliberately mirrors that method's own timezone resolution ('employee._get_tz()':
        the employee's own tz, then their calendar's, then the company calendar's, then UTC -
        see hr.employee._get_tz()) rather than going through 'ems.datetime_utils' (which
        resolves a *company-wide* tz instead, for an unrelated purpose - the auto-checkout
        cron's own retry window). The two only happen to agree on a box where an admin's
        personal timezone was manually set to match the company's; a fresh install has no
        reason to do that, and asserting through the wrong one intermittently failed by
        exactly that offset (found 2026-09-09 via CI, where they diverge)."""
        tz = pytz.timezone(self.teacher._get_tz())
        hour, minute = int(hour_float), round((hour_float % 1) * 60)
        local = tz.localize(datetime.combine(self.today, time(hour, minute)))
        return local.astimezone(pytz.utc).replace(tzinfo=None)

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
        self.assertEqual(result, self._expected_utc(13.5))

    def test_auto_close_attendance_closes_after_scheduled_hour(self):
        # 'dayofweek' must match 'check_in' 's own date, not 'self.weekday' (cached at
        # setUpClass time) - the 2h offset below can push check_in onto the PREVIOUS calendar
        # day whenever this test happens to run shortly after UTC midnight, same class of bug
        # already avoided by 'test_create_auto_closes_stale_open_attendance' (found 2026-09-08:
        # CI ran this class at 00:12 UTC, so 'self.weekday' was Tuesday while check_in was still
        # Monday, and the slot never matched).
        check_in = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=2)
        self._add_slot(0.0, 0.02, dayofweek=str(check_in.weekday()))  # ~1 minute after midnight, already passed
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
        # 'dayofweek' derived from check_in's own date, not 'self.weekday' - see the identical
        # NOTE on 'test_auto_close_attendance_closes_after_scheduled_hour' above.
        check_in = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=3)
        self._add_slot(0.0, 0.02, dayofweek=str(check_in.weekday()))
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

    def test_write_check_out_same_day_mismatched_microseconds_does_not_crash(self):
        # Regression test (issue #422): a check_in stamped with microseconds (e.g.
        # datetime.now(), how a real kiosk/systray punch is stored) and a check_out
        # set without microseconds (e.g. typed by hand in the form, or computed by
        # _auto_close_attendance()) on the SAME calendar day used to make Odoo's
        # hr.attendance.overtime engine treat check_in's and check_out's "day start"
        # as two distinct instants for the exact same date (native
        # hr.attendance._get_day_start_and_day()'s replace(hour=0, minute=0,
        # second=0) never resets microsecond) — two INSERTs for the same
        # (employee_id, date) key in one statement, self-colliding against
        # hr_attendance_overtime's own UNIQUE(employee_id, date) index.
        check_in = datetime.combine(self.today, time(8, 0, 0, 123456))
        attendance = self.env['hr.attendance'].create({
            'employee_id': self.teacher.id, 'check_in': check_in,
        })
        check_out = datetime.combine(self.today, time(16, 0, 0))

        attendance.write({'check_out': check_out})

        overtime = self.env['hr.attendance.overtime'].search([
            ('employee_id', '=', self.teacher.id), ('date', '=', self.today),
        ])
        self.assertLessEqual(len(overtime), 1)

    def test_cron_auto_check_out_savepoint_isolates_failures(self):
        # A failure closing one employee's attendance must not abort the whole
        # transaction and take every other employee's close down with it (found
        # 2026-09: a bare try/except around a raised exception doesn't undo Postgres's
        # own "transaction aborted" state — only a savepoint rollback does). The
        # injected failure below runs real (invalid) SQL, so it genuinely poisons the
        # cursor the same way the production bug did — a plain Python-level
        # exception wouldn't exercise this at all.
        self.env.company.auto_check_out = True
        self.env.company.auto_checkout_mode = 'ems'
        self.env.company.auto_checkout_time = 0.0
        self.env.company.auto_checkout_retry_until = 24.0
        self.calendar.flexible_hours = False
        other_teacher = self.env['hr.employee'].create({
            'name': 'Test Autocheckout Teacher 2', 'employee_type': 'teacher',
        })
        other_teacher.resource_calendar_id.flexible_hours = False
        # '_order = "check_in desc"' on hr.attendance: 'failing' must sort before
        # 'healthy' for an unisolated abort to actually reach 'healthy' too.
        failing_check_in = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=2)
        healthy_check_in = failing_check_in - timedelta(minutes=1)
        self._add_slot(0.0, 0.02, dayofweek=str(failing_check_in.weekday()))
        self.env['resource.calendar.attendance'].create({
            'calendar_id': other_teacher.resource_calendar_id.id,
            'name': 'Test Slot', 'dayofweek': str(healthy_check_in.weekday()),
            'hour_from': 0.0, 'hour_to': 0.02, 'day_period': 'morning',
        })
        failing = self.env['hr.attendance'].create({
            'employee_id': self.teacher.id, 'check_in': failing_check_in,
        })
        healthy = self.env['hr.attendance'].create({
            'employee_id': other_teacher.id, 'check_in': healthy_check_in,
        })

        original_close = type(failing)._auto_close_attendance

        def _boom(self):
            if self.id == failing.id:
                self.env.cr.execute("SELECT * FROM ems_test_nonexistent_table_422")
            return original_close(self)

        with patch.object(type(failing), '_auto_close_attendance', _boom):
            self.env['hr.attendance']._cron_auto_check_out()

        self.assertFalse(failing.check_out)
        self.assertTrue(healthy.check_out)

    def test_create_close_failure_is_isolated_and_notifies(self):
        # Mirrors test_cron_auto_check_out_savepoint_isolates_failures for the
        # create()-triggered backup path: a real (SQL-level) failure while
        # auto-closing a stale attendance must not corrupt the transaction, and
        # must notify the Academic Admins - the same robustness the cron already
        # has, now shared via _close_stale_attendance_safely().
        self.env.company.auto_check_out = True
        self.calendar.flexible_hours = False
        stale_check_in = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=1)
        self._add_slot(0.0, 0.02, dayofweek=str(stale_check_in.weekday()))
        stale = self.env['hr.attendance'].create({
            'employee_id': self.teacher.id, 'check_in': stale_check_in,
        })

        def _boom(self):
            self.env.cr.execute("SELECT * FROM ems_test_nonexistent_table_422")

        # Spy on the notify call rather than asserting on persisted mail.activity
        # state: verified separately (not asserted here, see
        # _notify_close_failure()'s own docstring) that when the notify happens
        # nested inside the very create() call that goes on to fail its own
        # native validation right after (exactly this scenario), the activity it
        # schedules is not reliably kept - a known, accepted gap, not something
        # this test should flake on. What's guaranteed and worth asserting is
        # that a close failure always triggers the notify call, on the right
        # record - the cron or the employee's next real check-in will pick the
        # still-open attendance back up regardless.
        with patch.object(type(stale), '_auto_close_attendance', _boom), \
             patch.object(type(stale), '_notify_close_failure', autospec=True) as notify_mock:
            with self.assertRaises(Exception) as failure:
                self.env['hr.attendance'].create({
                    'employee_id': self.teacher.id,
                    'check_in': datetime.now(timezone.utc).replace(tzinfo=None),
                })

        # The stale attendance stayed open (close failed) so Odoo's own native
        # validation blocked the new check-in - proof the raw injected SQL error
        # never escaped uncontrolled, only the transaction-safe outcome did.
        self.assertIn("hasn't checked out since", str(failure.exception))
        self.assertFalse(stale.check_out)
        notify_mock.assert_called_once_with(stale)

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

    # --- Approved absences shorten the working day ------------------------------------------
    #
    # An auto check-out that reads the raw weekly timetable closes the attendance at the end of
    # a day the employee was partly on leave for, crediting hours they had permission to miss.
    # See docs/en/developers/employees/absence.md.

    def _approved_absence(self, day, hour_from=None, hour_to=None):
        vals = {
            'employee_id': self.teacher.id,
            'holiday_status_id': self.env.ref('ems.leave_type_justified').id,
            'request_date_from': day,
            'request_date_to': day,
            'ems_submitted': True,
            'ems_responsible_declaration': True,
        }
        if hour_from is None:
            vals['ems_full_day'] = True
        else:
            vals.update({'ems_full_day': False,
                         'request_hour_from': hour_from, 'request_hour_to': hour_to})
        leave = self.env['hr.leave'].create(vals)
        leave.action_approve()
        return leave

    def test_an_approved_afternoon_absence_moves_the_check_out_earlier(self):
        """The teacher leaves at 14:00 with the afternoon approved and forgets to check out:
        the attendance must close at 14:00, not at the untouched end of their timetable."""
        self._add_slot(8.0, 14.0)
        self._add_slot(15.0, 18.0)
        self._approved_absence(self.today, hour_from=15.0, hour_to=18.0)

        result = self.env['hr.attendance']._get_last_working_hour(self.teacher, self.today)

        self.assertEqual(result, self._expected_utc(14.0),
            "the afternoon was approved off, so 14:00 is the last hour actually expected")

    def test_without_any_absence_the_whole_timetable_still_counts(self):
        """The fix must not move the check-out on an ordinary day."""
        self._add_slot(8.0, 14.0)
        self._add_slot(15.0, 18.0)

        result = self.env['hr.attendance']._get_last_working_hour(self.teacher, self.today)

        self.assertEqual(result, self._expected_utc(18.0))

    def test_a_whole_day_absence_leaves_nothing_to_close_at(self):
        """Nothing was expected of them at all, so there is no scheduled hour to close at and
        the attendance is deliberately left open for a human to correct - inventing an hour
        here is exactly what this fix is removing.

        Must land on a real Mon-Fri workday, not necessarily 'self.today': a whole-day absence's
        duration is computed by 'ems.absence._ems_working_days', which counts Mon-Fri days only
        (the centre's own business rule, unrelated to any calendar slot a test contrives) - on a
        weekend that yields a 0-day duration, which hr_holidays' own action_validate() then reads
        as 'nobody was supposed to work that day at all' and refuses to approve, regardless of
        the slot added below. Same class of date-dependent flake test_absence.py's own _monday()
        helper already exists to avoid; found here 2026-09-12 when CI happened to run on a
        Saturday."""
        day = self.today
        while day.weekday() >= 5:
            day += timedelta(days=1)
        self._add_slot(8.0, 14.0, dayofweek=str(day.weekday()))
        self._approved_absence(day)

        self.assertIsNone(
            self.env['hr.attendance']._get_last_working_hour(self.teacher, day))

    def test_a_pending_request_does_not_move_the_check_out(self):
        """Only an approved absence frees the employee from those hours."""
        self._add_slot(8.0, 14.0)
        self._add_slot(15.0, 18.0)
        leave = self.env['hr.leave'].create({
            'employee_id': self.teacher.id,
            'holiday_status_id': self.env.ref('ems.leave_type_justified').id,
            'request_date_from': self.today, 'request_date_to': self.today,
            'ems_full_day': False, 'request_hour_from': 15.0, 'request_hour_to': 18.0,
            'ems_submitted': True, 'ems_responsible_declaration': True,
        })
        self.assertEqual(leave.state, 'confirm')

        result = self.env['hr.attendance']._get_last_working_hour(self.teacher, self.today)

        self.assertEqual(result, self._expected_utc(18.0))
