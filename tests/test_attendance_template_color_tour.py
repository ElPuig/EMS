from odoo.tests import tagged, HttpCase


@tagged('post_install', '-at_install')
class TestAttendanceTemplateColorTour(HttpCase):

    def test_attendance_template_list_and_form_render(self):
        # To observe this tour in a real browser during development:
        #   self.start_tour("/odoo", "ems_attendance_template_color_smoke", login="admin", watch=True)
        self.start_tour("/odoo", "ems_attendance_template_color_smoke", login="admin")
