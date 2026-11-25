from unittest.mock import patch

from odoo.tests import HttpCase, tagged

from .common import mock_outgoing_email
from .test_certificate import create_certificate_fixtures, one_page_pdf


@tagged('post_install', '-at_install')
class TestCertificateTour(HttpCase):
    """Issue #835 - proves the certificate request screens render and work in a browser for the
    least-privileged role that uses them: the VET coordinator, who opens the list (Pending for me),
    completes the details their step requires on the form, attaches the required document only their position
    attaches, and hands the request over. The portal pages are
    server-rendered and covered by test_portal_certificate.py; the configuration screens and the
    collaborating companies by the admin crawler (test_role_smoke_admin_tour.py)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        create_certificate_fixtures(cls, prefix='TCTR')
        cls.certificate = cls.env['ems.certificate'].create({
            'type_id': cls.certificate_type.id, 'student_id': cls.student.id, 'origin': 'portal',
            'student_name': cls.student.name, 'student_document': '12345678Z', 'study_id': cls.study.id,
        })
        cls.certificate._ems_set_values({'school_year': '2025-2026', 'start': '2026-03-01', 'end': '2026-06-15'})
        cls.certificate._ems_submit()

    def test_coordinator_completes_the_training(self):
        self.start_tour("/odoo", 'ems_certificate_complete', login=self.coordinator.login)
        self.assertEqual(self.certificate.step_id, self.steps[1])
        values = {line.field_id.key: line for line in self.certificate.value_ids}
        self.assertEqual((values['company'].value_company_id, values['hours'].value_number), (self.company, 400))
        report = self.certificate.document_ids.filtered(lambda line: line.type_document_id == self.report_document)
        self.assertEqual(report.attachment_ids.mapped('name'), ['Report.pdf'])
        self.assertEqual(report.attachment_ids.res_id, report.id, "The file follows the request's access rights.")
        other = self.certificate.other_document_ids
        self.assertEqual((other.name, other.append_to_certificate, other.attachment_ids.mapped('name')),
                         ('Hours sheet', True, ['Sheet.pdf']))

    def test_secretary_issues_it_now(self):
        """A request with every detail and document, still waiting for the coordinator: the secretary
        issues it right away, and the coordinator's step is skipped."""
        certificate = self.env['ems.certificate'].create({
            'type_id': self.certificate_type.id, 'origin': 'secretariat', 'student_name': 'TCTR Ready Student',
            'applicant_email': 'tctr.ready@example.com', 'student_document': '87654321X', 'study_id': self.study.id,
        })
        certificate._ems_set_values({'school_year': '2025-2026', 'company': self.company.id, 'start': '2026-03-01',
                                     'end': '2026-06-15', 'hours': 400})
        certificate._ems_submit()
        for line in certificate.document_ids:
            line.attachment_ids = [(0, 0, {'name': 'doc.pdf', 'raw': one_page_pdf(), 'mimetype': 'application/pdf',
                                           'res_model': 'ems.certificate.document', 'res_id': line.id})]
        self.start_tour("/odoo", 'ems_certificate_issue_now', login=self.secretary.login)
        self.assertEqual(certificate.step_id, self.steps[2])
        self.assertTrue(certificate.name)
        self.assertEqual(certificate.activity_ids.user_id, self.director)

    def test_secretary_finds_an_archived_former_student(self):
        """Issue #858: former students and withdrawals are archived, and the Student dropdown still
        offers them."""
        alumna = self.env['res.partner'].create({
            'name': 'TCTR Alumna Archived', 'contact_type': 'alumni', 'student_id': 'TCTR858ALUMNA',
            'email': 'tctr.alumna@example.com',
            'active': False,
        })
        self.start_tour("/odoo", 'ems_certificate_former_student', login=self.secretary.login)
        certificate = self.env['ems.certificate'].search([('student_id', '=', alumna.id)])
        self.assertEqual((len(certificate), certificate.student_name, certificate.applicant_email),
                         (1, 'TCTR Alumna Archived', 'tctr.alumna@example.com'))

    def test_director_attests(self):
        """Issue #861: the Director, who approves certificates, attests a request instead of waiting
        for it to be issued."""
        certificate = self.env['ems.certificate'].create({
            'type_id': self.certificate_type.id, 'origin': 'secretariat', 'student_name': 'TCTR Attested Student',
            'applicant_email': 'tctr.attested@example.com', 'student_document': '11223344B', 'study_id': self.study.id,
        })
        certificate._ems_set_values({'school_year': '2025-2026', 'company': self.company.id, 'start': '2026-03-01',
                                     'end': '2026-06-15', 'hours': 400})
        certificate._ems_submit()
        for line in certificate.document_ids:
            line.attachment_ids = [(0, 0, {'name': 'doc.pdf', 'raw': one_page_pdf(), 'mimetype': 'application/pdf',
                                           'res_model': 'ems.certificate.document', 'res_id': line.id})]
        # Odoo renders reports as HTML under test: a real PDF, so the annexes can be merged.
        with patch('odoo.addons.base.models.ir_actions_report.IrActionsReport._render_qweb_pdf',
                   return_value=(one_page_pdf(), 'pdf')):
            self.start_tour("/odoo", 'ems_certificate_attest', login=self.director.login)
        self.assertEqual((certificate.state, certificate.document_kind), ('issued', 'attestation'))
        self.assertEqual(certificate.stamp_ids.mapped('action'), ['attest'])
