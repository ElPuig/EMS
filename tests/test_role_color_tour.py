from odoo.tests import tagged, HttpCase

from .common import force_user_language_to_english


@tagged('post_install', '-at_install')
class TestRoleColorTour(HttpCase):

    def test_role_list_and_form_render(self):
        force_user_language_to_english(self, self.env.ref('base.user_admin'))
        # To observe this tour in a real browser during development:
        #   self.start_tour("/odoo", "ems_role_color_smoke", login="admin", watch=True)
        self.start_tour("/odoo", "ems_role_color_smoke", login="admin")

    def test_employee_role_badge_renders(self):
        force_user_language_to_english(self, self.env.ref('base.user_admin'))
        # To observe this tour in a real browser during development:
        #   self.start_tour("/odoo", "ems_employee_role_badge_smoke", login="admin", watch=True)
        self.start_tour("/odoo", "ems_employee_role_badge_smoke", login="admin")

    def test_role_hierarchy_lock_renders(self):
        force_user_language_to_english(self, self.env.ref('base.user_admin'))
        # To observe this tour in a real browser during development:
        #   self.start_tour("/odoo", "ems_role_hierarchy_lock_smoke", login="admin", watch=True)
        self.start_tour("/odoo", "ems_role_hierarchy_lock_smoke", login="admin")
