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
        self.assertIn('/my/erasmus', self.url_open('/my/home').text)

    def test_student_of_another_level_is_sent_home(self):
        self._login(self.outsider_user)
        self.assertNotIn('/my/erasmus"', self.url_open('/my/home').text)
        response = self.url_open('/my/erasmus')
        self.assertTrue(response.url.endswith('/my/home'))
        response = self.url_open(f'/my/erasmus/call/{self.call.id}')
        self.assertTrue(response.url.endswith('/my/home'))

    def test_save_then_submit(self):
        self._login(self.student_user)
        self._save(availability='Summer only')
        application = self._application()
        self.assertEqual(application.state, 'draft')
        self.assertEqual(application.availability, 'Summer only')
        self.assertEqual(application.document_ids.attachment_ids.mapped('name'), ['cv.pdf'])
        response = self._save(submit=True, availability='Summer only')
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
        response = self._save(availability='Too late')
        self.assertIn('error=', response.url)
        self.assertFalse(self._application().availability)

    def test_rules_document_download(self):
        self.call.write({'rules_document': 'JVBERi0xLjQ=', 'rules_filename': 'call.pdf'})
        self._login(self.student_user)
        response = self.url_open(f'/my/erasmus/call/{self.call.id}/rules')
        self.assertEqual(response.content, b'%PDF-1.4')
        self._login(self.outsider_user)
        response = self.url_open(f'/my/erasmus/call/{self.call.id}/rules')
        self.assertNotEqual(response.content, b'%PDF-1.4')
