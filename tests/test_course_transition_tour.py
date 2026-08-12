from odoo.tests import tagged, HttpCase


@tagged('post_install', '-at_install')
class TestCourseTransitionTour(HttpCase):

    def test_course_transition_preview_tour(self):
        # The tour stops at the preview on purpose: the apply deletes the operational
        # records of the outgoing course and cannot be undone. It is covered by the
        # TransactionCase tests of tests/test_course_transition.py, which roll back.
        # To observe this tour in a real browser during development:
        #   self.start_tour("/odoo", "course_transition_preview_tour", login="admin", watch=True)
        self.start_tour("/odoo", "course_transition_preview_tour", login="admin")
