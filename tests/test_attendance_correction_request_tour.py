from datetime import datetime, timedelta
from unittest.mock import patch

from odoo import fields
from odoo.tests.common import HttpCase, tagged

from .common import force_user_language_to_english


@tagged('post_install', '-at_install')
class TestAttendanceCorrectionRequestTour(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employee = cls.env['hr.employee'].create({
            'name': 'Attendance Correction Request Tour Employee', 'employee_type': 'teacher',
        })
        cls.attendance = cls.env['hr.attendance'].create({
            'employee_id': cls.employee.id,
            'check_in': datetime(2026, 1, 5, 8, 0),
            'check_out': datetime(2026, 1, 5, 16, 0),
        })

    def test_attendance_correction_request_tour(self):
        force_user_language_to_english(self, self.env.ref('base.user_admin'))
        self.assertEqual(self.attendance.correction_count, 0)

        self.start_tour("/odoo", "ems_attendance_correction_request", login="admin")

        self.assertEqual(self.attendance.correction_count, 1)
        correction = self.attendance.correction_ids
        self.assertEqual(correction.reason, 'Tour: forgot to check out on time')
        # attendance_id is readonly="1" in the form (only ever populated via the
        # "Request Correction" button's default_attendance_id context) - it must still
        # resolve to the real attendance so original_check_in/out get correctly snapshotted
        # (see create()'s context-default fallback and its regression test in
        # tests/test_attendance_correction.py).
        self.assertEqual(correction.attendance_id, self.attendance)
        self.assertEqual(correction.original_check_in, self.attendance.check_in)
        self.assertEqual(correction.original_check_out, self.attendance.check_out)

    def test_attendance_correction_request_open_within_schedule_tour(self):
        # Issue #479: the requested_check_out field must not even render while the employee
        # is still clocked in and still within today's expected working hours - a real browser
        # check, since a TransactionCase can't prove the invisible attribute actually hides it
        # (see tests/test_attendance_correction.py for the field-value-level coverage).
        force_user_language_to_english(self, self.env.ref('base.user_admin'))
        employee = self.env['hr.employee'].create({
            'name': 'Attendance Correction Open Schedule Tour Employee', 'employee_type': 'teacher',
        })
        # A fixed reference moment, not real "now": using the actual wall clock made this
        # flaky whenever the suite happened to run close to local midnight (Europe/Madrid) -
        # check_in was computed at fixture-setup time, but the server re-reads
        # fields.Datetime.now() later (once per request, while the tour interacts with the
        # dialog), and if the schedule's own hour_to fell in between those reads, "now" had
        # already rolled past it. Confirmed in practice 2026-09-16 (suite run just after local
        # midnight). Freezing fields.Datetime.now() for the whole tour, to the same reference
        # check_in is computed from, removes the wall-clock dependency entirely.
        frozen_now = datetime(2026, 1, 12, 10, 0)
        check_in = frozen_now - timedelta(hours=2)
        self.env['resource.calendar.attendance'].create({
            'calendar_id': employee.resource_calendar_id.id,
            'name': 'Tour Slot (Attendance Correction)',
            'dayofweek': str(check_in.weekday()),
            'hour_from': 0.0,
            'hour_to': 23.9,
            'day_period': 'morning',
        })
        attendance = self.env['hr.attendance'].create({
            'employee_id': employee.id,
            'check_in': check_in,
        })

        with patch.object(fields.Datetime, 'now', return_value=frozen_now):
            self.start_tour("/odoo", "ems_attendance_correction_request_open_within_schedule", login="admin")

        self.assertEqual(attendance.correction_count, 1)
        correction = attendance.correction_ids
        self.assertTrue(correction.requested_check_in)
        self.assertFalse(correction.requested_check_out)
