from odoo.tests.common import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestJobTour(HttpCase):

    def test_job_crud_tour(self):
        self.start_tour("/odoo", "ems_job_crud", login="admin")

        job = self.env['hr.job'].search([('name', '=', 'Tour Job Position')])
        self.assertEqual(len(job), 1)
