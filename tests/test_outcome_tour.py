from odoo.tests import tagged, HttpCase


@tagged('post_install', '-at_install')
class TestOutcomeTour(HttpCase):

    def test_outcome_crud_tour(self):
        # To observe this tour in a real browser during development:
        #   self.start_tour("/odoo", "ems_outcome_crud", login="admin", watch=True)
        # step_delay: opens/closes a popup layer with "Add a line"/tab clicks, the same
        # shape that proved flaky under full-suite load in criteria_tour (its sibling,
        # nested one level deeper) — see test_criteria_tour.py and test_withdrawal_tour.py
        # for the same fix applied for the same reason.
        self.start_tour("/odoo", "ems_outcome_crud", login="admin", step_delay=300)
