# -*- coding: utf-8 -*-

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase

from .common import create_level_study_group, create_role_employee, create_role_user, mock_outgoing_email


class TestQualityMinuteStart(TransactionCase):
    """Who can start each kind of minute (ems.minute.type.starter_role_ids and starter_scope): a
    teacher is only offered the kinds they can start, and only for their own scope."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        cls.generic = cls.env.ref('__import__.minute_type_generic')
        cls.dep = cls.env.ref('__import__.minute_type_dep')
        cls.claustre = cls.env.ref('__import__.minute_type_claustre')
        cls.teaching_team = cls.env.ref('__import__.minute_type_teaching_team')
        cls.team_const = cls.env.ref('__import__.minute_type_team_const')
        cls.team_meeting = cls.env.ref('__import__.minute_type_team_meeting')
        cls.department = cls.env['hr.department'].create({'name': 'Start Test Department'})
        cls.other_department = cls.env['hr.department'].create({'name': 'Start Test Other Department'})
        cls.teacher = create_role_user(cls, 'teacher', 'start.teacher@example.com')
        cls.teacher_employee = create_role_employee(cls, cls.teacher, name='Start Teacher', department_id=cls.department.id)
        cls.chief = create_role_user(cls, 'department_chief', 'start.chief@example.com')
        cls.chief_employee = create_role_employee(cls, cls.chief, name='Start Chief', department_id=cls.department.id)
        cls.department.manager_id = cls.chief_employee

    def _startable(self, user):
        return self.env['ems.minute.type'].with_user(user).search([('can_start', '=', True)])

    def _create(self, user, minute_type, **scope):
        return self.env['ems.minute'].with_user(user).create({'type_id': minute_type.id, **scope})

    def test_a_teacher_is_only_offered_what_they_can_start(self):
        startable = self._startable(self.teacher)
        self.assertIn(self.generic, startable)
        self.assertNotIn(self.dep, startable)
        self.assertNotIn(self.claustre, startable)
        self.assertNotIn(self.team_const, startable)
        with self.assertRaises(ValidationError):
            self._create(self.teacher, self.dep, department_id=self.department.id)

    def test_a_department_chief_starts_only_their_department_minutes(self):
        self.assertIn(self.dep, self._startable(self.chief))
        minute = self.env['ems.minute'].with_user(self.chief).new({'type_id': self.dep.id})
        self.assertTrue(minute.start_scope_restricted)
        self.assertEqual(minute.start_department_ids._origin, self.department)
        self._create(self.chief, self.dep, department_id=self.department.id)
        with self.assertRaises(ValidationError):
            self._create(self.chief, self.dep, department_id=self.other_department.id)

    def test_the_management_team_calls_the_staff_meeting(self):
        self.env.ref('ems.role_secretary').sudo().with_context(ems_syncing_roles=True).write(
            {'employee_ids': [(6, 0, self.teacher_employee.ids)]})
        self.assertIn(self.claustre, self._startable(self.teacher))
        self._create(self.teacher, self.claustre)

    def test_a_group_teacher_starts_its_teaching_team_minute(self):
        _level, study, group = create_level_study_group(self, 'MST')
        _level2, _study2, other_group = create_level_study_group(self, 'MSU')
        subject = self.env['ems.subject'].create({
            'code': 'MST001', 'acronym': 'MST', 'name': 'MST Subject', 'study_ids': [(6, 0, study.ids)]})
        self.env['ems.teaching'].create({'teacher_id': self.teacher_employee.id, 'group_id': group.id, 'subject_id': subject.id})
        self.assertIn(self.teaching_team, self._startable(self.teacher))
        self._create(self.teacher, self.teaching_team, group_id=group.id)
        with self.assertRaises(ValidationError):
            self._create(self.teacher, self.teaching_team, group_id=other_group.id)

    def test_an_improvement_team_member_holds_its_meetings_but_does_not_constitute_it(self):
        team = self.env['ems.workgroup'].create({'name': 'Start Test Team', 'employee_ids': [(4, self.teacher_employee.id)]})
        startable = self._startable(self.teacher)
        self.assertIn(self.team_meeting, startable)
        self.assertNotIn(self.team_const, startable)
        self._create(self.teacher, self.team_meeting, workgroup_id=team.id)

    def test_the_administrator_starts_anything(self):
        admin = create_role_user(self, 'academic_admin', 'start.admin@example.com')
        create_role_employee(self, admin, name='Start Admin', employee_type='asp')
        self.assertEqual(self._startable(admin), self.env['ems.minute.type'].search([]))
        self._create(admin, self.dep, department_id=self.other_department.id)
