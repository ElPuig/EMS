from datetime import date

from odoo.tests.common import HttpCase, tagged

from .common import create_level_study, create_role_employee, create_role_user


@tagged('post_install', '-at_install')
class TestWorkingScheduleTutoringLevelTour(HttpCase):
    """Issue #846: a Department Chief gives a tutoring (ATAL/TT) card of a teacher's Schedule tab a
    level, marks a student support (ATAL) card as tutoring, and saves."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.level, cls.study = create_level_study(
            cls, 'TWSTL',
            level={'name': 'Tutoring Level Tour Level', 'declaration_code': 'eso'},
            study={'code': 'TWSTL001', 'name': 'Test Study (Tutoring Level Tour)', 'date': date.today()},
        )
        cls.subject = cls.env['ems.subject'].create({
            'code': 'TWSTL001', 'acronym': 'TWSTL', 'name': 'Tutoring Level Tour Subject',
            'study_ids': [(6, 0, [cls.study.id])],
        })
        cls.group = cls.env['ems.group'].create({
            'course': 1, 'acronym': 'TWSTLA', 'level_id': cls.level.id, 'study_id': cls.study.id,
        })
        cls.non_teaching = cls.env.ref('ems.non_teaching_tt')
        cls.non_teaching.declaration_code = 'tutoring'
        NonTeaching = cls.env['ems.non_teaching_type'].with_context(active_test=False)
        cls.student_support = NonTeaching.search([('code', '=', 'ATAL')]) or NonTeaching.create(
            {'code': 'ATAL', 'name': 'Student support'})
        cls.student_support.write({'declaration_code': 'level_or_tutoring', 'active': True})
        cls.teacher = cls.env['hr.employee'].create({
            'name': 'Tutoring Level Tour Teacher', 'employee_type': 'teacher',
        })
        cls.teacher.resource_calendar_id.apply_schedule_changes([
            {'dayofweek': '0', 'hour_from': 20.0, 'hour_to': 21.0, 'day_period': 'afternoon',
             'non_teaching': cls.non_teaching.id, 'name': 'TT'},
            {'dayofweek': '1', 'hour_from': 20.0, 'hour_to': 21.0, 'day_period': 'afternoon',
             'subject_id': cls.subject.id, 'group_ids': [cls.group.id], 'name': 'TWSTL'},
            {'dayofweek': '2', 'hour_from': 20.0, 'hour_to': 21.0, 'day_period': 'afternoon',
             'non_teaching': cls.student_support.id, 'name': 'ATAL'},
        ])
        cls.chief = create_role_user(cls, 'department_chief', 'test_twstl_chief')
        create_role_employee(cls, cls.chief)

    def test_department_chief_sets_the_level_of_a_tutoring_block(self):
        self.start_tour("/odoo", "ems_working_schedule_tutoring_level", login=self.chief.login)

        blocks = self.teacher.resource_calendar_id.attendance_ids
        tutorship_time = blocks.filtered(lambda block: block.non_teaching == self.non_teaching)
        student_support = blocks.filtered(lambda block: block.non_teaching == self.student_support)
        self.assertEqual(tutorship_time.level_id, self.level)
        self.assertEqual(student_support.level_id, self.level)
        self.assertEqual(student_support.attention_type, 'tutoring')
        self.assertFalse(blocks.filtered('subject_id').level_id)
