from odoo.tests import tagged, HttpCase


@tagged('post_install', '-at_install')
class TestNonTeachingTypeTour(HttpCase):

    def test_non_teaching_type_crud_tour(self):
        # To observe this tour in a real browser during development:
        #   self.start_tour("/odoo", "ems_non_teaching_type_crud", login="admin", watch=True)
        self.start_tour("/odoo", "ems_non_teaching_type_crud", login="admin")
