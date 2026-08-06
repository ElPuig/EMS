from odoo.tests import tagged, HttpCase


@tagged('post_install', '-at_install')
class TestEmployeeArchivedReasonTour(HttpCase):

    def test_employee_archived_reason_indicator_tour(self):
        # "0000 " prefix: hr.employee's default _order is "name", same convention as
        # TestEmployeeGoogleWorkspaceTour._seed_teacher.
        teacher = self.env['hr.employee'].create({
            'name': '0000 Tour Retired Teacher',
            'employee_type': 'teacher',
            'departure_reason_id': self.env.ref('hr.departure_retired').id,
            'active': False,
        })
        # A real entry on the (still-active, per phase 6/7 of
        # plans/course_transition_teacher_schedule_archival.md - only a course transition rolls a
        # calendar, not an employee leaving mid-course) calendar this now-archived employee last
        # had - so the tour has something concrete to confirm the Schedule tab's grid widget still
        # renders (phase 8 of the same plan: "confirm/fix the Schedule-tab grid renders a read-only
        # view of an archived calendar" - the only real path to that is an archived EMPLOYEE whose
        # calendar was never rolled over, since the widget only ever shows the CURRENT calendar).
        self.env['resource.calendar.attendance'].create({
            'calendar_id': teacher.resource_calendar_id.id,
            'name': 'Tour Retired Teacher Guard Duty',
            'dayofweek': '0', 'hour_from': 8.0, 'hour_to': 9.0, 'day_period': 'morning',
            'non_teaching': self.env.ref('ems.non_teaching_g').id,
        })
        self.start_tour("/odoo", "ems_employee_archived_reason_indicator", login="admin")
