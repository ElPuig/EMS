from odoo.tests import tagged, HttpCase

from .common import create_role_user


@tagged('post_install', '-at_install')
class TestGradeSessionTour(HttpCase):

    def test_grade_session_ui_tour(self):
        # To observe this tour in a real browser during development:
        #   self.start_tour("/odoo", "ems_grade_session_ui", login="admin", watch=True)
        # The Head of Studies creates the sessions (issue #878), the least-privileged role allowed.
        create_role_user(self, 'head_of_studies', 'tour_hos_grade_session')
        self.start_tour("/odoo", "ems_grade_session_ui", login="tour_hos_grade_session")
