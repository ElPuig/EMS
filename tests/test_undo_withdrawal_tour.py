# -*- coding: utf-8 -*-

from odoo.tests.common import HttpCase, tagged

from .common import create_level_study_group, create_role_user, mock_outgoing_email, next_student_id


@tagged('post_install', '-at_install')
class TestUndoWithdrawalTour(HttpCase):
    """A withdrawal registered by mistake undone by the secretariat from the student form
    (issue #592)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # The withdrawal and its undoing revoke and grant the portal, which sends the invitation.
        mock_outgoing_email(cls)
        course = cls.env['ems.course'].create({'start': 2081, 'end': 2082})
        cls.env.company.current_course_id = course
        _level, study, cls.group = create_level_study_group(cls, 'UWT', study={
            'code': 'UWT001', 'acronym': 'UWTS', 'name': 'Undo Withdrawal Tour Study'})
        subject = cls.env['ems.subject'].create({
            'code': 'UWTSUB', 'acronym': 'UWTSB', 'name': 'Undo Withdrawal Tour Subject',
            'study_ids': [(6, 0, [study.id])]})
        cls.student = cls.env['res.partner'].create({
            'name': 'Undo Withdrawal Tour Student', 'contact_type': 'student',
            'student_id': next_student_id(), 'main_group_id': cls.group.id})
        order = cls.env['sale.order'].create({
            'partner_id': cls.student.id, 'ems_course_id': course.id,
            'ems_study_id': study.id, 'ems_group_id': cls.group.id,
            'order_line': [(0, 0, {'product_id': subject.product_id.id})]})
        order.state = 'sale'
        cls.env['ems.withdrawal_wizard'].with_context(
            active_ids=cls.student.ids).create({}).action_apply()
        # create_role_user sets lang to en_US, which the English selectors of the tour need.
        cls.secretary = create_role_user(cls, 'secretary', 'test_secretary_undo_withdrawal_tour',
                                         email='undo.withdrawal.tour@example.com')

    def test_undo_withdrawal_tour(self):
        self.start_tour(f"/odoo/action-ems.action_student_kanban/{self.student.id}",
                        "ems_undo_withdrawal", login=self.secretary.login)
        self.assertTrue(self.student.active)
        self.assertEqual(self.student.contact_type, 'student')
        self.assertEqual(self.student.main_group_id, self.group)
