from odoo.tests.common import TransactionCase


class TestRole(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.role_hos = cls.env.ref('ems.role_hos')

    def test_create_default_color(self):
        role = self.env['ems.role'].create({'name': 'Test role default color'})
        self.assertEqual(role.color, '#3A8DDE')

    def test_create_valid_hex_color(self):
        role = self.env['ems.role'].create({'name': 'Test role valid color', 'color': '#112233'})
        self.assertEqual(role.color, '#112233')

    def test_invalid_color_raises(self):
        with self.assertRaises(Exception):
            self.env['ems.role'].create({'name': 'Test role invalid color', 'color': 'not-a-color'})

    def test_seed_roles_have_distinct_colors(self):
        roles = self.env['ems.role'].search([])
        colors = roles.mapped('color')
        self.assertEqual(len(colors), len(set(colors)), "Two or more roles share the exact same color.")
