from datetime import datetime

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
