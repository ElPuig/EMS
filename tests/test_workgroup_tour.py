from odoo.tests import tagged, HttpCase

from .common import force_user_language_to_english


@tagged('post_install', '-at_install')
class TestWorkgroupTour(HttpCase):

    def test_workgroup_crud_tour(self):
        force_user_language_to_english(self, self.env.ref('base.user_admin'))
        # To observe this tour in a real browser during development:
        #   self.start_tour("/odoo", "ems_workgroup_crud", login="admin", watch=True)
        self.start_tour("/odoo", "ems_workgroup_crud", login="admin")
