from odoo.tests import HttpCase, tagged

from .common import mock_outgoing_email
from .test_certificate import create_certificate_fixtures


@tagged('post_install', '-at_install')
class TestCertificateTour(HttpCase):
    """Issue #835 - proves the certificate request screens render and work in a browser for the
    least-privileged role that uses them: the VET coordinator, who opens the list (Pending for me),
    completes the workplace training on the form, attaches the required document only their position
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
            'fct_school_year': '2025-2026', 'period_start': '2026-03-01', 'period_end': '2026-06-15',
        })
        cls.certificate._ems_submit()

    def test_coordinator_completes_the_training(self):
        self.start_tour("/odoo", 'ems_certificate_complete', login=self.coordinator.login)
        self.assertEqual(self.certificate.step_id, self.steps[1])
        self.assertEqual((self.certificate.training_company_id, self.certificate.hours), (self.company, 400))
        report = self.certificate.document_ids.filtered(lambda line: line.type_document_id == self.report_document)
        self.assertEqual(report.attachment_ids.mapped('name'), ['Report.pdf'])
        self.assertEqual(report.attachment_ids.res_id, report.id, "The file follows the request's access rights.")
