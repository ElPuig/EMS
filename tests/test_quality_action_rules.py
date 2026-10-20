# -*- coding: utf-8 -*-

from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase

from .common import create_role_employee, create_role_user


class TestQualityActionRules(TransactionCase):
    """Agreements and actions follow the chain of command, as minutes do, never every holder of a
    post centre-wide. Three ways of being in one: whoever manages its content (the chain of the
    department or group it belongs to, the minute's writer and approver while it is not approved),
    the responsible people, who report its progress (the follow-up), and the people involved, who
    only read it and hear of its progress."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # A follow-up notifies the agreement's followers: no real email may leave a test.
        mail_patcher = patch('odoo.addons.base.models.ir_mail_server.IrMailServer.send_email')
        mail_patcher.start()
        cls.addClassCleanup(mail_patcher.stop)
        cls.type = cls.env.ref('__import__.minute_type_dep')
        cls.course = cls.env['ems.course'].search([('is_current', '=', True)], limit=1)
        cls.dep_a = cls.env['hr.department'].create({'name': 'Action Rules Department A'})
        cls.dep_b = cls.env['hr.department'].create({'name': 'Action Rules Department B'})
        cls.dep_c = cls.env['hr.department'].create({'name': 'Action Rules Department C'})

        # Branch of department A: its chief, and the Head of Studies above that chief.
        cls.hos = create_role_user(cls, 'head_of_studies', 'arules.hos@example.com', name='ARules HoS')
        cls.hos_employee = create_role_employee(cls, cls.hos)
        cls.chief_a = create_role_user(cls, 'department_chief', 'arules.chief.a@example.com', name='ARules Chief A')
        cls.chief_a_employee = create_role_employee(cls, cls.chief_a, department_id=cls.dep_a.id)
        cls.dep_a.manager_id = cls.chief_a_employee
        # After naming the chief: naming a department's manager rewrites the managers above.
        cls.chief_a_employee.parent_id = cls.hos_employee
        cls.teacher_a = create_role_user(cls, 'teacher', 'arules.teacher.a@example.com', name='ARules Teacher A')
        cls.teacher_a_employee = create_role_employee(cls, cls.teacher_a, department_id=cls.dep_a.id, parent_id=cls.chief_a_employee.id)

        # Branch of department B: the person responsible for the agreement, and their chief.
        cls.chief_b = create_role_user(cls, 'department_chief', 'arules.chief.b@example.com', name='ARules Chief B')
        cls.chief_b_employee = create_role_employee(cls, cls.chief_b, department_id=cls.dep_b.id)
        cls.teacher_b = create_role_user(cls, 'teacher', 'arules.teacher.b@example.com', name='ARules Teacher B')
        cls.teacher_b_employee = create_role_employee(cls, cls.teacher_b, department_id=cls.dep_b.id, parent_id=cls.chief_b_employee.id)

        # Nobody's chain: a teacher, a Department Chief and a Head of Studies from elsewhere.
        cls.teacher_c = create_role_user(cls, 'teacher', 'arules.teacher.c@example.com', name='ARules Teacher C')
        create_role_employee(cls, cls.teacher_c, department_id=cls.dep_c.id)
        cls.other_chief = create_role_user(cls, 'department_chief', 'arules.other.chief@example.com', name='ARules Other Chief')
        create_role_employee(cls, cls.other_chief, department_id=cls.dep_c.id)
        cls.other_hos = create_role_user(cls, 'head_of_studies', 'arules.other.hos@example.com', name='ARules Other HoS')
        create_role_employee(cls, cls.other_hos)
        cls.secretary = create_role_user(cls, 'secretary', 'arules.secretary@example.com', name='ARules Secretary')
        create_role_employee(cls, cls.secretary, employee_type='asp')

        cls.teacher_d = create_role_user(cls, 'teacher', 'arules.teacher.d@example.com', name='ARules Involved Teacher')
        cls.teacher_d_employee = create_role_employee(cls, cls.teacher_d, department_id=cls.dep_c.id)

        cls.committee = create_role_user(cls, 'quality', 'arules.committee@example.com', name='ARules Committee')
        cls.admin = create_role_user(cls, 'academic_admin', 'arules.admin@example.com', name='ARules Admin')

        cls.action = cls.env['ems.quality.action'].create({
            'name': 'Review the practical assessment criteria', 'department_id': cls.dep_a.id,
            'course_id': cls.course.id,
            'responsible_employee_ids': [(6, 0, [cls.teacher_b_employee.id])],
            'involved_employee_ids': [(6, 0, [cls.teacher_d_employee.id])],
        })
        cls.followup = cls.env['ems.quality.followup'].create({
            'action_id': cls.action.id, 'description': 'Draft criteria shared.',
        })

    def _reads(self, user, record):
        return bool(record.with_user(user).search([('id', '=', record.id)]))

    def _follows_up(self, user):
        return self.env['ems.quality.followup'].with_user(user).create({
            'action_id': self.action.id, 'description': f'Follow-up by {user.name}',
        })

    def _writes(self, user):
        self.assertTrue(self.action.with_user(user).can_manage_content)
        self.action.with_user(user).write({'resources': f'Checked by {user.name}'})
        self._follows_up(user)

    def _only_follows_up(self, user):
        """Progress, not content: a follow-up entry and the description, which explains how to
        carry the agreement out; never what was agreed."""
        self._follows_up(user)
        action = self.action.with_user(user)
        self.assertTrue(action.can_follow_up)
        self.assertTrue(action.can_edit, "the form opens for editing, for the description")
        self.assertFalse(action.can_manage_content)
        action.write({'description': f'<p>How to do it, by {user.name}</p>'})
        with self.assertRaises(AccessError):
            action.write({'name': 'What the meeting did not agree'})
        with self.assertRaises(AccessError):
            action.write({'description': '<p>And the deadline</p>', 'deadline_text': 'Whenever'})

    def test_a_department_member_reads_it_but_does_not_write_it(self):
        self.assertTrue(self._reads(self.teacher_a, self.action))
        self.assertTrue(self._reads(self.teacher_a, self.followup))
        with self.assertRaises(AccessError):
            self.action.with_user(self.teacher_a).write({'resources': 'Not mine to change'})
        with self.assertRaises(AccessError):
            self.env['ems.quality.followup'].with_user(self.teacher_a).create({
                'action_id': self.action.id, 'description': 'Not mine to report',
            })

    def test_a_teacher_from_elsewhere_sees_neither_it_nor_its_follow_up(self):
        self.assertFalse(self._reads(self.teacher_c, self.action))
        self.assertFalse(self._reads(self.teacher_c, self.followup))

    def test_the_responsible_person_follows_it_up_but_does_not_change_it(self):
        self._only_follows_up(self.teacher_b)

    def test_the_chain_of_command_of_the_responsible_person_follows_it_up(self):
        self._only_follows_up(self.chief_b)

    def test_the_holders_of_the_responsible_post_follow_it_up(self):
        role = self.env['ems.role'].create({'name': 'ARules Responsible Post', 'employee_type': 'teacher',
                                            'employee_ids': [(6, 0, [self.teacher_d_employee.id])]})
        self.action.responsible_role_id = role
        self._only_follows_up(self.teacher_d)

    def test_the_people_involved_read_it_and_hear_of_its_progress(self):
        """They are the ones who have to do something about it, not the ones who manage it."""
        self.assertTrue(self._reads(self.teacher_d, self.action))
        self.assertTrue(self._reads(self.teacher_d, self.followup))
        self.assertFalse(self.action.with_user(self.teacher_d).can_follow_up)
        self.assertFalse(self.action.with_user(self.teacher_d).can_edit)
        with self.assertRaises(AccessError):
            self.action.with_user(self.teacher_d).write({'description': '<p>Not mine to explain</p>'})
        with self.assertRaises(AccessError):
            self._follows_up(self.teacher_d)
        self.assertIn(self.teacher_d.partner_id, self.action.message_partner_ids)
        self.assertIn(self.teacher_b.partner_id, self.action.message_partner_ids)
        self._follows_up(self.teacher_b)
        message = self.action.message_ids.filtered(lambda message: 'Follow-up by ARules Teacher B' in (message.body or ''))
        self.assertTrue(message, "adding a follow-up entry tells the agreement's followers")
        self.assertIn(self.teacher_d.partner_id, message.notified_partner_ids)

    def test_the_chain_of_command_of_the_department_writes_it(self):
        self.assertIn(self.hos, self.chief_a_employee.tutor_scope_user_ids)
        self._writes(self.chief_a)
        self._writes(self.hos)

    def test_chiefs_of_another_branch_do_not_see_it(self):
        """Holding the post is not enough: a Department Chief or a Head of Studies who is not
        above this department or this responsible person does not get it."""
        for user in (self.other_chief, self.other_hos):
            self.assertFalse(self._reads(user, self.action), user.name)
            self.assertFalse(self._reads(user, self.followup), user.name)

    def test_the_secretariat_only_sees_its_own_scopes(self):
        self.assertFalse(self._reads(self.secretary, self.action))

    def test_the_committee_and_the_administrator_manage_them_all(self):
        self._writes(self.committee)
        self._writes(self.admin)

    def _minute(self, **overrides):
        vals = {'type_id': self.type.id, 'department_id': self.dep_a.id, 'course_id': self.course.id,
                'date': fields.Date.context_today(self.env['ems.minute'])}
        vals.update(overrides)
        return self.env['ems.minute'].create(vals)

    def test_whoever_writes_a_minute_manages_its_agreements_until_it_is_approved(self):
        """An outside attendee writing the minute adds and edits its agreements while it is being
        written; once approved, the agreement is its responsible people's and their chain's."""
        public_c = self.env['hr.employee.public'].search([('user_id', '=', self.teacher_c.id)])
        minute = self._minute(redactor_employee_id=public_c.id, attendee_ids=[(6, 0, public_c.ids)])
        agreement = self.env['ems.quality.action'].with_user(self.teacher_c).create({
            'name': 'Share the rubric', 'minute_id': minute.id,
            'responsible_employee_ids': [(6, 0, [self.teacher_b_employee.id])],
        })
        agreement.with_user(self.teacher_c).write({'deadline_text': 'Before the first assessment'})
        minute.section_value_ids.filtered(lambda value: value.required).content = "<p>Discussed.</p>"
        minute.action_submit()
        minute.action_approve()
        self.assertTrue(self._reads(self.teacher_c, agreement), "an attendee still reads what was agreed")
        with self.assertRaises(AccessError):
            agreement.with_user(self.teacher_c).write({'deadline_text': 'Changed after approval'})
        self.env['ems.quality.followup'].with_user(self.teacher_b).create({
            'action_id': agreement.id, 'description': 'Rubric shared with the department',
        })

    def test_whoever_creates_an_action_outside_a_minute_keeps_writing_it(self):
        action = self.env['ems.quality.action'].with_user(self.teacher_c).create({
            'name': 'Label the lab cupboards', 'type': 'improvement', 'department_id': self.dep_c.id,
        })
        action.with_user(self.teacher_c).write({'resources': 'Labels'})
