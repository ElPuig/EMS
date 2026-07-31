from datetime import date

from odoo.tests.common import HttpCase, tagged

from .common import create_level_study, mock_outgoing_email


@tagged('post_install', '-at_install')
class TestAttendanceIssueTour(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Marking a session line as missed triggers _update_notification(), which calls
        # send_notification() -> send_mail(force_send=True) - mocked per CLAUDE.md.
        mock_outgoing_email(cls)

        cls.level, cls.study = create_level_study(
            cls, 'TAIT',
            level={'name': 'Test Level (Attendance Issue Tour)'},
            study={'name': 'Test Study (Attendance Issue Tour)', 'date': date.today()},
        )
        cls.subject = cls.env['ems.subject'].create({
            'code': 'TAIT001', 'acronym': 'TAIT', 'name': 'Test Subject (Attendance Issue Tour)',
            'study_ids': [(6, 0, [cls.study.id])],
        })
        cls.space = cls.env['ems.space'].create({
            'code': 'TAIT-A', 'name': 'Test Space (Attendance Issue Tour)',
            'space_type_id': cls.env.ref('ems.space_type_classroom').id,
            'work_location_id': cls.env.ref('ems.work_location_main').id,
        })
        cls.teacher = cls.env['hr.employee'].create({
            'name': 'Attendance Issue Tour Teacher', 'employee_type': 'teacher',
        })
        cls.tutor_employee = cls.env['hr.employee'].create({
            'name': 'Attendance Issue Tour Tutor', 'employee_type': 'teacher',
        })
        cls.group = cls.env['ems.group'].create({
            'course': 1, 'acronym': 'TAIT', 'level_id': cls.level.id, 'study_id': cls.study.id,
            'tutor_id': cls.tutor_employee.id,
        })
        cls.student = cls.env['res.partner'].create({
            'name': 'Attendance Issue Tour Student', 'contact_type': 'student',
            'main_group_id': cls.group.id, 'student_email': 'attendance.issue.tour.student@example.com',
        })
        cls.template = cls.env['ems.attendance_template'].create({
            'teacher_ids': [(6, 0, [cls.teacher.id])], 'level_id': cls.level.id, 'study_id': cls.study.id,
            'subject_id': cls.subject.id, 'group_ids': [(6, 0, [cls.group.id])], 'space_id': cls.space.id,
            'start_date': date(2020, 1, 1), 'end_date': date(2030, 12, 31),
            'student_ids': [(6, 0, [cls.student.id])],
        })
        cls.schedule = cls.env['ems.attendance_schedule'].create({
            'attendance_template_id': cls.template.id, 'weekday': str(date.today().weekday()),
            'start_time': 8.0, 'end_time': 9.0, 'space_id': cls.space.id,
        })
        # NOTE: not named cls.session - HttpCase.authenticate() uses self.session internally
        # (a Werkzeug session object), and a same-named fixture attribute shadows it.
        cls.attendance_session = cls.env['ems.attendance_session_header'].create({
            'attendance_schedule_id': cls.schedule.id, 'date': date.today(),
            'mode': 'scheduled', 'session_teacher_id': cls.teacher.id,
        })
        line = cls.attendance_session.attendance_session_line_ids.filtered(lambda l: l.student_id == cls.student)
        line.status_id = cls.env.ref('ems.attendance_status_miss')

    def test_attendance_issue_drill_down_tour(self):
        self.start_tour("/odoo", "ems_attendance_issue_drill_down", login="admin")

    def test_attendance_issue_exception_popup_tour(self):
        issue_status = self.env['ems.attendance_issue_status'].search([
            ('attendance_issue_student_id.student_id', '=', self.student.id),
        ], limit=1)
        issue_status.notification_id.write({
            'state': 'failed', 'exc_info': 'Notification delivery failed (tour fixture).',
        })
        self.start_tour("/odoo", "ems_attendance_issue_exception_popup", login="admin")
