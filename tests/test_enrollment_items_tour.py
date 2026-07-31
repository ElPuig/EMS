from odoo.tests.common import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestEnrollmentItemsTour(HttpCase):

    def test_enrollment_item_crud_tour(self):
        self.start_tour("/odoo", "ems_enrollment_item_crud", login="admin")

        product = self.env['product.template'].search([('name', '=', 'Tour Enrollment Item')])
        self.assertEqual(len(product), 1)
        self.assertEqual(product.default_code, 'TOUR-ITEM')
