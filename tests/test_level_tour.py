from odoo.tests import tagged, HttpCase


@tagged('post_install', '-at_install')
class TestLevelTour(HttpCase):

    def test_level_crud_tour(self):
        self.start_tour("/odoo", "ems_level_crud", login="admin")
