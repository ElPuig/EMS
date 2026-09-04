from datetime import date

from odoo.tests.common import HttpCase, tagged

from .common import create_level_study


@tagged('post_install', '-at_install')
class TestAttendanceSessionTour(HttpCase):
    """Roll-call ('Current') screen: covers what attendance_passlist_tour.js and
    attendance_status_tour.js don't - the same-day continuation (double period) banner and
    auto-copy, sorting, deleting a session, and guard mode (starting + marking a colleague's
    not-yet-started slot, with no delete button offered)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.level, cls.study = create_level_study(
            cls, 'TASG', level={'name': 'Test Level (Attendance Session Guard Tour)'},
            study={'code': 'TASG001', 'name': 'Test Study (Attendance Session Guard Tour)', 'date': date.today()},
        )
        cls.subject = cls.env['ems.subject'].create({
            'code': 'TASG001', 'acronym': 'TASG', 'name': 'Attendance Session Guard Tour Subject',
            'study_ids': [(6, 0, [cls.study.id])],
        })
        cls.group = cls.env['ems.group'].create({
            'course': 1, 'acronym': 'TASG', 'level_id': cls.level.id, 'study_id': cls.study.id,
            'name': 'Attendance Session Guard Tour Group',
        })
        cls.space = cls.env['ems.space'].create({
            'code': 'TASG-A', 'name': 'Test Space (Attendance Session Guard Tour)',
            'space_type_id': cls.env.ref('ems.space_type_classroom').id,
            'work_location_id': cls.env.ref('ems.work_location_main').id,
        })

        # Real teacher login, not admin - same reasoning as test_attendance_passlist_tour.py:
        # starting a session via the button resolves session_teacher_id from the clicking
        # user's own hr.employee (employee_type == 'teacher' required). This same teacher
        # plays double duty: owner of the two continuation periods, AND the one covering the
        # colleague's slot in Guard mode - both are genuine, independent uses of one real login.
        cls.teacher_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Attendance Session Guard Tour Teacher', 'login': 'test_teacher_attendance_session_guard_tour',
            'groups_id': [(4, cls.env.ref('ems.group_teacher').id), (4, cls.env.ref('base.group_user').id)],
        })
        cls.teacher_employee = cls.env['hr.employee'].create({
            'name': 'Attendance Session Guard Tour Teacher', 'employee_type': 'teacher',
            'user_id': cls.teacher_user.id,
        })
        # The colleague being covered in Guard mode never logs in - only their hr.employee
        # and schedule need to exist for get_guard_planned() to surface it to someone else.
        cls.other_employee = cls.env['hr.employee'].create({
            'name': 'Attendance Session Guard Tour Colleague', 'employee_type': 'teacher',
        })

        # Distinct firstname/lastname order on purpose (Zoe Aguilar / Ana Bosch) so the
        # lastname-vs-name sort actually produces two different orderings - a sort test that
        # can't tell the two apart would pass by accident either way.
        cls.student1 = cls.env['res.partner'].create({
            'name': 'Zoe Aguilar', 'firstname': 'Zoe', 'lastname': 'Aguilar',
            'contact_type': 'student', 'main_group_id': cls.group.id,
        })
        cls.student2 = cls.env['res.partner'].create({
            'name': 'Ana Bosch', 'firstname': 'Ana', 'lastname': 'Bosch',
            'contact_type': 'student', 'main_group_id': cls.group.id,
        })

        cls.template = cls.env['ems.attendance_template'].create({
            'teacher_ids': [(6, 0, [cls.teacher_employee.id])],
            'study_ids': [(6, 0, [cls.study.id])], 'subject_id': cls.subject.id,
            'group_ids': [(6, 0, [cls.group.id])],
            'start_date': date(2020, 1, 1), 'end_date': date(2030, 12, 31),
        })
        weekday = str(date.today().weekday())
        # Two back-to-back periods on the same template/day, deliberately NOT started here
        # (must stay "planned" so the tour drives onStartSession() for both, exercising the
        # continuation check - which compares this period's start against the *previous*
        # period's own end_time - for real, not just at the TransactionCase level).
        cls.schedule1 = cls.env['ems.attendance_schedule'].create({
            'attendance_template_id': cls.template.id, 'weekday': weekday,
            'start_time': 8.0, 'end_time': 9.0, 'space_id': cls.space.id,
            'student_ids': [(6, 0, [cls.student1.id, cls.student2.id])],
        })
        cls.schedule2 = cls.env['ems.attendance_schedule'].create({
            'attendance_template_id': cls.template.id, 'weekday': weekday,
            'start_time': 9.0, 'end_time': 10.0, 'space_id': cls.space.id,
            'student_ids': [(6, 0, [cls.student1.id, cls.student2.id])],
        })

        cls.guard_template = cls.env['ems.attendance_template'].create({
            'teacher_ids': [(6, 0, [cls.other_employee.id])],
            'study_ids': [(6, 0, [cls.study.id])], 'subject_id': cls.subject.id,
            'group_ids': [(6, 0, [cls.group.id])],
            'start_date': date(2020, 1, 1), 'end_date': date(2030, 12, 31),
        })
        # Unlike normal/Manual mode, Guard mode has no date/time override of its own - it always
        # filters both get_guard_sessions()/get_guard_planned()'s results down to whatever
        # matches the real wall-clock time (_isCurrentSlot() in attendance_session_view.js).
        # Spanning the whole day (same trick as test_strike_tour.py/test_attendance_passlist_tour.py)
        # keeps this "current" no matter what time this test happens to run at.
        cls.guard_schedule = cls.env['ems.attendance_schedule'].create({
            'attendance_template_id': cls.guard_template.id, 'weekday': weekday,
            'start_time': 0.0, 'end_time': 23.0, 'space_id': cls.space.id,
            'student_ids': [(6, 0, [cls.student1.id])],
        })

    def test_attendance_session_continuation_sort_and_delete_tour(self):
        self.start_tour("/odoo", "ems_attendance_session_continuation", login="test_teacher_attendance_session_guard_tour")

        # The second period's session was deleted at the end of the tour - only the first
        # period's remains.
        sessions = self.env['ems.attendance_session_header'].search([
            ('attendance_schedule_id', 'in', [self.schedule1.id, self.schedule2.id]),
        ])
        self.assertEqual(sessions.attendance_schedule_id, self.schedule1)

        line1 = sessions.attendance_session_line_ids.filtered(lambda l: l.student_id == self.student1)
        self.assertEqual(line1.status_id, self.env.ref('ems.attendance_status_delayed'))

    def test_attendance_session_guard_tour(self):
        self.start_tour("/odoo", "ems_attendance_session_guard", login="test_teacher_attendance_session_guard_tour")

        session = self.env['ems.attendance_session_header'].search([
            ('attendance_schedule_id', '=', self.guard_schedule.id),
        ])
        self.assertEqual(len(session), 1)
        self.assertEqual(session.session_teacher_id, self.teacher_employee)
        self.assertEqual(session.template_teacher_ids, self.other_employee)

        line = session.attendance_session_line_ids.filtered(lambda l: l.student_id == self.student1)
        self.assertEqual(line.status_id, self.env.ref('ems.attendance_status_delayed'))
