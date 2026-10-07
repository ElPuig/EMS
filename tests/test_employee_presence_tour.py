from datetime import timedelta

from odoo import fields
from odoo.tests import HttpCase, tagged

from odoo.addons.ems import _disable_login_presence_control

from .common import create_role_employee, create_role_user, mock_outgoing_email


@tagged('post_install', '-at_install')
class TestEmployeePresenceTour(HttpCase):
    """The presence dot looks the same on the Teachers kanban and on the form, for a plain teacher, in
    every colour (issue #575) - see ems_employee_base's hr_presence_state."""

    def _colleague(self, name, working_now):
        employee = create_role_employee(self, create_role_user(self, 'teacher', name.lower().replace(' ', '_')), name=name)
        # A slot covering the whole of today's weekday makes them "should be working now" at any
        # hour the test runs; none at all leaves them out of working hours.
        weekday = str(self.env['ems.datetime_utils'].get_local_today().weekday())
        employee.resource_calendar_id = self.env['resource.calendar'].create({
            'name': f'{name} Schedule',
            'attendance_ids': [(0, 0, {'name': 'All day', 'dayofweek': weekday, 'hour_from': 0.0, 'hour_to': 23.99})]
            if working_now else [(5, 0, 0)],
        })
        return employee

    def test_employee_presence_tour(self):
        mock_outgoing_email(self)
        self.env.company.hr_presence_control_attendance = True
        _disable_login_presence_control(self.env)
        present = self._colleague('0000 Presence Green', working_now=True)
        self.env['hr.attendance'].create({'employee_id': present.id, 'check_in': fields.Datetime.now() - timedelta(minutes=30)})
        self._colleague('0000 Presence Yellow', working_now=True)
        self._colleague('0000 Presence Grey', working_now=False)
        on_leave = self._colleague('0000 Presence Plane', working_now=True)
        today = self.env['ems.datetime_utils'].get_local_today()
        self.env['hr.leave'].create({
            'employee_id': on_leave.id, 'holiday_status_id': self.env.ref('ems.leave_type_justified').id,
            'request_date_from': today, 'request_date_to': today, 'ems_full_day': True,
            'ems_submitted': True, 'ems_responsible_declaration': True,
        }).action_approve()
        # The least-privileged role that sees the Teachers screen: a plain teacher, no HR rights.
        create_role_user(self, 'teacher', 'presence_tour_teacher')

        self.start_tour("/odoo", "ems_employee_presence", login="presence_tour_teacher")
