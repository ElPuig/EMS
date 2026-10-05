from datetime import date

from dateutil.relativedelta import relativedelta

from odoo.exceptions import AccessDenied
from odoo.tests.common import TransactionCase

from .common import next_student_id

DOMAIN = 'portal-signin.example.com'


class TestPortalGoogleSignin(TransactionCase):
    """A student's portal user, whose login is his personal email, also opens with "Sign in with
    Google" through his corporate account (student_email): linked on the first Google sign-in,
    password login untouched. See models/contacts/portal_google_signin.py."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.google_ws_domain = DOMAIN
        cls.google = cls.env.ref('auth_oauth.provider_google')
        cls.student, cls.minor = cls.env['res.partner'].create([{
            'name': 'Google Signin Student', 'contact_type': 'student', 'student_id': next_student_id(),
            'email': 'signin.student@example.com', 'student_email': f'signin.student@{DOMAIN}',
            'birth_date': date.today() - relativedelta(years=19),
        }, {
            'name': 'Google Signin Minor', 'contact_type': 'student', 'student_id': next_student_id(),
            'email': 'signin.minor@example.com', 'student_email': f'signin.minor@{DOMAIN}',
            'birth_date': date.today() - relativedelta(years=15),
        }])
        cls.user, cls.minor_user = cls.env['res.users'].with_context(no_reset_password=True).create([{
            'name': partner.name, 'login': partner.email, 'password': 'signin-pass-1234',
            'partner_id': partner.id, 'groups_id': [(6, 0, [cls.env.ref('base.group_portal').id])],
        } for partner in (cls.student, cls.minor)])

    def _signin(self, email, uid='109000000000000000001', verified=True, provider=None):
        validation = {'user_id': uid, 'email': email, 'email_verified': verified}
        return self.env['res.users'].sudo()._auth_oauth_signin(
            (provider or self.google).id, validation, {'access_token': 'token-1', 'state': '{}'})

    def test_first_google_signin_links_the_student(self):
        self.assertEqual(self._signin(f'signin.student@{DOMAIN}'), 'signin.student@example.com')
        self.assertEqual(self.user.oauth_uid, '109000000000000000001')
        self.assertEqual(self.user.oauth_provider_id, self.google)
        self.assertEqual(self.user.login, 'signin.student@example.com')

    def test_email_case_does_not_matter(self):
        self.assertEqual(self._signin(f'Signin.Student@{DOMAIN.upper()}'), self.user.login)

    def test_a_minor_signs_in_too(self):
        self.assertEqual(self._signin(f'signin.minor@{DOMAIN}'), self.minor_user.login)

    def test_later_signins_go_through_the_link(self):
        self._signin(f'signin.student@{DOMAIN}')
        # Once linked, auth_oauth itself finds the user by its Google id.
        self.assertEqual(self._signin('whatever@elsewhere.example.com'), self.user.login)

    def test_password_login_keeps_working(self):
        self._signin(f'signin.student@{DOMAIN}')
        self.user.with_user(self.user)._check_credentials(
            {'type': 'password', 'password': 'signin-pass-1234'}, {'interactive': True})

    def test_email_outside_the_centre_domain_is_refused(self):
        self.student.student_email = 'signin.student@gmail.com'
        with self.assertRaises(AccessDenied):
            self._signin('signin.student@gmail.com')
        self.assertFalse(self.user.oauth_uid)

    def test_unverified_email_is_refused(self):
        with self.assertRaises(AccessDenied):
            self._signin(f'signin.student@{DOMAIN}', verified=False)

    def test_other_provider_is_refused(self):
        other_provider = self.env['auth.oauth.provider'].create({
            'name': 'Test Provider', 'client_id': 'x', 'auth_endpoint': 'https://example.com/auth',
            'validation_endpoint': 'https://example.com/validate', 'body': 'Test Provider',
        })
        with self.assertRaises(AccessDenied):
            self._signin(f'signin.student@{DOMAIN}', provider=other_provider)

    def test_email_with_no_student_is_refused(self):
        with self.assertRaises(AccessDenied):
            self._signin(f'nobody@{DOMAIN}')

    def test_internal_users_are_never_matched(self):
        self.user.write({'groups_id': [(6, 0, [self.env.ref('base.group_user').id])]})
        with self.assertRaises(AccessDenied):
            self._signin(f'signin.student@{DOMAIN}')

    def test_google_id_already_linked_elsewhere_is_refused(self):
        self.minor_user.write({'oauth_provider_id': self.google.id, 'oauth_uid': '109000000000000000009'})
        # The same Google id cannot open a second account; auth_oauth itself finds the minor.
        self.assertEqual(self._signin(f'signin.student@{DOMAIN}', uid='109000000000000000009'),
                         self.minor_user.login)
        self.assertFalse(self.user.oauth_uid)

    def test_changing_the_corporate_email_unlinks_google(self):
        self._signin(f'signin.student@{DOMAIN}')
        self.student.student_email = f'signin.student2@{DOMAIN}'
        self.assertFalse(self.user.oauth_uid)
        self.assertFalse(self.user.oauth_provider_id)

    def test_rewriting_the_same_corporate_email_keeps_the_link(self):
        self._signin(f'signin.student@{DOMAIN}')
        self.student.student_email = f'Signin.Student@{DOMAIN}'
        self.assertEqual(self.user.oauth_uid, '109000000000000000001')
