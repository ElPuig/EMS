from odoo.tests.common import HttpCase, tagged

from .common import create_level_study


@tagged('post_install', '-at_install')
class TestEnrollmentTemplateTour(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.level, cls.study = create_level_study(
            cls, 'TETT', level={'name': 'Test Level (Enrollment Template Tour)'},
            study={'name': 'Test Study (Enrollment Template Tour)'},
        )

    def test_enrollment_template_crud_tour(self):
        self.start_tour("/odoo", "ems_enrollment_template_crud", login="admin")

        template = self.env['sale.order.template'].search([('name', '=', 'Tour Enrollment Template')])
        self.assertEqual(len(template), 1)
        self.assertEqual(template.ems_study_id, self.study)
