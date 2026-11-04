from datetime import timedelta

from odoo import fields
from odoo.http import Request
from odoo.tests.common import HttpCase, tagged

from .common import mock_outgoing_email
from .test_erasmus import PDF, create_erasmus_fixtures


def create_portal_erasmus_fixtures(cls):
    """create_erasmus_fixtures() plus portal users for the eligible student and the outsider
    (login doubles as password)."""
    create_erasmus_fixtures(cls)
    cls.student_user, cls.outsider_user = cls.env['res.users'].with_context(no_reset_password=True).create([{
        'name': partner.name, 'login': login, 'password': login, 'partner_id': partner.id,
        'lang': 'en_US', 'groups_id': [(6, 0, [cls.env.ref('base.group_portal').id])],
    } for partner, login in (
        (cls.student, 'test_portal_erasmus_student'),
        (cls.outsider, 'test_portal_erasmus_outsider'),
    )])


@tagged('post_install', '-at_install')
class TestPortalErasmus(HttpCase):
    """Issue #683 - the portal's Erasmus+ page (/my/erasmus): applying, uploading and submitting,
    always as the logged-in student."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        create_portal_erasmus_fixtures(cls)

    def _login(self, user):
        self.authenticate(user.login, user.login)

    def _save(self, submit=False, **answers):
        data = {'csrf_token': Request.csrf_token(self), **answers}
        if submit:
            data['submit'] = '1'
        files = [(f'document_{self.cv.id}', ('cv.pdf', PDF, 'application/pdf'))]
        return self.url_open(f'/my/erasmus/call/{self.call.id}/save', data=data, files=files)

    def _application(self):
        return self.env['ems.erasmus.application'].search([
            ('call_id', '=', self.call.id), ('partner_id', '=', self.student.id)])

    def test_eligible_student_sees_the_call(self):
        self._login(self.student_user)
        response = self.url_open('/my/erasmus')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Test Erasmus Call', response.text)
        home = self.url_open('/my/home').text
        self.assertIn('/my/erasmus', home)
        self.assertIn('href="/my/erasmus" class="nav-link"', home, "The portal menu has an entry, like the card.")

    def test_student_of_another_level_is_sent_home(self):
        self._login(self.outsider_user)
        home = self.url_open('/my/home').text
        self.assertNotIn('/my/erasmus"', home, "Neither the card nor the portal menu entry.")
        response = self.url_open('/my/erasmus')
        self.assertTrue(response.url.endswith('/my/home'))
        response = self.url_open(f'/my/erasmus/call/{self.call.id}')
        self.assertTrue(response.url.endswith('/my/home'))

    def test_save_then_submit(self):
        self._login(self.student_user)
        self._save(applicant_notes='Summer only')
        application = self._application()
        self.assertEqual(application.state, 'draft')
        self.assertEqual(application.applicant_notes, 'Summer only')
        self.assertEqual(application.document_ids.attachment_ids.mapped('name'), ['cv.pdf'])
        response = self._save(submit=True, applicant_notes='Summer only')
        self.assertIn('submitted=1', response.url)
        self.assertEqual(application.state, 'submitted')

    def test_application_form_renders(self):
        self._login(self.student_user)
        response = self.url_open(f'/my/erasmus/call/{self.call.id}')
        self.assertEqual(response.status_code, 200)
        self.assertIn('o_ems_erasmus_form', response.text)
        self.assertIn(f'document_{self.cv.id}', response.text)
        self.assertNotIn(f'document_{self.authorization.id}', response.text, "Minors-only document hidden to adults")

    def test_subsanation_only_offers_the_documents_asked_for(self):
        self._login(self.student_user)
        self._save(submit=True)
        application = self._application()
        application.document_ids.filtered(lambda line: line.call_document_id == self.cv).action_mark_needs_change()
        application.action_request_subsanation()
        self.call.action_close()
        page = self.url_open(f'/my/erasmus/call/{self.call.id}').text
        self.assertIn('o_ems_erasmus_subsanation', page)
        self.assertIn(f'name="document_{self.cv.id}"', page)
        self.assertNotIn(f'name="document_{self.certificate.id}"', page)
        self._save(submit=True)
        self.assertEqual(application.state, 'submitted')

    def test_closed_call_refuses_changes(self):
        self._login(self.student_user)
        self._save()
        self.call.date_close = fields.Datetime.now() - timedelta(hours=1)
        response = self._save(applicant_notes='Too late')
        self.assertIn('error=', response.url)
        self.assertFalse(self._application().applicant_notes)

    def test_rules_document_download(self):
        self.call.write({'rules_document': 'JVBERi0xLjQ=', 'rules_filename': 'call.pdf'})
        self._login(self.student_user)
        response = self.url_open(f'/my/erasmus/call/{self.call.id}/rules')
        self.assertEqual(response.content, b'%PDF-1.4')
        self._login(self.outsider_user)
        response = self.url_open(f'/my/erasmus/call/{self.call.id}/rules')
        self.assertNotEqual(response.content, b'%PDF-1.4')

    def test_admitted_applicant_sees_the_interview_call(self):
        """Issue #684: once called, the portal shows the interview's date and place."""
        self._login(self.student_user)
        self._save(submit=True)
        application = self._application()
        application._ems_set_state('admitted')
        application.write({'interview_date': fields.Datetime.now() + timedelta(days=3),
                           'interview_place': 'Room E12'})
        self.assertNotIn('o_ems_erasmus_interview', self.url_open(f'/my/erasmus/call/{self.call.id}').text)
        application.action_send_interview_call()
        page = self.url_open(f'/my/erasmus/call/{self.call.id}').text
        self.assertIn('o_ems_erasmus_interview', page)
        self.assertIn('Room E12', page)

    # The issue-#682 review: the step bar and the "what to do now" box.

    def _progress(self, application):
        progress = application._ems_portal_progress()
        return [status for _label, status in progress['steps']], progress['next']

    def test_progress_follows_the_application(self):
        self._login(self.student_user)
        self._save()
        application = self._application()
        statuses, nxt = self._progress(application)
        self.assertEqual(statuses[:2], ['current', 'todo'])
        self.assertEqual((nxt['level'], nxt['deadline'], nxt['is_date']), ('warning', self.call.date_close, False))
        application._ems_set_state('subsanation')
        statuses, nxt = self._progress(application)
        self.assertEqual(statuses[:2], ['done', 'current'])
        self.assertEqual((nxt['level'], nxt['key']), ('warning', 'subsanation'))
        application._ems_set_state('admitted')
        statuses, nxt = self._progress(application)
        self.assertEqual(statuses[2], 'current', "The interview step.")
        self.assertEqual((nxt['level'], nxt['key']), ('info', ''), "Nothing to do until called.")
        application.write({'interview_date': fields.Datetime.now() + timedelta(days=3), 'interview_place': 'Room E12'})
        application.action_send_interview_call()
        _statuses, nxt = self._progress(application)
        self.assertEqual((nxt['level'], nxt['key'], nxt['deadline']), ('warning', 'interview', application.interview_date))
        self.assertIn('Room E12', nxt['text'])
        application._ems_set_state('reserve')
        statuses, nxt = self._progress(application)
        self.assertEqual(statuses[:5], ['done', 'done', 'done', 'done', 'current'])
        self.assertEqual(nxt['level'], 'info', "A reserve waits for a free place.")

    def test_progress_marks_where_an_application_ended(self):
        self._login(self.student_user)
        self._save(submit=True)
        application = self._application()
        application._ems_set_state('excluded')
        statuses, nxt = self._progress(application)
        self.assertEqual(statuses[:3], ['done', 'failed', 'todo'])
        self.assertEqual(nxt['level'], 'secondary')
        application._ems_set_state('not_selected')
        statuses, _nxt = self._progress(application)
        self.assertEqual(statuses[3], 'failed', "Not selected in the resolution step.")

    def test_page_groups_the_calls(self):
        """Own applications first, then the open calls; a closed call folded away."""
        self._login(self.student_user)
        page = self.url_open('/my/erasmus').text
        self.assertIn('o_ems_erasmus_section_open', page)
        self.assertNotIn('o_ems_erasmus_section_mine', page)
        date_close = self.call.date_close
        self.call.date_close = fields.Datetime.now() - timedelta(hours=1)
        page = self.url_open('/my/erasmus').text
        self.assertIn('o_ems_erasmus_section_other', page)
        self.assertNotIn('o_ems_erasmus_section_open', page)
        self.call.date_close = date_close
        self._save(submit=True)
        page = self.url_open('/my/erasmus').text
        self.assertIn('o_ems_erasmus_section_mine', page)
        self.assertIn('o_ems_erasmus_steps', page)
        self.assertIn('o_ems_erasmus_state_submitted', page)
        self.assertIn('text-bg-info', page, "A submitted application has its own colour.")
        self.assertNotIn('o_ems_erasmus_section_open', page)

    def test_sent_application_folds_away(self):
        self._login(self.student_user)
        page = self.url_open(f'/my/erasmus/call/{self.call.id}').text
        self.assertIn('o_ems_erasmus_form_details" open="open"', page)
        self._save(submit=True)
        self.call.action_close()
        page = self.url_open(f'/my/erasmus/call/{self.call.id}').text
        self.assertIn('<details class="mb-4 o_ems_erasmus_form_details">', page, "Folded once sent and closed.")
        self.assertIn('o_ems_erasmus_next', page)
