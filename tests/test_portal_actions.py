import base64
from datetime import date

from odoo.http import Request
from odoo.tests.common import HttpCase, tagged

from .common import mock_outgoing_email

FAKE_PDF = base64.b64encode(b'%PDF-1.4 fake test content')


@tagged('post_install', '-at_install')
class TestPortalActions(HttpCase):
    """The ~10 state-changing portal action routes (controllers/portal_enrollment.py) had zero
    coverage except portal_documentation_renew_iban (test_portal_enrollment.py). These are
    plain HttpCase.url_open() checks, not browser tours: a pure POST/GET action endpoint only
    needs to prove it doesn't 500 for a real request, matching the bar already set by the one
    action route that WAS tested - a page render deserves a tour, a state-mutation endpoint
    doesn't need more than this."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        cls.course = cls.env['ems.course'].search([('is_enrollment_default', '=', True)], limit=1) \
            or cls.env['ems.course'].create({'start': 2098, 'end': 2099, 'is_enrollment_default': True})
        cls.student = cls.env['res.partner'].create({
            'name': 'Portal Action Tour Student', 'contact_type': 'student',
        })
        cls.portal_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Portal Action Tour Student', 'login': 'test_portal_action_student',
            'partner_id': cls.student.id,
            'groups_id': [(6, 0, [cls.env.ref('base.group_portal').id])],
        })
        # A scopeless (no level/study restriction) template matches every order, so
        # sale.order's own authorization sync (_get_authorization_commands, triggered on
        # write) auto-creates the ems.authorization here - a second, manual (0, 0, {...})
        # command on top of it collides with the (enrollment_id, template_id) unique
        # constraint (confirmed empirically).
        cls.auth_template = cls.env['ems.authorization.template'].create({
            'name': 'Portal Action Tour Authorization', 'legal_text': '<p>Legal text</p>',
            'is_required': False, 'acceptance_only': False,
        })
        cls.order = cls.env['sale.order'].create({
            'partner_id': cls.student.id, 'ems_course_id': cls.course.id,
        })
        # get_portal_enrollment() only finds orders in state in ('sent', 'sale').
        cls.order.action_quotation_sent()
        cls.authorization = cls.order.ems_authorization_ids.filtered(
            lambda a: a.template_id == cls.auth_template)
        if not cls.authorization:
            cls.order.ems_authorization_ids = [(0, 0, {
                'template_id': cls.auth_template.id, 'status': 'pending',
            })]
            cls.authorization = cls.order.ems_authorization_ids.filtered(
                lambda a: a.template_id == cls.auth_template)

    def _authenticate(self):
        self.authenticate(self.portal_user.login, self.portal_user.login)

    def _post(self, url, data=None):
        self._authenticate()
        payload = {'csrf_token': Request.csrf_token(self)}
        payload.update(data or {})
        return self.url_open(url=url, data=payload)

    def test_select_student(self):
        response = self._post('/my/select-student/%d' % self.student.id)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.student.selected_student_id, self.student)

    def test_enrollment_authorize(self):
        response = self._post(
            '/my/gestion-matriculas/authorize/%d' % self.authorization.id,
            {'decision': 'yes'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.authorization.status, 'yes')

    def test_enrollment_confirm_comment(self):
        response = self._post(
            '/my/gestion-matriculas/confirm',
            {'action': 'comment', 'comments': 'Tour: a question about my enrollment'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.order.message_ids.filtered(
            lambda m: 'Tour: a question about my enrollment' in (m.body or '')))

    def test_authorization_document_download(self):
        self.authorization.write({
            'signed_document': FAKE_PDF, 'signed_document_name': 'cert.pdf',
        })
        self._authenticate()
        response = self.url_open(
            url='/my/gestion-matriculas/authorization/%d/document' % self.authorization.id,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, base64.b64decode(FAKE_PDF))

    def test_documentation_submit_iban(self):
        response = self._post('/my/documentacion/submit', {
            'doc_type': 'iban', 'doc_value': 'ES9121000418450200051332',
            'doc_value2': 'Portal Action Tour Student',
        })
        self.assertEqual(response.status_code, 200)
        document = self.env['ems.student.document'].search([
            ('partner_id', '=', self.student.id), ('doc_type', '=', 'iban'),
        ])
        self.assertEqual(len(document), 1)

    def test_documentation_cancel(self):
        document = self.env['ems.student.document'].create({
            'partner_id': self.student.id, 'doc_type': 'iban',
            'doc_value': 'ES9121000418450200051332', 'doc_value2': 'Portal Action Tour Student',
            'expiry_date': date.today(),
        })
        self.assertEqual(document.status, 'pending')

        response = self._post('/my/documentacion/cancel/%d' % document.id)

        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(document.status, 'pending')

    def test_documentation_download(self):
        document = self.env['ems.student.document'].create({
            'partner_id': self.student.id, 'doc_type': 'other',
            'doc_file': FAKE_PDF, 'doc_file_name': 'other.pdf',
        })
        self._authenticate()
        response = self.url_open(url='/my/documentacion/download/%d' % document.id)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, base64.b64decode(FAKE_PDF))
