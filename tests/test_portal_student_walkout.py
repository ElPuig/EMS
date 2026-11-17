from datetime import timedelta

from odoo import fields
from odoo.http import Request
from odoo.tests.common import HttpCase, tagged

from .common import mock_outgoing_email
from .test_student_walkout import PDF, create_walkout_fixtures, open_walkout, reject_walkout


@tagged('post_install', '-at_install')
class TestPortalStudentWalkout(HttpCase):
    """Issue #800: the portal's student walkout pages (/my/vagues), always as the logged-in student."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        create_walkout_fixtures(cls, 'WLP')

    def _login(self, partner):
        user = partner.user_ids[:1]
        self.authenticate(user.login, user.login)

    def _post(self, url, files=None, **data):
        return self.url_open(url, data={'csrf_token': Request.csrf_token(self), **data}, files=files)

    def test_delegate_sees_the_card_and_calls_a_walkout(self):
        self._login(self.delegate)
        home = self.url_open('/my/home').text
        self.assertIn('href="/my/vagues" class="nav-link"', home)
        self.assertIn('/my/vagues/nova', self.url_open('/my/vagues').text)
        form = self.url_open('/my/vagues/nova')
        self.assertEqual(form.status_code, 200)
        # The calendar of a call opened now, and the first day it can be for (next Monday).
        self.assertIn('o_ems_walkout_calendar', form.text)
        self.assertIn('Each phase starts when its email reaches the group', form.text)
        walkout_date = self.today + timedelta(days=7)
        # The earliest day needs a shorter joining; the first one with both phases whole is next Monday.
        self.assertIn(f'min="{fields.Date.to_string(self.today + timedelta(days=4))}"', form.text)
        self.assertIn('the joining phase will be shorter', form.text)
        response = self._post('/my/vagues/nova', walkout_date=fields.Date.to_string(walkout_date), notes='Union',
                              files=[('union_call', ('call.pdf', PDF, 'application/pdf'))])
        self.assertIn('opened=1', response.url)
        walkout = self.env['ems.student_walkout'].search([('group_id', '=', self.group.id)])
        self.assertEqual((walkout.walkout_date, walkout.state), (walkout_date, 'voting'))
        self.assertEqual(walkout.attachment_ids.mapped('name'), ['call.pdf'])

    def test_refused_call_shows_why(self):
        self._login(self.delegate)
        response = self._post('/my/vagues/nova', walkout_date=fields.Date.to_string(self.today + timedelta(days=3)),
                              files=[('union_call', ('call.pdf', PDF, 'application/pdf'))])
        self.assertIn('error=1', response.url)
        self.assertIn('too late', response.text)

    def test_reason_is_required_in_the_form_and_on_the_server(self):
        self._login(self.delegate)
        self.assertRegex(self.url_open('/my/vagues/nova').text, r'<textarea[^>]*id="notes"[^>]*required="required"')
        response = self._post('/my/vagues/nova', walkout_date=fields.Date.to_string(self.today + timedelta(days=7)),
                              notes='   ', files=[('union_call', ('call.pdf', PDF, 'application/pdf'))])
        self.assertIn('error=1', response.url)
        self.assertIn('reason of the walkout', response.text)
        self.assertFalse(self.env['ems.student_walkout'].search([('group_id', '=', self.group.id)]))

    def test_classmate_votes_then_joins(self):
        walkout = open_walkout(self)
        self._login(self.classmate)
        self.assertIn('o_ems_walkout_banner', self.url_open('/my/home').text)
        self.assertNotIn('/my/vagues/nova', self.url_open('/my/vagues').text, "Only the delegates call one.")
        page = self.url_open(f'/my/vagues/{walkout.id}').text
        self.assertIn('o_ems_walkout_vote', page)
        self.assertNotIn('o_ems_walkout_join', page, "Joining comes after the group vote.")
        self._post(f'/my/vagues/{walkout.id}/vota', group_vote='yes')
        self.assertEqual(walkout.group_yes_count, 1)
        self.assertNotIn('o_ems_walkout_banner', self.url_open('/my/home').text)
        # A classmate cannot cancel it: the student is always the logged-in one, and not its delegate.
        self._post(f'/my/vagues/{walkout.id}/anulla')
        self.assertEqual(walkout.state, 'voting')
        walkout._ems_portal_vote(self.delegate, 'yes')
        self.assertEqual(walkout.state, 'joining', "Two yes of three: the result is decided.")
        page = self.url_open(f'/my/vagues/{walkout.id}').text
        self.assertIn('o_ems_walkout_join', page)
        self.assertIn('o_ems_walkout_banner', self.url_open('/my/home').text, "A pending answer: whether to join.")
        self._post(f'/my/vagues/{walkout.id}/suma', joins='yes')
        self.assertEqual(walkout.joining_student_ids, self.classmate)

    def test_a_student_given_access_after_the_proposal_joins(self):
        """Issue #830: told they cannot vote while the group votes, and able to join once it opens."""
        walkout = open_walkout(self)
        self.env['res.users'].with_context(no_reset_password=True).create({
            'name': self.offline.name, 'login': 'test_walkout_offline_late', 'password': 'test_walkout_offline_late',
            'partner_id': self.offline.id, 'lang': 'en_US', 'groups_id': [(6, 0, [self.env.ref('base.group_portal').id])],
        })
        self._login(self.offline)
        page = self.url_open(f'/my/vagues/{walkout.id}').text
        self.assertNotIn('o_ems_walkout_vote', page)
        self.assertIn('so you cannot vote', page)
        walkout._ems_portal_vote(self.delegate, 'yes')
        walkout._ems_portal_vote(self.subdelegate, 'yes')
        self.assertEqual(walkout.state, 'joining')
        self.assertIn('o_ems_walkout_banner', self.url_open('/my/home').text)
        page = self.url_open(f'/my/vagues/{walkout.id}').text
        self.assertIn('o_ems_walkout_join', page)
        self.assertNotIn('so you cannot', page)
        self._post(f'/my/vagues/{walkout.id}/suma', joins='yes')
        self.assertIn(self.offline, walkout.joining_student_ids)

    def test_delegate_cancels_the_call(self):
        walkout = open_walkout(self)
        self._login(self.subdelegate)
        page = self.url_open(f'/my/vagues/{walkout.id}').text
        self.assertIn('o_ems_walkout_manage', page)
        self._post(f'/my/vagues/{walkout.id}/anulla')
        self.assertEqual(walkout.state, 'cancelled')

    def test_the_group_sees_why_a_call_was_rejected(self):
        walkout = open_walkout(self)
        reject_walkout(walkout, self.head_of_studies, 'ems.student_walkout_rejection_region')
        self._login(self.classmate)
        page = self.url_open(f'/my/vagues/{walkout.id}').text
        self.assertIn('o_ems_walkout_rejected', page)
        self.assertIn(walkout.rejection_reason_id.name, page)

    def test_family_and_outsiders_are_sent_away(self):
        walkout = open_walkout(self)
        self.authenticate(self.family_user.login, self.family_user.login)
        self.assertNotIn('/my/vagues"', self.url_open('/my/home').text)
        self.assertTrue(self.url_open(f'/my/vagues/{walkout.id}').url.endswith('/my/home'))
        self._post(f'/my/vagues/{walkout.id}/vota', group_vote='yes')
        self.assertEqual(walkout.group_yes_count, 0)

    def test_the_family_ratifies_that_a_minor_joins(self):
        walkout = open_walkout(self)
        walkout._ems_portal_vote(self.delegate, 'yes')
        walkout._ems_portal_vote(self.subdelegate, 'yes')
        walkout._ems_portal_join(self.classmate, True)
        line = walkout.line_ids.filtered(lambda line: line.student_id == self.classmate)
        self.authenticate(self.family_user.login, self.family_user.login)
        home = self.url_open('/my/home').text
        self.assertIn('o_ems_walkout_ratify_banner', home)
        self.assertIn('href="/my/vagues" class="nav-link"', home)
        page = self.url_open('/my/vagues').text
        self.assertIn('o_ems_walkout_ratify', page)
        self.assertIn(f'<strong>{self.classmate.name}</strong>', page)
        self.assertNotIn(f'<strong>{self.subdelegate.name}</strong>', page, "Only the children who join.")
        # A family can only answer for its own children: another call's line is refused.
        self._post(f'/my/vagues/ratifica/{line.id}', decision='yes')
        self.assertEqual(line.ratification, 'ratified')
        self.assertNotIn('o_ems_walkout_ratify_banner', self.url_open('/my/home').text)
        self._post(f'/my/vagues/ratifica/{line.id}', decision='no')
        self.assertEqual(line.ratification, 'refused')


    # --- Issue #833: whoever signs in, by password or with Google, gets their own portal ---------

    def _password_login(self, user, login):
        """Sign in by password with `login` (what the person types), as the login page does."""
        user.password = 'shared-email-833'
        self.authenticate(login, 'shared-email-833')

    def _corporate_domain(self, *students):
        """A Workspace domain of its own (a personal email may never be on it, issue #514) and a
        corporate email on it for each student."""
        self.env.company.google_ws_domain = 'school-833.example.net'
        for student in students:
            student.student_email = f'{student.student_id.lower()}@school-833.example.net'

    def _google_login(self, email):
        """The login Google sign-in opens for a verified corporate email (auth_oauth's own step)."""
        return self.env['res.users'].sudo()._auth_oauth_signin(
            self.env.ref('auth_oauth.provider_google').id,
            {'user_id': f'google-{email}', 'email': email, 'email_verified': True},
            {'access_token': 'token-833', 'state': '{}'})

    def _assert_student_mode(self):
        """The student's own portal: the walkouts entry and the proposal form (a delegate or
        sub-delegate), never a family's ratification page."""
        home = self.url_open('/my/home').text
        self.assertIn('href="/my/vagues" class="nav-link"', home)
        self.assertNotIn('o_ems_walkout_ratify_banner', home)
        self.assertIn('/my/vagues/nova', self.url_open('/my/vagues').text)
        self.assertEqual(self.url_open('/my/vagues/nova').status_code, 200)

    def test_a_student_sharing_the_email_signs_in_as_a_student_and_the_family_as_a_family(self):
        self._corporate_domain(self.subdelegate)
        self.subdelegate.email = self.family.email
        (self.family | self.subdelegate)._ems_sync_portal_login()
        student_user, family_user = self.subdelegate.user_ids, self.family_user
        self.assertEqual(student_user.login, self.subdelegate.student_email)
        self.assertEqual(family_user.login, self.family.email)

        # The student: with the corporate email and the portal password, or with Google.
        self._password_login(student_user, self.subdelegate.student_email)
        self._assert_student_mode()
        self.assertEqual(self._google_login(self.subdelegate.student_email), student_user.login)

        # The family, with the shared email: the family's portal, never the student's.
        walkout = open_walkout(self)
        walkout._ems_portal_vote(self.delegate, 'yes')
        walkout._ems_portal_vote(self.subdelegate, 'yes')
        walkout._ems_portal_join(self.subdelegate, True)
        self._password_login(family_user, self.family.email)
        home = self.url_open('/my/home').text
        self.assertIn('o_ems_walkout_ratify_banner', home)
        page = self.url_open('/my/vagues').text
        self.assertIn('o_ems_walkout_ratify', page)
        self.assertIn(f'<strong>{self.subdelegate.name}</strong>', page)
        # A family never proposes a walkout for its child: back to its ratification page.
        response = self.url_open('/my/vagues/nova')
        self.assertTrue(response.url.endswith('/my/vagues'))
        self.assertIn('o_ems_walkout_ratify', response.text)
        self.assertNotIn('o_ems_walkout_calendar', response.text)

    def test_a_student_with_their_own_email_signs_in_as_a_student_both_ways(self):
        self._corporate_domain(self.delegate)
        self.delegate.email = 'delegate.own.833@example.org'
        self.delegate._ems_sync_portal_login()
        user = self.delegate.user_ids
        self.assertEqual(user.login, 'delegate.own.833@example.org')
        self._password_login(user, 'delegate.own.833@example.org')
        self._assert_student_mode()
        self.assertEqual(self._google_login(self.delegate.student_email), user.login)

    def test_delegate_extends_the_joining_once_from_the_portal(self):
        """Issue #838: also once it is closed; a classmate never."""
        walkout = open_walkout(self, days=14)
        walkout._ems_portal_vote(self.delegate, 'yes')
        walkout._ems_portal_vote(self.subdelegate, 'yes')
        walkout._ems_close()
        self._login(self.classmate)
        self.assertNotIn('o_ems_walkout_extend', self.url_open(f'/my/vagues/{walkout.id}').text)
        self._post(f'/my/vagues/{walkout.id}/amplia')
        self.assertEqual(walkout.state, 'closed')
        self._login(self.delegate)
        self.assertIn('o_ems_walkout_extend_send', self.url_open(f'/my/vagues/{walkout.id}').text)
        response = self._post(f'/my/vagues/{walkout.id}/amplia')
        self.assertIn('saved=1', response.url)
        self.assertEqual((walkout.state, walkout.delegate_extended), ('joining', True))
        self.assertNotIn('o_ems_walkout_extend_send', self.url_open(f'/my/vagues/{walkout.id}').text,
                         "Only once.")
        response = self._post(f'/my/vagues/{walkout.id}/amplia')
        self.assertIn('error=1', response.url)

    def test_a_shortened_joining_warns_the_delegate(self):
        """Issue #838: Friday is only possible with a shorter joining phase: it is created, with a warning."""
        self._login(self.delegate)
        friday = fields.Date.to_string(self.today + timedelta(days=4))
        response = self._post('/my/vagues/nova', walkout_date=friday, notes='Union',
                              files=[('union_call', ('call.pdf', PDF, 'application/pdf'))])
        self.assertIn('opened=1', response.url)
        self.assertIn('o_ems_walkout_join_cut', response.text)
        self.assertIn('14.0 h at most instead of 24 h', response.text)
        self.assertIn('up to a maximum of 24 h', response.text)
        self._login(self.classmate)
        walkout = self.env['ems.student_walkout'].search([('group_id', '=', self.group.id)])
        self.assertNotIn('o_ems_walkout_join_cut', self.url_open(f'/my/vagues/{walkout.id}').text,
                         "Only the delegates are warned.")
