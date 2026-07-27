from odoo.tests import tagged, HttpCase


@tagged('post_install', '-at_install')
class TestOutcomeTour(HttpCase):

    def test_outcome_crud_tour(self):
        # To observe this tour in a real browser during development:
        #   self.start_tour("/odoo", "ems_outcome_crud", login="admin", watch=True)
        self.start_tour("/odoo", "ems_outcome_crud", login="admin")
