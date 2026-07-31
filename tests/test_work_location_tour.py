from odoo.tests.common import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestWorkLocationTour(HttpCase):

    def test_work_location_crud_tour(self):
        self.start_tour("/odoo", "ems_work_location_crud", login="admin")

        location = self.env['hr.work.location'].search([('name', '=', 'Tour Work Location')])
        self.assertEqual(len(location), 1)
