from odoo.tests.common import HttpCase, tagged

from .test_ampa_membership import AmpaMembershipFixtures


@tagged('post_install', '-at_install')
class TestAmpaMembershipTour(AmpaMembershipFixtures, HttpCase):
    """Issue #820, in a real browser as the tutor: the AMPA column and filters of the Students
    list (kanban and list modes) and the badge of the student form."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_ampa_fixtures()

    def test_ampa_membership_tour(self):
        self.start_tour("/odoo", "ems_ampa_membership", login=self.tutor.login)
