from datetime import date

from odoo.tests.common import HttpCase, tagged

from .common import create_level_study


@tagged('post_install', '-at_install')
class TestAttendancePasslistTour(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.level, cls.study = create_level_study(
            cls, 'TATT', level={'name': 'Test Level (Attendance Take Tour)'},
            study={'code': 'TATT001', 'name': 'Test Study (Attendance Take Tour)', 'date': date.today()},
        )
        cls.subject = cls.env['ems.subject'].create({
            'code': 'TATT001', 'acronym': 'TATT', 'name': 'Test Subject (Attendance Take Tour)',
            'study_ids': [(6, 0, [cls.study.id])],
        })
        cls.group = cls.env['ems.group'].create({
            'course': 1, 'acronym': 'TATT', 'level_id': cls.level.id, 'study_id': cls.study.id,
            'name': 'Attendance Take Tour Group',
        })
        cls.space = cls.env['ems.space'].create({
            'code': 'TATT-A', 'name': 'Test Space (Attendance Take Tour)',
            'space_type_id': cls.env.ref('ems.space_type_classroom').id,
            'work_location_id': cls.env.ref('ems.work_location_main').id,
        })
        # Log in as a real teacher for this tour, not admin: _default_teacher_id()
        # (models/attendance/attendance_session.py) resolves session_teacher_id from the
        # CLICKING user's own hr.employee (employee_type == 'teacher' required) when a
        # session is created through the "Start session" button - this dev DB's real
        # "Administrator" account has employee_type='employee', not 'teacher' (confirmed
        # with the developer: expected - only real teachers start sessions, not admins).
        cls.teacher_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Attendance Take Tour Teacher', 'login': 'test_teacher_attendance_take_tour',
            'groups_id': [(4, cls.env.ref('ems.group_teacher').id), (4, cls.env.ref('base.group_user').id)],
        })
        cls.teacher_employee = cls.env['hr.employee'].create({
            'name': 'Attendance Take Tour Teacher', 'employee_type': 'teacher',
            'user_id': cls.teacher_user.id,
        })
        cls.student1 = cls.env['res.partner'].create({
            'name': 'Attendance Take Tour Student 1', 'contact_type': 'student',
            'main_group_id': cls.group.id,
        })
        cls.student2 = cls.env['res.partner'].create({
            'name': 'Attendance Take Tour Student 2', 'contact_type': 'student',
            'main_group_id': cls.group.id,
        })
        cls.template = cls.env['ems.attendance_template'].create({
            'teacher_ids': [(6, 0, [cls.teacher_employee.id])],
            'study_ids': [(6, 0, [cls.study.id])], 'subject_id': cls.subject.id,
            'group_ids': [(6, 0, [cls.group.id])], 'space_id': cls.space.id,
            'start_date': date(2020, 1, 1), 'end_date': date(2030, 12, 31),
            'student_ids': [(6, 0, [cls.student1.id, cls.student2.id])],
        })
        # start/end span the whole day so the schedule is "current" no matter what time this
        # test happens to run at (same trick as test_strike_tour.py). Deliberately NOT
        # creating a session here - it must still be "planned" so the tour can exercise
        # onStartSession(), not just an already-started one.
        cls.schedule = cls.env['ems.attendance_schedule'].create({
            'attendance_template_id': cls.template.id, 'weekday': str(date.today().weekday()),
            'start_time': 0.0, 'end_time': 23.0, 'space_id': cls.space.id,
        })
        # Second status by 'sequence' order (the same order the client's _loadStatuses() and
        # the tour's "2nd status column" click both rely on) - whatever it technically is,
        # clicking that same position must result in this status being set.
        cls.target_status = cls.env['ems.attendance_status'].search([], order='sequence')[1]

    def test_attendance_take_tour(self):
        self.start_tour("/odoo", "ems_attendance_take", login="test_teacher_attendance_take_tour")

        session = self.env['ems.attendance_session_header'].search([
            ('attendance_schedule_id', '=', self.schedule.id), ('date', '=', date.today()),
        ])
        self.assertEqual(len(session), 1)

        line1 = session.attendance_session_line_ids.filtered(lambda l: l.student_id == self.student1)
        self.assertEqual(line1.status_id, self.target_status)

        line2 = session.attendance_session_line_ids.filtered(lambda l: l.student_id == self.student2)
        self.assertEqual(line2.notes, 'Tour note for student 2')
