from odoo.tests import tagged, HttpCase


@tagged('post_install', '-at_install')
class TestEmployeeTour(HttpCase):

    def test_employee_form_tabs_tour(self):
        self.env['hr.employee'].create({
            'name': 'Employee Form Tour',
            'employee_type': 'teacher',
        })
        # To observe this tour in a real browser during development:
        #   self.start_tour("/odoo", "ems_employee_form_tabs", login="admin", watch=True)
        self.start_tour("/odoo", "ems_employee_form_tabs", login="admin")
