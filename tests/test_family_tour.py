from odoo.tests.common import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestFamilyTour(HttpCase):

    def test_family_crud_tour(self):
        self.start_tour("/odoo", "ems_family_crud", login="admin")

        family = self.env['res.partner'].search([('name', '=', 'Tour Family Contact')])
        self.assertEqual(len(family), 1)
        self.assertEqual(family.contact_type, 'family')
