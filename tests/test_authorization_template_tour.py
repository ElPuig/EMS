from odoo.tests.common import HttpCase, tagged

from .common import force_user_language_to_english


@tagged('post_install', '-at_install')
class TestAuthorizationTemplateTour(HttpCase):

    def test_authorization_template_crud_tour(self):
        force_user_language_to_english(self, self.env.ref('base.user_admin'))
        self.start_tour("/odoo", "ems_authorization_template_crud", login="admin")

        template = self.env['ems.authorization.template'].search([('name', '=', 'Tour Authorization Template')])
        self.assertEqual(len(template), 1)
        self.assertIn('Tour legal text', template.legal_text)
