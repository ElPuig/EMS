from odoo.tests import tagged, HttpCase


@tagged('post_install', '-at_install')
class TestGradeImportWizardTour(HttpCase):

    def test_grade_import_wizard_missing_sheet_tour(self):
        self.start_tour("/odoo", "ems_grade_import_wizard_missing_sheet", login="admin")

    def test_import_wizard_form_renders(self):
        # To observe this tour in a real browser during development:
        #   self.start_tour("/odoo", "ems_grade_import_wizard_smoke", login="admin", watch=True)
        self.start_tour("/odoo", "ems_grade_import_wizard_smoke", login="admin")
