from odoo.tests import tagged, HttpCase


@tagged('post_install', '-at_install')
class TestGradeSessionTour(HttpCase):

    def test_grade_session_ui_tour(self):
        # To observe this tour in a real browser during development:
        #   self.start_tour("/odoo", "ems_grade_session_ui", login="admin", watch=True)
        self.start_tour("/odoo", "ems_grade_session_ui", login="admin")
