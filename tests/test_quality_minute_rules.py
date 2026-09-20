# -*- coding: utf-8 -*-

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase

from .common import create_role_employee, create_role_user


class TestQualityMinuteRules(TransactionCase):
    """Without record rules every teacher could read and write every minute, which is the gap these
    rules close. Worth testing because access rights alone say nothing about *which* records."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.type = cls.env.ref('__import__.minute_type_dep_ccff')
        cls.course = cls.env['ems.course'].search([('is_current', '=', True)], limit=1)
        cls.dep_a = cls.env['hr.department'].create({'name': 'Rules Department A'})
        cls.dep_b = cls.env['hr.department'].create({'name': 'Rules Department B'})
        # Distinct names on purpose: the helper derives the employee name from the user's, and the
        # working calendar it creates has a unique name constraint.
        cls.user_a = create_role_user(cls, 'teacher', 'rules.a@example.com', name='Rules Teacher A')
        cls.employee_a = create_role_employee(cls, cls.user_a, department_id=cls.dep_a.id)
        cls.user_b = create_role_user(cls, 'teacher', 'rules.b@example.com', name='Rules Teacher B')
        cls.employee_b = create_role_employee(cls, cls.user_b, department_id=cls.dep_b.id)

    def _minute(self, department, **overrides):
        vals = {'type_id': self.type.id, 'department_id': department.id, 'course_id': self.course.id,
                'date': fields.Date.context_today(self.env['ems.minute'])}
        vals.update(overrides)
        return self.env['ems.minute'].create(vals)

    def test_a_teacher_reads_their_own_department_minute(self):
        minute = self._minute(self.dep_a)
        self.assertTrue(minute.with_user(self.user_a).read(['name']))

    def test_a_teacher_does_not_read_another_department_minute(self):
        minute = self._minute(self.dep_b, attendee_ids=[(6, 0, [])])
        found = self.env['ems.minute'].with_user(self.user_a).search([('id', '=', minute.id)])
        self.assertFalse(found, "another department's minute is none of this teacher's business")

    def test_an_attendee_reads_the_minute_whatever_the_scope(self):
        public_a = self.env['hr.employee.public'].browse(self.employee_a.id)
        minute = self._minute(self.dep_b, attendee_ids=[(6, 0, public_a.ids)])
        self.assertTrue(minute.with_user(self.user_a).read(['name']))

    def test_an_approved_minute_cannot_be_edited_by_the_teaching_staff(self):
        public_a = self.env['hr.employee.public'].browse(self.employee_a.id)
        minute = self._minute(self.dep_a, redactor_employee_id=public_a.id)
        minute.section_value_ids.filtered(lambda value: value.required).content = "<p>Discussed.</p>"
        minute.action_submit()
        minute.action_approve()
        with self.assertRaises(AccessError):
            minute.with_user(self.user_a).write({'abstract': 'changed after approval'})

    def test_the_secretariat_sees_every_minute(self):
        minute = self._minute(self.dep_b)
        user = create_role_user(self, 'secretary', 'rules.secretary@example.com', name='Rules Secretary')
        create_role_employee(self, user, employee_type='asp')
        self.assertTrue(minute.with_user(user).read(['name']))

    def test_a_teacher_does_not_see_another_department_action_plan(self):
        minute = self._minute(self.dep_b)
        action = self.env['ems.quality.action'].create({
            'name': "Someone else's action", 'type': 'corrective', 'minute_id': minute.id,
            'course_id': self.course.id, 'department_id': self.dep_b.id,
        })
        found = self.env['ems.quality.action'].with_user(self.user_a).search([('id', '=', action.id)])
        self.assertFalse(found)

    def test_a_teacher_sees_the_action_they_are_responsible_for(self):
        public_a = self.env['hr.employee.public'].browse(self.employee_a.id)
        action = self.env['ems.quality.action'].create({
            'name': 'Mine to do', 'type': 'agreement', 'course_id': self.course.id,
            'department_id': self.dep_b.id, 'responsible_employee_ids': [(6, 0, public_a.ids)],
        })
        found = self.env['ems.quality.action'].with_user(self.user_a).search([('id', '=', action.id)])
        self.assertIn(action, found, "an action is visible to whoever has to do it, wherever it came from")
