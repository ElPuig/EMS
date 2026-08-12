from odoo.tests.common import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestAspTour(HttpCase):

    def test_asp_crud_tour(self):
        self.start_tour("/odoo", "ems_asp_crud", login="admin")

        employee = self.env['hr.employee'].search([('name', '=', 'ASP Tour Employee')])
        self.assertEqual(len(employee), 1)
        self.assertEqual(employee.employee_type, 'asp')

    def test_asp_role_crud_tour(self):
        self.start_tour("/odoo", "ems_asp_role_crud", login="admin")

        role = self.env['ems.role'].search([('name', '=', 'ASP Tour Role')])
        self.assertEqual(len(role), 1)
        self.assertEqual(role.employee_type, 'asp')
