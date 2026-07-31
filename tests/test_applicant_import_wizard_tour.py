from odoo.tests.common import HttpCase, tagged

from .common import create_level_study_group


@tagged('post_install', '-at_install')
class TestApplicantImportWizardTour(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Reverted automatically with the test's own transaction rollback (see
        # test_applicant_import_wizard.py for the same pattern).
        cls.env.company.center_code = '8028047'
        cls.level, cls.study, cls.group = create_level_study_group(
            cls, 'AIWT',
            level={'name': 'Test Level (Applicant Import Wizard Tour)'},
            study={'code': 'CFGM_ZZ99', 'name': 'Test Study (Applicant Import Wizard Tour)'},
        )

    def test_applicant_import_wizard_tour(self):
        applicant = self.env['res.partner'].search([('student_id', '=', '1234567890')])
        self.assertFalse(applicant)

        self.start_tour("/odoo", "ems_applicant_import_wizard_upload", login="admin")

        applicant = self.env['res.partner'].search([('student_id', '=', '1234567890')])
        self.assertEqual(len(applicant), 1)
        self.assertEqual(applicant.contact_type, 'applicant')
        self.assertEqual(applicant.study_id, self.study)
