from datetime import datetime

from odoo.tests.common import HttpCase, tagged


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
        self.assertEqual(self.attendance.correction_count, 0)

        self.start_tour("/odoo", "ems_attendance_correction_request", login="admin")

        self.assertEqual(self.attendance.correction_count, 1)
        correction = self.attendance.correction_ids
        self.assertEqual(correction.reason, 'Tour: forgot to check out on time')
