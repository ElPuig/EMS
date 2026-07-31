from datetime import datetime

from odoo.tests.common import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestAttendanceJustificationTour(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.teacher = cls.env['hr.employee'].create({
            'name': 'Attendance Justification Tour Teacher', 'employee_type': 'teacher',
        })
        cls.student = cls.env['res.partner'].create({
            'name': 'Attendance Justification Tour Student', 'contact_type': 'student',
        })
        cls.justification = cls.env['ems.attendance_justification'].create({
            'teacher_id': cls.teacher.id, 'student_id': cls.student.id,
            'start_date': datetime(2026, 1, 5, 9, 0), 'end_date': datetime(2026, 1, 5, 11, 0),
        })

    def test_attendance_justification_open_and_edit_tour(self):
        self.assertFalse(self.justification.notes)

        self.start_tour("/odoo", "ems_attendance_justification_open_and_edit", login="admin")

        self.assertEqual(self.justification.notes, 'Tour note')
