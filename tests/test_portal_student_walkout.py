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

    def test_delegate_sees_the_card_and_requests_a_walkout(self):
        self._login(self.delegate)
        home = self.url_open('/my/home').text
        self.assertIn('href="/my/vagues" class="nav-link"', home)
        self.assertIn('/my/vagues/nova', self.url_open('/my/vagues').text)
        self.assertEqual(self.url_open('/my/vagues/nova').status_code, 200)
        walkout_date = self.today + timedelta(days=4)
        response = self._post('/my/vagues/nova', walkout_date=fields.Date.to_string(walkout_date), notes='Union',
                              files=[('union_call', ('call.pdf', PDF, 'application/pdf'))])
        self.assertIn('opened=1', response.url)
        walkout = self.env['ems.student_walkout'].search([('group_id', '=', self.group.id)])
        self.assertEqual(walkout.walkout_date, walkout_date)
        self.assertEqual(walkout.attachment_ids.mapped('name'), ['call.pdf'])

    def test_refused_request_shows_why(self):
        self._login(self.delegate)
        response = self._post('/my/vagues/nova', walkout_date=fields.Date.to_string(self.today + timedelta(days=1)),
                              files=[('union_call', ('call.pdf', PDF, 'application/pdf'))])
        self.assertIn('error=1', response.url)
        self.assertIn('72', response.text)

    def test_classmate_votes_then_joins(self):
        walkout = open_walkout(self)
        self._login(self.classmate)
        self.assertIn('o_ems_walkout_banner', self.url_open('/my/home').text)
        self.assertNotIn('/my/vagues/nova', self.url_open('/my/vagues').text, "Only the delegates request one.")
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
        walkout._ems_portal_vote(self.subdelegate, 'no')
        self.assertEqual(walkout.state, 'joining')
        page = self.url_open(f'/my/vagues/{walkout.id}').text
        self.assertIn('o_ems_walkout_join', page)
        self.assertIn('o_ems_walkout_banner', self.url_open('/my/home').text, "A pending answer: whether to join.")
        self._post(f'/my/vagues/{walkout.id}/suma', joins='yes')
        self.assertEqual(walkout.joining_student_ids, self.classmate)

    def test_delegate_cancels_the_request(self):
        walkout = open_walkout(self)
        self._login(self.subdelegate)
        page = self.url_open(f'/my/vagues/{walkout.id}').text
        self.assertIn('o_ems_walkout_manage', page)
        self.assertNotIn('/tanca', page, "The calendar is fixed: no closing by hand.")
        self._post(f'/my/vagues/{walkout.id}/anulla')
        self.assertEqual(walkout.state, 'cancelled')

    def test_a_call_waiting_for_the_head_of_studies_is_only_for_its_delegate(self):
        walkout = open_walkout(self, accept=False)
        self._login(self.classmate)
        self.assertTrue(self.url_open(f'/my/vagues/{walkout.id}').url.endswith('/my/home'))
        self._login(self.delegate)
        self.assertIn('o_ems_walkout_pending', self.url_open(f'/my/vagues/{walkout.id}').text)
        reject_walkout(walkout, self.head_of_studies, 'ems.student_walkout_rejection_region')
        page = self.url_open(f'/my/vagues/{walkout.id}').text
        self.assertIn('o_ems_walkout_rejected', page)
        self.assertIn(walkout.rejection_reason_id.name, page)

    def test_family_and_outsiders_are_sent_away(self):
        walkout = open_walkout(self)
        family_user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': self.family.name, 'login': 'test_walkout_family_wlp', 'password': 'test_walkout_family_wlp',
            'partner_id': self.family.id, 'groups_id': [(6, 0, [self.env.ref('base.group_portal').id])],
        })
        self.authenticate(family_user.login, family_user.login)
        self.assertNotIn('/my/vagues"', self.url_open('/my/home').text)
        self.assertTrue(self.url_open(f'/my/vagues/{walkout.id}').url.endswith('/my/home'))
        self._post(f'/my/vagues/{walkout.id}/vota', group_vote='yes')
        self.assertEqual(walkout.group_yes_count, 0)
