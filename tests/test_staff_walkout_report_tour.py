# -*- coding: utf-8 -*-

from odoo.tests import tagged
from odoo.tests.common import HttpCase

from .common import create_role_user, make_working_day, mock_outgoing_email, shift_ems_clock


@tagged('post_install', '-at_install')
class TestStaffWalkoutReportTour(HttpCase):
    """Issue #813: the walkout report as the Director, the only role it is for: the day's dialog,
    the pivot and the list behind it."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        # 10:00 of a school day: the fixture's 8:00 period has started.
        today = shift_ems_clock(cls, hour=10.0, weekdays=(0, 1, 2, 3, 4)).date()
        make_working_day(cls, today)
        cls.director = create_role_user(cls, 'director', 'staff_walkout_tour_director')
        walker = cls.env['hr.employee'].create({'name': '0000 TSSR Tour Walker', 'employee_type': 'teacher'})
        walker.resource_calendar_id = cls.env['resource.calendar'].create({
            'name': walker.name, 'employee_id': walker.id,
            'attendance_ids': [(5, 0, 0), (0, 0, {
                'name': 'TSSR Tour', 'dayofweek': str(today.weekday()), 'hour_from': 8.0, 'hour_to': 9.0})],
        })

    def test_staff_walkout_report_tour(self):
        self.start_tour("/odoo", "ems_staff_walkout_report", login=self.director.login)
