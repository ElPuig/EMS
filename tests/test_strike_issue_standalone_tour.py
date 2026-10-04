from odoo.tests import tagged, HttpCase

from .common import create_role_employee, create_role_user, mock_outgoing_email, next_student_id


@tagged('post_install', '-at_install')
class TestStrikeIssueStandaloneTour(HttpCase):
    """Issue #402: a strike issued outside the roll-call view, from Coexistence > Strikes."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # The tour issues a real ems.strike (force_send=True on create()): see tests/test_strike.py.
        mock_outgoing_email(cls)
        cls.teacher_user = create_role_user(cls, 'teacher', 'strike_standalone_teacher')
        create_role_employee(cls, cls.teacher_user)
        cls.student_without_strikes = cls.env['res.partner'].create({
            'name': 'Strike From Student Student', 'contact_type': 'student', 'student_id': next_student_id(),
            'student_email': 'strike_from_student_student@example.com',
        })
        cls.env['res.partner'].create({
            'name': 'Strike Standalone Student', 'contact_type': 'student', 'student_id': next_student_id(),
            'student_email': 'strike_standalone_student@example.com',
        })

    def test_strike_issue_standalone_tour(self):
        self.start_tour("/odoo", "ems_strike_issue_standalone", login=self.teacher_user.login)
        strike = self.env['ems.strike'].search([('notes', '=', 'Caught running in the corridor')])
        self.assertEqual(strike.teacher_id.user_id, self.teacher_user)
        self.assertTrue(strike.kicked_out)
        self.assertFalse(strike.attendance_session_line_id)
        # Issue #554: the second strike, confirmed despite the duplicate warning.
        self.assertTrue(self.env['ems.strike'].search([('notes', '=', 'Threw a chair, a different incident')]))

    def test_strike_issue_from_student_tour(self):
        self.start_tour(f"/odoo/action-ems.action_student_kanban/{self.student_without_strikes.id}",
                        "ems_strike_issue_from_student", login=self.teacher_user.login)
        strike = self.env['ems.strike'].search([('notes', '=', 'Insulted a classmate at the playground')])
        self.assertEqual(strike.student_id, self.student_without_strikes)
        self.assertEqual(strike.teacher_id.user_id, self.teacher_user)
