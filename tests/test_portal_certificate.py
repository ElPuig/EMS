from unittest.mock import patch

from odoo.http import Request
from odoo.tests.common import HttpCase, tagged

from .common import create_level_study_group, mock_outgoing_email, next_student_id
from .test_certificate import create_certificate_fixtures, one_page_pdf


@tagged('post_install', '-at_install')
class TestPortalCertificate(HttpCase):
    """Issue #835 - certificate requests on the portal: a current student files one from
    /my/certificats; a former student fills in the form, answers and downloads the certificate
    through the link with its access token, without logging in."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        create_certificate_fixtures(cls, prefix='TPCR')
        cls.student_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': cls.student.name, 'login': 'test_portal_certificate_student',
            'password': 'test_portal_certificate_student', 'partner_id': cls.student.id, 'lang': 'en_US',
            'groups_id': [(6, 0, [cls.env.ref('base.group_portal').id])],
        })
        # A student of a level no certificate type is offered to.
        _level, cls.other_study, other_group = create_level_study_group(cls, 'TPCX')
        cls.other_student = cls.env['res.partner'].create({
            'name': 'TPCX Student', 'contact_type': 'student', 'student_id': next_student_id(),
            'main_group_id': other_group.id, 'birth_date': '2000-01-01',
        })
        cls.other_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'TPCX Student', 'login': 'test_portal_certificate_other',
            'password': 'test_portal_certificate_other', 'partner_id': cls.other_student.id, 'lang': 'en_US',
            'groups_id': [(6, 0, [cls.env.ref('base.group_portal').id])],
        })

    def _form(self, **extra):
        return {
            'csrf_token': Request.csrf_token(self),
            'student_name': 'TPCR Student', 'student_document': '12345678Z', 'study_id': str(self.study.id),
            'fct_school_year': '2025-2026', 'company_name': 'Some Company', **extra,
        }

    def _requests(self):
        return self.env['ems.certificate'].search([('student_id', '=', self.student.id)])

    def test_current_student_requests_from_the_portal(self):
        self.authenticate(self.student_user.login, self.student_user.login)
        response = self.url_open('/my/certificats')
        self.assertIn('o_ems_certificate_new', response.text)
        self.assertIn(self.study.name, response.text)
        self.assertIn('id="certificate_new_body" class="collapse "', response.text, "The form starts folded.")
        self.assertNotIn(self.other_study.name, response.text, "Only studies of the type's levels are offered.")
        self.assertIn(f'<option value="{self.env["ems.course"].search([], limit=1).name}"', response.text,
                      "The courses EMS has are suggested for the school year.")

        response = self.url_open('/my/certificats/submit', data=self._form(student_document=''))
        self.assertIn('error=missing', response.url)
        self.assertIn('id="certificate_new_body" class="collapse show"', response.text,
                      "Back with an error, the form is open.")
        self.assertFalse(self._requests())

        # The agreement (anyone attaches it) and an optional file; the training report is only the
        # first step's position's, so the portal does not offer it and ignores it if sent.
        self.assertIn(f'document_{self.agreement_document.id}', response.text)
        self.assertNotIn(f'document_{self.report_document.id}', response.text)
        files = [(f'document_{self.agreement_document.id}', ('agreement.pdf', one_page_pdf(), 'application/pdf')),
                 (f'document_{self.report_document.id}', ('report.pdf', one_page_pdf(), 'application/pdf')),
                 ('documents', ('other.pdf', one_page_pdf(), 'application/pdf'))]
        response = self.url_open('/my/certificats/submit', data=self._form(), files=files)
        self.assertIn('submitted=1', response.url)
        certificate = self._requests()
        self.assertEqual((certificate.state, certificate.origin, certificate.step_id),
                         ('in_progress', 'portal', self.steps[0]))
        self.assertEqual((certificate.requester_id, certificate.company_name), (self.student, 'Some Company'))
        agreement, report = certificate.document_ids.sorted('sequence')
        self.assertEqual(agreement.attachment_ids.mapped('name'), ['agreement.pdf'])
        self.assertFalse(report.attachment_ids)
        self.assertEqual(certificate.other_attachment_ids.mapped('name'), ['other.pdf'])

    def test_not_offered_to_other_levels(self):
        self.authenticate(self.other_user.login, self.other_user.login)
        self.assertNotIn('/my/certificats', self.url_open('/my/certificats').url)

    def test_former_student_by_link(self):
        certificate = self.env['ems.certificate'].create({
            'type_id': self.certificate_type.id, 'student_id': self.student.id,
            'applicant_email': 'former@example.com',
        })
        url = certificate.get_portal_url()
        # Without logging in (a public session): the token opens it, a wrong one does not.
        self.authenticate(None, None)
        self.assertIn('o_ems_certificate_form', self.url_open(url).text)
        wrong = self.url_open(f'/my/certificats/{certificate.id}?access_token=wrong')
        self.assertNotIn('o_ems_certificate_form', wrong.text)

        token = certificate.access_token
        response = self.url_open(f'/my/certificats/{certificate.id}/submit?access_token={token}',
                                 data=self._form(hours='300'))
        self.assertIn('submitted=1', response.url)
        self.assertEqual((certificate.state, certificate.hours), ('in_progress', 300))

        certificate._ems_request_documentation('Attach the agreement')
        response = self.url_open(f'/my/certificats/{certificate.id}/reply?access_token={token}',
                                 data={'csrf_token': Request.csrf_token(self), 'message': ''})
        self.assertIn('error=reply', response.url)
        files = [(f'document_{self.agreement_document.id}', ('agreement.png', b'\x89PNG fake', 'image/png'))]
        response = self.url_open(f'/my/certificats/{certificate.id}/reply?access_token={token}',
                                 data={'csrf_token': Request.csrf_token(self), 'message': 'Here'}, files=files)
        self.assertIn('replied=1', response.url)
        self.assertEqual(certificate.state, 'in_progress')
        self.assertEqual(certificate.document_ids.attachment_ids.mapped('name'), ['agreement.png'])

    def test_request_summary(self):
        """The request's page shows the applicant what they wrote and what the centre added."""
        certificate = self.env['ems.certificate'].create({
            'type_id': self.certificate_type.id, 'student_id': self.student.id, 'origin': 'portal',
            'student_name': 'TPCR Student', 'student_document': '12345678Z', 'study_id': self.study.id,
            'fct_school_year': '2025-2026', 'company_name': 'As Written SL',
        })
        certificate._ems_submit()
        certificate.write({'training_company_id': self.company.id, 'hours': 380})
        self.authenticate(None, None)
        html = self.url_open(certificate.get_portal_url()).text
        self.assertIn('o_ems_certificate_summary', html)
        for text in ('12345678Z', '2025-2026', self.company.name, 'B12345678', '380', self.steps[0].name):
            self.assertIn(text, html)
        self.assertNotIn('As Written SL', html, "The company the centre linked replaces the one written.")

    def test_download_the_issued_certificate(self):
        certificate = self.env['ems.certificate'].create({
            'type_id': self.certificate_type.id, 'student_id': self.student.id, 'origin': 'portal',
            'student_name': 'TPCR Student', 'student_document': '12345678Z', 'study_id': self.study.id,
            'fct_school_year': '2025-2026', 'training_company_id': self.company.id, 'hours': 300,
            'period_start': '2026-03-01', 'period_end': '2026-06-01',
        })
        certificate._ems_submit()
        pdf_url = f'/my/certificats/{certificate.id}/pdf?access_token={certificate._portal_ensure_token()}'
        self.assertNotIn('%PDF', self.url_open(pdf_url).text, "Nothing to download before it is issued.")
        for line in certificate.document_ids:
            line.attachment_ids = [(0, 0, {'name': 'a.pdf', 'raw': one_page_pdf(), 'mimetype': 'application/pdf'})]
        with patch('odoo.addons.base.models.ir_actions_report.IrActionsReport._render_qweb_pdf',
                   return_value=(one_page_pdf(), 'pdf')):
            for _step in range(3):
                certificate.action_done_step()
        self.assertEqual(certificate.state, 'issued')
        response = self.url_open(pdf_url)
        self.assertEqual(response.headers['Content-Type'], 'application/pdf')
        self.assertTrue(response.content.startswith(b'%PDF'))
