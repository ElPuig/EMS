from odoo.tests.common import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestEmploymentTypeTour(HttpCase):

    def test_employment_type_crud_tour(self):
        self.start_tour("/odoo", "ems_employment_type_crud", login="admin")

        contract_type = self.env['hr.contract.type'].search([('name', '=', 'Tour Employment Type')])
        self.assertEqual(len(contract_type), 1)
