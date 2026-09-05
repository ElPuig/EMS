from odoo.tests.common import HttpCase, tagged

from .common import create_level_study_group, force_user_language_to_english


@tagged('post_install', '-at_install')
class TestStudentImportWizardTour(HttpCase):

    def test_student_import_wizard_missing_columns_tour(self):
        force_user_language_to_english(self, self.env.ref('base.user_admin'))
        self.start_tour("/odoo", "ems_student_import_wizard_missing_columns", login="admin")

    def test_student_import_wizard_success_tour(self):
        force_user_language_to_english(self, self.env.ref('base.user_admin'))
        # 'Grup Classe' in the uploaded xlsx (ESFERA-TOUR-A) must resolve via this group's
        # own external_id - see static/tests/tours/student_import_wizard_tour.js.
        create_level_study_group(
            self, 'TSIWT', level={'name': 'Test Level (Student Import Wizard Tour)'},
            study={'code': 'TSIWT01', 'name': 'Test Study (Student Import Wizard Tour)'},
            group={'external_id': 'ESFERA-TOUR-A'},
        )
        self.start_tour("/odoo", "ems_student_import_wizard_success", login="admin")

        student = self.env['res.partner'].search([('student_id', '=', '9200001')])
        self.assertTrue(student)
        self.assertEqual(student.name, 'Esfera Success Tour Student Test')
        self.assertTrue(student.main_group_id)

        family = self.env['res.partner'].search([('document_id', '=', '55667788Y')])
        self.assertTrue(family)
        relation = self.env['res.partner.relation'].search([
            ('left_partner_id', '=', family.id), ('right_partner_id', '=', student.id),
        ])
        self.assertEqual(relation.type_id, self.env.ref('ems.relation_type_mother'))
