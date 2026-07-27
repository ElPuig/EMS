from odoo.tests import tagged, HttpCase


@tagged('post_install', '-at_install')
class TestGroupTour(HttpCase):

    def test_group_form_tabs_and_reinforcement_crud_tour(self):
        # To observe this tour in a real browser during development:
        #   self.start_tour("/odoo", "ems_group_form_tabs_and_reinforcement_crud", login="admin", watch=True)
        self.start_tour("/odoo", "ems_group_form_tabs_and_reinforcement_crud", login="admin")
