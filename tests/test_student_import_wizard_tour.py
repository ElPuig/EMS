from odoo.tests.common import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestStudentImportWizardTour(HttpCase):

    def test_student_import_wizard_missing_columns_tour(self):
        self.start_tour("/odoo", "ems_student_import_wizard_missing_columns", login="admin")
