from datetime import date, datetime

from odoo.tests.common import HttpCase, tagged

from .common import (
    create_level_study_group, create_role_employee, create_role_user, force_user_language_to_english,
    mock_outgoing_email, next_student_id,
)


@tagged('post_install', '-at_install')
class TestAttendanceJustificationTour(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.teacher = cls.env['hr.employee'].create({
            'name': 'Attendance Justification Tour Teacher', 'employee_type': 'teacher',
        })
        cls.student = cls.env['res.partner'].create({
            'name': 'Attendance Justification Tour Student', 'contact_type': 'student', 'student_id': next_student_id(),
        })
        cls.justification = cls.env['ems.attendance_justification'].create({
            'teacher_id': cls.teacher.id, 'student_id': cls.student.id,
            'start_date': datetime(2026, 1, 5, 9, 0), 'end_date': datetime(2026, 1, 5, 11, 0),
        })
        # Dedicated student for the creation-flow tour, kept separate from cls.student/
        # cls.justification above so the two test methods stay independent of each other.
        cls.student2 = cls.env['res.partner'].create({
            'name': 'Attendance Justification Tour Student 2', 'contact_type': 'student', 'student_id': next_student_id(),
        })
        cls._setup_tutor_justification()

    @classmethod
    def _setup_tutor_justification(cls):
        """A tutor's justification covering a miss in a session taught by another teacher
        (issue #469) - the tutor can read neither that session nor its schedule."""
        # Marking the line as a miss queues family notifications.
        mock_outgoing_email(cls)
        cls.tutor_user = create_role_user(cls, 'tutor', 'tour_tutor_attendance_justification')
        tutor = create_role_employee(cls, cls.tutor_user)
        other_teacher = cls.env['hr.employee'].create({
            'name': 'Attendance Justification Tour Other Teacher', 'employee_type': 'teacher',
        })
        __, study, group = create_level_study_group(cls, 'TJT', group={'tutor_id': tutor.id})
        student = cls.env['res.partner'].create({
            'name': 'Attendance Justification Tutor Tour Student', 'contact_type': 'student',
            'student_id': next_student_id(), 'main_group_id': group.id,
        })
        subject = cls.env['ems.subject'].create({
            'code': 'TJT001', 'acronym': 'TJT', 'name': 'Attendance Justification Tour Subject',
            'study_ids': [(6, 0, [study.id])],
        })
        cls.tutor_space = cls.env['ems.space'].create({
            'code': 'TJT-A', 'name': 'Attendance Justification Tour Space',
            'space_type_id': cls.env.ref('ems.space_type_classroom').id,
            'work_location_id': cls.env.ref('ems.work_location_main').id,
        })
        template = cls.env['ems.attendance_template'].create({
            'teacher_ids': [(6, 0, [other_teacher.id])], 'study_ids': [(6, 0, [study.id])],
            'subject_id': subject.id, 'group_ids': [(6, 0, [group.id])],
            'start_date': date(2020, 1, 1), 'end_date': date(2030, 12, 31),
        })
        session_date = date(2026, 2, 4)
        schedule = cls.env['ems.attendance_schedule'].create({
            'attendance_template_id': template.id, 'weekday': str(session_date.weekday()),
            'start_time': 10.0, 'end_time': 11.0, 'space_id': cls.tutor_space.id,
            'student_ids': [(6, 0, [student.id])],
        })
        session = cls.env['ems.attendance_session_header'].create({
            'attendance_schedule_id': schedule.id, 'date': session_date,
            'mode': 'scheduled', 'session_teacher_id': other_teacher.id,
        })
        line = session.attendance_session_line_ids.filtered(lambda l: l.student_id == student)
        line.status_id = cls.env.ref('ems.attendance_status_miss')
        cls.env['ems.attendance_justification'].create({
            'teacher_id': tutor.id, 'student_id': student.id,
            'start_date': datetime(2026, 2, 4, 0, 0), 'end_date': datetime(2026, 2, 4, 23, 59),
            'attendance_session_line_ids': [(6, 0, [line.id])],
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

    def test_attendance_justification_tutor_open_tour(self):
        # Logs in as a plain tutor, not admin: the bug (issue #469) only exists for a user
        # the teacher record rules restrict to their own sessions.
        self.start_tour("/odoo", "ems_attendance_justification_tutor_open", login=self.tutor_user.login)
