from odoo.tests.common import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestAuthorizationTemplateTour(HttpCase):

    def test_authorization_template_crud_tour(self):
        self.start_tour("/odoo", "ems_authorization_template_crud", login="admin")

        template = self.env['ems.authorization.template'].search([('name', '=', 'Tour Authorization Template')])
        self.assertEqual(len(template), 1)
        self.assertIn('Tour legal text', template.legal_text)
