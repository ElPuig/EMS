from odoo.tests import tagged, HttpCase


@tagged('post_install', '-at_install')
class TestEmployeeArchivedReasonTour(HttpCase):

    def test_employee_archived_reason_indicator_tour(self):
        # "0000 " prefix: hr.employee's default _order is "name", same convention as
        # TestEmployeeGoogleWorkspaceTour._seed_teacher.
        self.env['hr.employee'].create({
            'name': '0000 Tour Retired Teacher',
            'employee_type': 'teacher',
            'departure_reason_id': self.env.ref('hr.departure_retired').id,
            'active': False,
        })
        self.start_tour("/odoo", "ems_employee_archived_reason_indicator", login="admin")
