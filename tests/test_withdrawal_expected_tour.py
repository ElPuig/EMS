from datetime import date

from odoo.tests.common import HttpCase, tagged

from .common import create_level_study, create_role_employee, create_role_user, next_student_id, shift_ems_clock


@tagged('post_install', '-at_install')
class TestWithdrawalExpectedTour(HttpCase):
    """Issue #644: the expected withdrawal in a browser - the tutor (least privileged role that
    marks one) on the student's form, and a teacher's roll-call listing the student off it."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.today = shift_ems_clock(cls).date()  # 10:00 of the company's day
        cls.level, cls.study = create_level_study(cls, 'TWET', study={
            'name': 'Withdrawal Expected Tour Study', 'date': cls.today,
        }, level={'name': 'Withdrawal Expected Tour Level'})
        cls.subject = cls.env['ems.subject'].create({
            'code': 'TWET001', 'acronym': 'TWET', 'name': 'Withdrawal Expected Tour Subject',
            'study_ids': [(6, 0, [cls.study.id])],
        })
        cls.space = cls.env['ems.space'].create({
            'code': 'TWET-A', 'name': 'Withdrawal Expected Tour Space',
            'space_type_id': cls.env.ref('ems.space_type_classroom').id,
            'work_location_id': cls.env.ref('ems.work_location_main').id,
        })
        cls.tutor_user = create_role_user(cls, 'tutor', 'test_withdrawal_expected_tutor', name='Withdrawal Expected Tutor')
        cls.tutor = create_role_employee(cls, cls.tutor_user)
        cls.teacher_user = create_role_user(cls, 'teacher', 'test_withdrawal_expected_teacher', name='Withdrawal Expected Teacher')
        cls.teacher = create_role_employee(cls, cls.teacher_user, name='Withdrawal Expected Teacher')
        cls.group = cls.env['ems.group'].create({
            'course': 1, 'acronym': 'TWET', 'level_id': cls.level.id, 'study_id': cls.study.id,
            'tutor_id': cls.tutor.id,
        })
        cls.student = cls.env['res.partner'].create({
            'name': 'Leaving Student', 'contact_type': 'student', 'student_id': next_student_id(),
            'main_group_id': cls.group.id,
        })
        cls.classmate = cls.env['res.partner'].create({
            'name': 'Staying Student', 'contact_type': 'student', 'student_id': next_student_id(),
            'main_group_id': cls.group.id,
        })
        weekday = str(cls.today.weekday())
        # A class in the teacher's own schedule, so the student's Schedule tab has something: on a
        # Monday, since that tab only shows Monday to Friday and the suite may run at the weekend.
        cls.teacher.resource_calendar_id.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 11.0, 'hour_to': 12.0, 'day_period': 'morning',
            'subject_id': cls.subject.id, 'group_ids': [cls.group.id], 'name': 'Withdrawal Expected Tour class',
        }])
        for student in (cls.student, cls.classmate):
            cls.env['ems.enrollment'].create({'student_id': student.id, 'group_id': cls.group.id, 'subject_id': cls.subject.id})
        template = cls.env['ems.attendance_template'].create({
            'teacher_ids': [(6, 0, [cls.teacher.id])], 'study_ids': [(6, 0, [cls.study.id])],
            'subject_id': cls.subject.id, 'group_ids': [(6, 0, [cls.group.id])],
            'start_date': date(2020, 1, 1), 'end_date': date(2035, 12, 31),
        })
        cls.schedule = cls.env['ems.attendance_schedule'].create({
            'attendance_template_id': template.id, 'weekday': weekday,
            'start_time': 11.0, 'end_time': 12.0, 'space_id': cls.space.id,
            'student_ids': [(6, 0, [cls.student.id, cls.classmate.id])],
        })

    def test_tutor_marks_and_reverts(self):
        self.start_tour(f"/odoo/res.partner/{self.student.id}", "ems_withdrawal_expected_tutor",
                        login=self.tutor_user.login)
        self.assertFalse(self.student.withdrawal_expected)
        self.assertEqual(self.student.message_ids.tracking_value_ids.filtered(
            lambda value: value.field_id.name == 'withdrawal_expected').mapped('new_value_integer'), [0, 1])

    def test_roll_call_lists_the_student_off(self):
        self.student.with_user(self.tutor_user)._ems_mark_withdrawal_expected()
        self.start_tour("/odoo", "ems_withdrawal_expected_roll_call", login=self.teacher_user.login)
        session = self.env['ems.attendance_session_header'].search([('attendance_schedule_id', '=', self.schedule.id)])
        line = session.with_context(active_test=False).all_attendance_session_line_ids.filtered(
            lambda line: line.student_id == self.student)
        self.assertFalse(line.active)
        self.assertEqual(line.not_expected_reason, 'withdrawal')
