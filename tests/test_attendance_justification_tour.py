from datetime import datetime

from odoo.tests.common import HttpCase, tagged

from .common import force_user_language_to_english


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
        # Dedicated student for the creation-flow tour, kept separate from cls.student/
        # cls.justification above so the two test methods stay independent of each other.
        cls.student2 = cls.env['res.partner'].create({
            'name': 'Attendance Justification Tour Student 2', 'contact_type': 'student',
        })

    def test_attendance_justification_open_and_edit_tour(self):
        force_user_language_to_english(self, self.env.ref('base.user_admin'))
        self.assertFalse(self.justification.notes)

        self.start_tour("/odoo", "ems_attendance_justification_open_and_edit", login="admin")

        self.assertEqual(self.justification.notes, 'Tour note')

    def test_attendance_justification_create_tour(self):
        force_user_language_to_english(self, self.env.ref('base.user_admin'))
        self.start_tour("/odoo", "ems_attendance_justification_create", login="admin")

        justification = self.env['ems.attendance_justification'].search([
            ('student_id', '=', self.student2.id),
            ('teacher_id', '=', self.teacher.id),
        ])
        self.assertEqual(len(justification), 1)
        # Confirmed empirically: the headless test browser's own timezone (not the logged-in
        # admin user's Europe/Madrid res.partner.tz) is what luxon uses to parse the typed
        # text, and it's UTC in this container - stored values match exactly what was typed.
        self.assertEqual(justification.start_date, datetime(2026, 2, 5, 9, 0))
        self.assertEqual(justification.end_date, datetime(2026, 2, 5, 11, 0))
