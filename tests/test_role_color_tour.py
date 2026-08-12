from odoo.tests import tagged, HttpCase


@tagged('post_install', '-at_install')
class TestRoleColorTour(HttpCase):

    def test_role_list_and_form_render(self):
        # To observe this tour in a real browser during development:
        #   self.start_tour("/odoo", "ems_role_color_smoke", login="admin", watch=True)
        self.start_tour("/odoo", "ems_role_color_smoke", login="admin")

    def test_employee_role_badge_renders(self):
        # To observe this tour in a real browser during development:
        #   self.start_tour("/odoo", "ems_employee_role_badge_smoke", login="admin", watch=True)
        self.start_tour("/odoo", "ems_employee_role_badge_smoke", login="admin")
