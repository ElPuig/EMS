from odoo.tests import tagged, HttpCase


@tagged('post_install', '-at_install')
class TestWorkgroupTour(HttpCase):

    def test_workgroup_crud_tour(self):
        # To observe this tour in a real browser during development:
        #   self.start_tour("/odoo", "ems_workgroup_crud", login="admin", watch=True)
        self.start_tour("/odoo", "ems_workgroup_crud", login="admin")
