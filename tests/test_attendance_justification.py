from datetime import datetime

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestAttendanceJustification(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.teacher = cls.env['hr.employee'].create({
            'name': 'Test Teacher (Attendance Justification)',
            'employee_type': 'teacher',
        })
        cls.student = cls.env['res.partner'].create({
            'name': 'Test Student (Attendance Justification)',
            'contact_type': 'student',
        })

    def test_overlapping_justification_raises(self):
        self.env['ems.attendance_justification'].create({
            'teacher_id': self.teacher.id,
            'student_id': self.student.id,
            'start_date': datetime(2026, 1, 5, 9, 0),
            'end_date': datetime(2026, 1, 5, 11, 0),
        })

        with self.assertRaises(ValidationError):
            self.env['ems.attendance_justification'].create({
                'teacher_id': self.teacher.id,
                'student_id': self.student.id,
                'start_date': datetime(2026, 1, 5, 10, 0),
                'end_date': datetime(2026, 1, 5, 12, 0),
            })

    def test_non_overlapping_justification_allowed(self):
        self.env['ems.attendance_justification'].create({
            'teacher_id': self.teacher.id,
            'student_id': self.student.id,
            'start_date': datetime(2026, 1, 5, 9, 0),
            'end_date': datetime(2026, 1, 5, 11, 0),
        })

        justification = self.env['ems.attendance_justification'].create({
            'teacher_id': self.teacher.id,
            'student_id': self.student.id,
            'start_date': datetime(2026, 1, 5, 11, 0),
            'end_date': datetime(2026, 1, 5, 13, 0),
        })
        self.assertTrue(justification.id)
