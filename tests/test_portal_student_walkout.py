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
        walkout_date = self.today + timedelta(days=7)
        self.assertIn(f'min="{fields.Date.to_string(walkout_date)}"', form.text)
        response = self._post('/my/vagues/nova', walkout_date=fields.Date.to_string(walkout_date), notes='Union',
                              files=[('union_call', ('call.pdf', PDF, 'application/pdf'))])
        self.assertIn('opened=1', response.url)
        walkout = self.env['ems.student_walkout'].search([('group_id', '=', self.group.id)])
        self.assertEqual((walkout.walkout_date, walkout.state), (walkout_date, 'voting'))
        self.assertEqual(walkout.attachment_ids.mapped('name'), ['call.pdf'])

    def test_refused_call_shows_why(self):
        self._login(self.delegate)
        response = self._post('/my/vagues/nova', walkout_date=fields.Date.to_string(self.today + timedelta(days=4)),
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

