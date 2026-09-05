from odoo.tests import tagged, HttpCase

from .common import force_user_language_to_english


@tagged('post_install', '-at_install')
class TestCriteriaTour(HttpCase):

    def test_criteria_crud_tour(self):
        force_user_language_to_english(self, self.env.ref('base.user_admin'))
        # To observe this tour in a real browser during development:
        #   self.start_tour("/odoo", "ems_criteria_crud", login="admin", watch=True)
        # step_delay: this tour opens/closes three stacked popup layers (subject -> outcome
        # -> criteria) with several "Add a line"/tab-switch clicks in between — confirmed
        # flaky under full-suite load (intermittent TIMEOUTs on different steps in
        # different runs, absent in isolated runs), the same category of issue fixed the
        # same way in test_withdrawal_tour.py: give the DOM more time to settle between
        # steps rather than trusting each click to land immediately.
        self.start_tour("/odoo", "ems_criteria_crud", login="admin", step_delay=300)
