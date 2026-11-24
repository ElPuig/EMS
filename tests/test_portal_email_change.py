from datetime import date

from dateutil.relativedelta import relativedelta

from odoo.tests.common import TransactionCase

from .common import create_level_study_group, mock_outgoing_email, next_student_id


class TestPortalEmailChange(TransactionCase):
    """Changing the main email of a student or family contact: the form asks whether to update or
    give the portal access, and write() does what was answered (issue #842)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        cls.admin_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Admin (Email Change)', 'login': 'test_admin_email_change',
            'email': 'admin.email.change@example.com',
            'groups_id': [(4, cls.env.ref('ems.group_academic_admin').id),
                          (4, cls.env.ref('base.group_user').id)],
        })
        cls.level, cls.study, cls.group = create_level_study_group(
            cls, 'TEC', level={'name': 'Test Email Change Level'},
            study={'code': 'TEC001', 'acronym': 'TECS', 'name': 'Test Email Change Study'})
        cls.Partner = cls.env['res.partner'].with_user(cls.admin_user).with_context(lang='en_US')

    def _student(self, email='old.student@example.com'):
        return self.Partner.create({
            'name': f'Email Change Student {email}', 'firstname': 'Email', 'lastname': 'Change',
            'contact_type': 'student', 'student_id': next_student_id(),
            'main_group_id': self.group.id, 'email': email,
            'birth_date': date.today() - relativedelta(years=19),
        })

    def _grant(self, partner):
        self.env['ems.portal.access.wizard'].sudo().new({'mode': 'grant'})._apply_one(partner)

    def _login(self, partner):
        return partner.with_context(active_test=False).user_ids[:1].login

    def test_no_access_asks_to_give_it(self):
        question = self.Partner.get_portal_email_question(self._student().id, 'New@example.com')
        self.assertEqual(question['confirm'], 'Give portal access')
        self.assertIn('has no portal access', question['message'])

    def test_revoked_access_says_so(self):
        student = self._student()
        self._grant(student)
        student.sudo().user_ids.write({'active': False})
        question = self.Partner.get_portal_email_question(student.id, 'new@example.com')
        self.assertIn('was revoked', question['message'])

    def test_active_access_asks_to_update_it(self):
        student = self._student()
        self._grant(student)
        question = self.Partner.get_portal_email_question(student.id, 'new@example.com')
        self.assertEqual(question['confirm'], 'Update the portal access')

    def test_nothing_to_ask_for_the_same_email_or_a_non_portal_contact(self):
        student = self._student()
        self.assertFalse(self.Partner.get_portal_email_question(student.id, 'OLD.student@example.com'))
        other = self.Partner.create({'name': 'Plain Contact', 'email': 'plain@example.com'})
        self.assertFalse(self.Partner.get_portal_email_question(other.id, 'new@example.com'))

    def test_apply_gives_access_with_the_new_email(self):
        student = self._student()
        student.with_user(self.admin_user).write({'email': 'given@example.com', 'portal_email_decision': 'apply'})
        self.assertEqual(self._login(student), 'given@example.com')

    def test_keep_changes_only_the_email(self):
        student = self._student()
        student.with_user(self.admin_user).write({'email': 'kept@example.com', 'portal_email_decision': 'keep'})
        self.assertEqual(student.email, 'kept@example.com')
        self.assertFalse(student.with_context(active_test=False).user_ids)

    def test_apply_moves_an_active_access(self):
        student = self._student()
        self._grant(student)
        student.with_user(self.admin_user).write({'email': 'moved@example.com', 'portal_email_decision': 'apply'})
        self.assertEqual(self._login(student), 'moved@example.com')
        self.assertTrue(student.user_ids)

    def test_keep_leaves_an_active_access_alone(self):
        student = self._student()
        self._grant(student)
        student.with_user(self.admin_user).write({'email': 'stays@example.com', 'portal_email_decision': 'keep'})
        self.assertEqual(self._login(student), 'old.student@example.com')

    def test_without_an_answer_an_active_access_still_moves(self):
        """Imports and other code have no dialog: the access follows the email, as before."""
        student = self._student()
        self._grant(student)
        student.with_user(self.admin_user).write({'email': 'auto@example.com'})
        self.assertEqual(self._login(student), 'auto@example.com')

    def test_a_tutor_of_another_group_is_not_offered_the_access(self):
        other_teacher = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Other Tutor (Email Change)', 'login': 'test_other_tutor_email_change',
            'groups_id': [(4, self.env.ref('ems.group_tutor').id), (4, self.env.ref('base.group_user').id)],
        })
        student = self._student()
        self.assertFalse(self.env['res.partner'].with_user(other_teacher).get_portal_email_question(
            student.id, 'new@example.com'))
