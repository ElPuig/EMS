from odoo.tests import tagged, HttpCase


@tagged('post_install', '-at_install')
class TestSubjectTour(HttpCase):

    def test_subject_crud_tour(self):
        # To observe this tour in a real browser during development:
        #   self.start_tour("/odoo", "ems_subject_crud", login="admin", watch=True)
        self.start_tour("/odoo", "ems_subject_crud", login="admin")
