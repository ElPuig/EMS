from odoo.tests.common import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestGradeImportWizardTour(HttpCase):

    def test_grade_import_wizard_missing_sheet_tour(self):
        self.start_tour("/odoo", "ems_grade_import_wizard_missing_sheet", login="admin")
