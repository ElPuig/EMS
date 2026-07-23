from odoo.tests import tagged, HttpCase


@tagged('post_install', '-at_install')
class TestDepartmentColorTour(HttpCase):

    def test_department_list_and_form_render(self):
        # To observe this tour in a real browser during development:
        #   self.start_tour("/odoo", "ems_department_color_smoke", login="admin", watch=True)
        self.start_tour("/odoo", "ems_department_color_smoke", login="admin")

    def test_department_kanban_render(self):
        # To observe this tour in a real browser during development:
        #   self.start_tour("/odoo", "ems_department_kanban_color_smoke", login="admin", watch=True)
        self.start_tour("/odoo", "ems_department_kanban_color_smoke", login="admin")
