# -*- coding: utf-8 -*-

from datetime import timedelta

from odoo import fields
from odoo.tests.common import TransactionCase

from .common import create_role_user


class TestQualityAction(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.course = cls.env['ems.course'].search([('is_current', '=', True)], limit=1)
        if not cls.course:
            cls.course = cls.env['ems.course'].create({'start': 2026, 'end': 2027, 'is_current': True})
        cls.department = cls.env['hr.department'].create({'name': 'Quality Test Department'})
        cls.other_department = cls.env['hr.department'].create({'name': 'Quality Other Department'})

    def _action(self, **overrides):
        vals = {'name': 'Test agreement', 'type': 'agreement', 'course_id': self.course.id}
        vals.update(overrides)
        return self.env['ems.quality.action'].create(vals)

    def test_code_is_issued_on_create(self):
        action = self._action(department_id=self.department.id)
        self.assertTrue(action.code)
        self.assertTrue(action.code.startswith('ACORD-'), action.code)
        self.assertIn(self.course.short_code, action.code)

    def test_code_counter_is_per_scope(self):
        """Two departments each start their own numbering, which is what makes a gap visible."""
        first = self._action(department_id=self.department.id)
        second = self._action(department_id=self.department.id)
        other = self._action(department_id=self.other_department.id)
        self.assertNotEqual(first.code, second.code)
        self.assertEqual(first.code.rsplit('-', 1)[0], second.code.rsplit('-', 1)[0])
        self.assertNotEqual(first.code.rsplit('-', 1)[0], other.code.rsplit('-', 1)[0])
        self.assertEqual(other.code.rsplit('-', 1)[1], first.code.rsplit('-', 1)[1],
                         "a fresh scope starts its own counter from the same number")

    def test_centre_wide_actions_get_their_own_counter(self):
        action = self._action(is_centre=True)
        self.assertIn('-CEN-', action.code)

    def test_state_starts_as_new_and_becomes_analysed_when_planned(self):
        action = self._action(department_id=self.department.id)
        self.assertEqual(action.state, 'new')
        action.deadline_date = fields.Date.context_today(action) + timedelta(days=30)
        self.assertEqual(action.state, 'analysed')

    def test_state_follows_the_latest_followup(self):
        action = self._action(department_id=self.department.id)
        today = fields.Date.context_today(action)
        self.env['ems.quality.followup'].create({
            'action_id': action.id,
            'date': today - timedelta(days=10),
            'state': 'in_progress',
            'description': 'Started',
        })
        self.assertEqual(action.state, 'in_progress')
        self.env['ems.quality.followup'].create({
            'action_id': action.id,
            'date': today,
            'state': 'closed',
            'description': 'Finished',
        })
        self.assertEqual(action.state, 'closed')

    def test_state_uses_the_latest_entry_even_when_added_out_of_order(self):
        """Entries are written in whatever order they are remembered; the date decides."""
        action = self._action(department_id=self.department.id)
        today = fields.Date.context_today(action)
        self.env['ems.quality.followup'].create({
            'action_id': action.id, 'date': today, 'state': 'closed', 'description': 'Finished',
        })
        self.env['ems.quality.followup'].create({
            'action_id': action.id, 'date': today - timedelta(days=30), 'state': 'in_progress', 'description': 'Earlier note',
        })
        self.assertEqual(action.state, 'closed')

    def test_overdue_only_while_open(self):
        action = self._action(department_id=self.department.id)
        action.deadline_date = fields.Date.context_today(action) - timedelta(days=1)
        self.assertTrue(action.is_late)
        self.env['ems.quality.followup'].create({
            'action_id': action.id,
            'date': fields.Date.context_today(action),
            'state': 'closed',
            'description': 'Done',
        })
        self.assertFalse(action.is_late, "a closed action is not overdue any more")

    def test_scope_name(self):
        self.assertEqual(self._action(department_id=self.department.id).scope_name, self.department.name)
        self.assertEqual(self._action(is_centre=True).scope_name, "Centre")

    def test_a_teacher_can_create_and_follow_up_an_action(self):
        """The whole point of the model: a teacher must see and advance what they owe."""
        user = create_role_user(self, 'teacher', 'quality.action.teacher@example.com')
        action = self.env['ems.quality.action'].with_user(user).create({
            'name': 'Agreed in the department meeting',
            'type': 'agreement',
            'course_id': self.course.id,
            'department_id': self.department.id,
        })
        self.env['ems.quality.followup'].with_user(user).create({
            'action_id': action.id,
            'date': fields.Date.context_today(action),
            'state': 'in_progress',
            'description': 'Getting on with it',
        })
        self.assertEqual(action.state, 'in_progress')
