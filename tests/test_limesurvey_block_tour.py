from odoo.tests import tagged, HttpCase


@tagged('post_install', '-at_install')
class TestLimesurveyBlockTour(HttpCase):

    def test_limesurvey_block_special_type_tour(self):
        # To observe this tour in a real browser during development:
        #   self.start_tour("/odoo", "ems_limesurvey_block_special_type", login="admin", watch=True)
        self.start_tour("/odoo", "ems_limesurvey_block_special_type", login="admin")
