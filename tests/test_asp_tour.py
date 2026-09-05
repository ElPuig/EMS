from odoo.tests.common import HttpCase, tagged

from .common import force_user_language_to_english


@tagged('post_install', '-at_install')
class TestAspTour(HttpCase):

    def test_asp_crud_tour(self):
        force_user_language_to_english(self, self.env.ref('base.user_admin'))
        self.start_tour("/odoo", "ems_asp_crud", login="admin")

        employee = self.env['hr.employee'].search([('name', '=', 'ASP Tour Employee')])
        self.assertEqual(len(employee), 1)
        self.assertEqual(employee.employee_type, 'asp')

    def test_asp_role_crud_tour(self):
        force_user_language_to_english(self, self.env.ref('base.user_admin'))
        self.start_tour("/odoo", "ems_asp_role_crud", login="admin")

        role = self.env['ems.role'].search([('name', '=', 'ASP Tour Role')])
        self.assertEqual(len(role), 1)
        self.assertEqual(role.employee_type, 'asp')
