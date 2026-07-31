from odoo.tests.common import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestProviderTour(HttpCase):

    def test_provider_crud_tour(self):
        self.start_tour("/odoo", "ems_provider_crud", login="admin")

        provider = self.env['res.partner'].search([
            ('name', '=', 'Tour Provider Contact'), ('contact_type', '=', 'provider'),
        ])
        self.assertEqual(len(provider), 1)
