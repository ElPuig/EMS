from odoo.tests import tagged, HttpCase

from .common import force_user_language_to_english


@tagged('post_install', '-at_install')
class TestContentTour(HttpCase):

    def test_content_crud_tour(self):
        force_user_language_to_english(self, self.env.ref('base.user_admin'))
        # To observe this tour in a real browser during development:
        #   self.start_tour("/odoo", "ems_content_crud", login="admin", watch=True)
        # step_delay: opens/closes a popup layer with "Add a line"/tab clicks, the same
        # shape that proved flaky under full-suite load in criteria_tour (its sibling) —
        # see test_criteria_tour.py and test_withdrawal_tour.py for the same fix applied
        # for the same reason.
        self.start_tour("/odoo", "ems_content_crud", login="admin", step_delay=300)
