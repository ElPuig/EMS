from odoo.tests import tagged, HttpCase


@tagged('post_install', '-at_install')
class TestTeachingTour(HttpCase):

    def test_teaching_form_renders_tour(self):
        # To observe this tour in a real browser during development:
        #   self.start_tour("/odoo", "ems_teaching_form_renders", login="admin", watch=True)
        self.start_tour("/odoo", "ems_teaching_form_renders", login="admin")
