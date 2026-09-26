from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase

from .common import create_level_study_group, create_role_employee, create_role_user, mock_outgoing_email
from .test_contact_data_request import create_contact_data_fixtures


class TestContactDataRequestSendWizard(TransactionCase):
    """ems.contact.data.request.send.wizard (issue #507): who gets a request, what is skipped, who
    is told to be called by phone, and what a tutor may reach."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        create_contact_data_fixtures(cls, 'TCSW')
        cls.secretary = create_role_user(cls, 'secretary', 'test_secretary_tcsw',
                                         name='Test Secretary (TCSW)', email='secretary.tcsw@example.com')

    def _wizard(self, user=None, **vals):
        vals.setdefault('course_id', self.course.id)
        vals.setdefault('target', 'scope')
        vals.setdefault('group_ids', [(6, 0, self.group.ids)])
        return self.env['ems.contact.data.request.send.wizard'].with_user(user or self.secretary) \
            .with_context(lang='en_US').create(vals)

    def _requests(self):
        return self.env['ems.contact.data.request'].search([('group_id', '=', self.group.id)])

    def test_group_scope_sends_only_to_incomplete(self):
        self._wizard().action_apply()
        requests = self._requests()
        self.assertEqual(requests.student_id, self.minor)
        self.assertEqual(requests.state, 'pending')
        self.assertTrue(requests.sent_date)
        self.assertIn('identity document', requests.missing_fields)

    def test_minor_request_is_emailed_to_the_family(self):
        self._wizard(grant_portal=False).action_apply()
        mail = self.env['mail.mail'].search([('email_to', '=', self.family.email)], limit=1)
        self.assertTrue(mail)
        self.assertIn('/my/dades-contacte', mail.body_html)

    def test_only_whoever_acts_for_the_student_is_asked(self):
        # A minor gets a portal account of their own that only consults (res.partner.
        # _ems_portal_is_view_only): the request goes to the family, who can answer it, and never
        # to them - neither by email, nor as a recipient in the preview, nor with a portal invitation.
        self.minor.email = 'minor.tcsw@example.com'
        wizard = self._wizard(grant_portal=True)
        wizard._onchange_selection()
        line = wizard.line_ids.filtered(lambda line: line.student_id == self.minor)
        self.assertEqual(line.recipient_emails, self.family.email)
        wizard.action_apply()
        self.assertFalse(self.env['mail.mail'].search([('email_to', '=', self.minor.email)]))
        self.assertTrue(self.env['mail.mail'].search([('email_to', '=', self.family.email)]))
        self.assertFalse(self.minor.with_context(active_test=False).user_ids)

    def test_all_students_when_not_only_incomplete(self):
        self._wizard(only_incomplete=False).action_apply()
        self.assertEqual(self._requests().student_id, self.minor | self.adult)

    def test_pending_request_is_not_sent_twice_and_done_one_is_reopened(self):
        self._wizard().action_apply()
        request = self._requests()
        request.reminder_count = 3
        self._wizard().action_apply()
        self.assertEqual(request.reminder_count, 3, "A pending request is left alone")
        request.state = 'done'
        self._wizard().action_apply()
        self.assertEqual(request.state, 'pending')
        self.assertEqual(request.reminder_count, 0)

    def test_nobody_reachable_is_reported(self):
        self.family.email = False
        result = self._wizard().action_apply()
        self.assertEqual(result['params']['type'], 'warning')
        self.assertIn(self.minor.name, result['params']['message'])

    def test_grant_portal_invites_the_family(self):
        self._wizard(grant_portal=True).action_apply()
        self.assertTrue(self.family.with_context(active_test=False).user_ids.filtered(lambda user: user._is_portal()))

    def test_preview_lists_missing_and_recipients(self):
        wizard = self._wizard()
        wizard._onchange_selection()
        line = wizard.line_ids.filtered(lambda line: line.student_id == self.minor)
        self.assertIn(self.family.email, line.recipient_emails)
        self.assertTrue(line.missing)
        complete = wizard.line_ids.filtered(lambda line: line.student_id == self.adult)
        self.assertIn('Data complete', complete.note)

    def test_tutor_reaches_only_their_own_students(self):
        _level, _study, other_group = create_level_study_group(self, 'TCSO', study={
            'code': 'TCSO01', 'acronym': 'TCSOS', 'name': 'Other Send Study'})
        other_tutor = create_role_user(self, 'tutor', 'test_other_tutor_tcsw', name='Other Tutor (TCSW)')
        other_group.tutor_id = create_role_employee(self, other_tutor)
        wizard = self._wizard(user=other_tutor, target='students', student_ids=[(6, 0, self.minor.ids)])
        with self.assertRaises(UserError):
            wizard.action_apply()
        self.assertNotIn(self.group, wizard._scope_allowed_groups())
        self._wizard(user=self.tutor).action_apply()
        self.assertEqual(self._requests().student_id, self.minor)

    def test_plain_teacher_cannot_request(self):
        teacher = create_role_user(self, 'teacher', 'test_teacher_tcsw', name='Teacher (TCSW)')
        with self.assertRaises(Exception):
            self._wizard(user=teacher).action_apply()
