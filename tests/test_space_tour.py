from odoo.tests import tagged, HttpCase

from .common import force_user_language_to_english


@tagged('post_install', '-at_install')
class TestSpaceTour(HttpCase):

    def test_space_crud_tour(self):
        force_user_language_to_english(self, self.env.ref('base.user_admin'))
        # To observe this tour in a real browser during development:
        #   self.start_tour("/odoo", "ems_space_crud", login="admin", watch=True)
        self.start_tour("/odoo", "ems_space_crud", login="admin")
