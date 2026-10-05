from datetime import date

from odoo.tests.common import HttpCase, tagged

from .common import create_level_study, create_role_employee, create_role_user


@tagged('post_install', '-at_install')
class TestWorkingScheduleRoleEditTour(HttpCase):
    """Issue #531: a Department Chief removes a class from a teacher's Schedule tab and saves -
    the browser-side counterpart of TestScheduleEditRoles (see that class for the background)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.level, cls.study = create_level_study(
            cls, 'TWSRE',
            level={'name': 'Test Level (Working Schedule Role Edit Tour)'},
            study={'code': 'TWSRE001', 'name': 'Test Study (Working Schedule Role Edit Tour)', 'date': date.today()},
        )
        cls.subject = cls.env['ems.subject'].create({
            'code': 'TWSRE001', 'acronym': 'TWSRE', 'name': 'Role Edit Tour Subject',
            'study_ids': [(6, 0, [cls.study.id])],
        })
        cls.group = cls.env['ems.group'].create({
            'course': 1, 'acronym': 'TWSREA', 'level_id': cls.level.id, 'study_id': cls.study.id,
        })
        cls.teacher = cls.env['hr.employee'].create({
            'name': 'Role Edit Tour Teacher', 'employee_type': 'teacher',
        })
        cls.teacher.resource_calendar_id.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 20.0, 'hour_to': 21.0, 'day_period': 'afternoon',
            'subject_id': cls.subject.id, 'group_ids': [cls.group.id], 'name': 'TWSRE',
        }])
        cls.chief = create_role_user(cls, 'department_chief', 'test_twsre_chief')
        create_role_employee(cls, cls.chief)

    def test_department_chief_removes_a_class(self):
        self.assertTrue(self.teacher.teaching_ids)
        self.start_tour("/odoo", "ems_working_schedule_role_edit", login=self.chief.login)

        self.assertFalse(self.teacher.resource_calendar_id.attendance_ids.filtered('subject_id'))
        self.assertFalse(self.teacher.teaching_ids)
