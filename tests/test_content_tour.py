from odoo.tests import tagged, HttpCase


@tagged('post_install', '-at_install')
class TestContentTour(HttpCase):

    def test_content_crud_tour(self):
        # To observe this tour in a real browser during development:
        #   self.start_tour("/odoo", "ems_content_crud", login="admin", watch=True)
        self.start_tour("/odoo", "ems_content_crud", login="admin")
