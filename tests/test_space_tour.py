from odoo.tests import tagged, HttpCase


@tagged('post_install', '-at_install')
class TestSpaceTour(HttpCase):

    def test_space_crud_tour(self):
        # To observe this tour in a real browser during development:
        #   self.start_tour("/odoo", "ems_space_crud", login="admin", watch=True)
        self.start_tour("/odoo", "ems_space_crud", login="admin")
