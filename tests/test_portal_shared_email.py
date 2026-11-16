from datetime import date
from unittest.mock import patch

from dateutil.relativedelta import relativedelta

from odoo.tests.common import TransactionCase

from .common import create_level_study_group, mock_outgoing_email, next_student_id

DOMAIN = 'shared-email.example.com'


class TestPortalSharedEmail(TransactionCase):
    """A student whose main email is also a family member's (issue #833): the portal login with
    that email is the family's, and the student's portal user gets the corporate email
    (student_email) as login instead, created once the Google account exists. See
    docs/en/developers/contacts/portal_access_wizard.md."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        cls.env.company.write({
            'google_ws_domain': DOMAIN,
            'google_ws_dry_run': True,
            'google_ws_ou_minor': '/alumnos',
            'google_ws_ou_adult': '/alumnos/+18',
        })
        # The portal invitation's mail.template has no email_from of its own: give the acting
        # user an email (see TestPortalAccessWizard.setUpClass for why).
        cls.admin_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Admin (Shared Email)', 'login': 'test_admin_shared_email',
            'email': 'admin.shared@example.com',
            'groups_id': [(4, cls.env.ref('ems.group_academic_admin').id),
                          (4, cls.env.ref('base.group_user').id)],
        })
        cls.level, cls.study, cls.group = create_level_study_group(
            cls, 'TSE', level={'name': 'Test Shared Email Level'},
            study={'code': 'TSE001', 'acronym': 'TSES', 'name': 'Test Shared Email Study'})
        cls.father = cls.env.ref('ems.relation_type_father')

    def _student(self, email, student_email=False, family_email=None, adult=False):
        """A student and, when family_email is given, a family member related to them."""
        student = self.env['res.partner'].create({
            'name': f'Shared Email Student {email}', 'firstname': 'Shared', 'lastname': 'Student',
            'contact_type': 'student', 'student_id': next_student_id(),
            'main_group_id': self.group.id, 'email': email, 'student_email': student_email,
            'birth_date': date.today() - relativedelta(years=19 if adult else 15),
        })
        family = self.env['res.partner']
        if family_email:
            family = self.env['res.partner'].create({
                'name': f'Shared Email Family {family_email}', 'contact_type': 'family',
                'email': family_email,
            })
            self.env['res.partner.relation'].create({
                'left_partner_id': family.id, 'type_id': self.father.id,
                'right_partner_id': student.id,
            })
        return student, family

    def _grant(self, students):
        wizard = self.env['ems.portal.access.wizard'].with_user(self.admin_user).with_context(
            lang='en_US').create({'mode': 'grant', 'student_ids': [(6, 0, students.ids)]})
        wizard._onchange_mode()
        return wizard, wizard.action_apply()['params']['message']

    def _portal_user(self, partner):
        return partner.with_context(active_test=False).user_ids[:1]

    def _portal_user_with_login(self, partner, login):
        return self.env['res.users'].with_context(no_reset_password=True).create({
            'name': partner.name, 'login': login, 'partner_id': partner.id,
            'groups_id': [(6, 0, [self.env.ref('base.group_portal').id])],
        })

    # --- granting -------------------------------------------------------

    def test_family_wins_and_student_gets_the_corporate_login(self):
        student, family = self._student('home@example.com', f'stu1@{DOMAIN}', 'home@example.com')
        self._grant(student)
        self.assertEqual(self._portal_user(family).login, 'home@example.com')
        self.assertEqual(self._portal_user(student).login, f'stu1@{DOMAIN}')
        self.assertTrue(self._portal_user(student)._is_portal())
        self.assertEqual(student.email, 'home@example.com', "the main email is not touched")

    def test_no_collision_keeps_the_personal_email_as_login(self):
        student, family = self._student('own@example.com', f'stu2@{DOMAIN}', 'parents@example.com')
        self._grant(student)
        self.assertEqual(self._portal_user(student).login, 'own@example.com')
        self.assertEqual(self._portal_user(family).login, 'parents@example.com')

    def test_student_without_corporate_email_is_reported_and_left_without_user(self):
        student, family = self._student('home3@example.com', False, 'home3@example.com')
        _wizard, message = self._grant(student)
        self.assertEqual(self._portal_user(family).login, 'home3@example.com')
        self.assertFalse(self._portal_user(student))
        self.assertIn('corporate email', message)
        self.assertNotIn('same email as an existing user', message)

    def test_granting_the_family_takes_its_login_back_from_the_student(self):
        """The state before issue #833: the student was granted first and took the shared login."""
        student, family = self._student('home4@example.com', f'stu4@{DOMAIN}', 'home4@example.com')
        self._portal_user_with_login(student, 'home4@example.com')
        self._grant(student)
        self.assertEqual(self._portal_user(student).login, f'stu4@{DOMAIN}')
        self.assertEqual(self._portal_user(family).login, 'home4@example.com')

    def test_regrant_after_an_undone_withdrawal_uses_the_corporate_login(self):
        student, family = self._student('home5@example.com', f'stu5@{DOMAIN}', 'home5@example.com')
        summary = student._ems_grant_student_portal()
        self.assertFalse(summary['issues'])
        self.assertEqual(self._portal_user(student).login, f'stu5@{DOMAIN}')
        self.assertEqual(self._portal_user(family).login, 'home5@example.com')

    def test_main_email_change_realigns_the_login(self):
        student, _family = self._student('home6@example.com', f'stu6@{DOMAIN}', 'home6@example.com')
        self._grant(student)
        student.email = 'own6@example.com'
        self.assertEqual(self._portal_user(student).login, 'own6@example.com')
        self.assertTrue(self._portal_user(student).active)

    # --- the Google account opens the waiting portal ---------------------

    def _create_google_account(self, student):
        self.env.company.google_ws_enabled = True
        with patch.object(type(student), '_gw_deliver_credentials', return_value=(True, True)):
            student._gw_create_account()

    def test_google_account_creation_grants_the_waiting_student(self):
        student, _family = self._student('home7@example.com', False, 'home7@example.com')
        self._grant(student)
        self._create_google_account(student)
        self.assertTrue(student.student_email)
        user = self._portal_user(student)
        self.assertEqual(user.login, student.student_email)
        self.assertTrue(user._is_portal())

    def test_google_account_creation_grants_nothing_the_centre_did_not_grant(self):
        """No family access means the centre never granted the portal for this student."""
        student, _family = self._student('home8@example.com', False, 'home8@example.com')
        self._create_google_account(student)
        self.assertTrue(student.student_email)
        self.assertFalse(self._portal_user(student))

    def test_google_signin_opens_the_student_portal(self):
        student, _family = self._student('home9@example.com', f'stu9@{DOMAIN}', 'home9@example.com')
        self._grant(student)
        validation = {'user_id': '109000000000000000833', 'email': f'stu9@{DOMAIN}',
                      'email_verified': True}
        login = self.env['res.users'].sudo()._auth_oauth_signin(
            self.env.ref('auth_oauth.provider_google').id, validation,
            {'access_token': 'token-833', 'state': '{}'})
        self.assertEqual(login, f'stu9@{DOMAIN}')

    def test_credentials_emails_go_to_the_shared_address(self):
        student, _family = self._student('home10@example.com', f'stu10@{DOMAIN}', 'home10@example.com')
        for xmlid in ('ems.mail_template_google_welcome',
                      'ems.mail_template_google_password_reset_student'):
            with self.subTest(template=xmlid):
                email_to = self.env.ref(xmlid)._render_field('email_to', student.ids)[student.id]
                self.assertEqual(email_to, 'home10@example.com')

    # --- warning --------------------------------------------------------

    def test_warning_only_for_a_student_sharing_the_email(self):
        shared, family = self._student('Home11@Example.com', False, 'home11@example.com')
        own, _other = self._student('own11@example.com', False, 'parents11@example.com')
        self.assertTrue(shared.portal_email_shared_with_family)
        self.assertFalse(own.portal_email_shared_with_family)
        self.assertFalse(family.portal_email_shared_with_family)

    def test_wizard_preview_explains_the_corporate_login(self):
        student, _family = self._student('home12@example.com', f'stu12@{DOMAIN}', 'home12@example.com')
        waiting, _family2 = self._student('home13@example.com', False, 'home13@example.com')
        wizard = self.env['ems.portal.access.wizard'].with_user(self.admin_user).with_context(
            lang='en_US').create({'mode': 'grant', 'student_ids': [(6, 0, (student | waiting).ids)]})
        wizard._onchange_mode()
        notes = {line.recipient_id: line.note for line in wizard.line_ids}
        self.assertIn(f'stu12@{DOMAIN}', notes[student])
        self.assertIn('corporate email', notes[waiting])

    # --- existing installations (migration 18.0.0.49.3) ------------------

    def test_fix_existing_shared_email_portals(self):
        holder, holder_family = self._student('home14@example.com', f'stu14@{DOMAIN}', 'home14@example.com')
        self._portal_user_with_login(holder, 'home14@example.com')
        waiting, waiting_family = self._student('home15@example.com', f'stu15@{DOMAIN}', 'home15@example.com')
        self._portal_user_with_login(waiting_family, 'home15@example.com')
        untouched, _family = self._student('own16@example.com', f'stu16@{DOMAIN}', 'parents16@example.com')
        self._portal_user_with_login(untouched, 'own16@example.com')

        found = self.env['res.partner']._ems_students_sharing_email_with_family()
        self.assertIn(holder, found)
        self.assertIn(waiting, found)
        self.assertNotIn(untouched, found)
        (holder | waiting | untouched)._ems_fix_shared_email_portals()

        self.assertEqual(self._portal_user(holder).login, f'stu14@{DOMAIN}')
        self.assertEqual(self._portal_user(holder_family).login, 'home14@example.com')
        self.assertEqual(self._portal_user(waiting).login, f'stu15@{DOMAIN}')
        self.assertTrue(self._portal_user(waiting)._is_portal())
        self.assertEqual(self._portal_user(untouched).login, 'own16@example.com')
