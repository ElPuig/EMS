from odoo.tests.common import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestWorkingScheduleStaleBreaksTour(HttpCase):
    """Schedule tab widget bug (found 2026-08-11 while verifying the derived-break weekly-span
    redesign): 'derivedBreaks'/'summary' (schedule_grid_field.js) were only ever loaded in
    'onWillStart' - a mount-only hook - so navigating from one teacher's form to a DIFFERENT one
    via the pager (Odoo's form view reuses the same widget component instance, no remount) left
    the PREVIOUSLY viewed teacher's own derived break still showing on the newly navigated-to
    one, until an actual full page reload. Fixed by switching to 'useRecordObserver', which
    reloads on every record change, not just on mount. Exercises the real interactive pager flow
    - a clean upgrade.sh and passing TransactionCase tests prove none of this on their own, since
    neither renders anything in a real browser, let alone simulates staying mounted across a
    record change."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.non_teaching_br = cls.env.ref('ems.non_teaching_br')
        cls.non_teaching_g = cls.env.ref('ems.non_teaching_g')
        cls.framework = cls.env['resource.calendar'].create({
            'name': 'Test Framework (Stale Breaks Tour)', 'is_framework': True, 'full_time_required_hours': 24,
        })
        cls.env['resource.calendar.attendance'].create({
            'calendar_id': cls.framework.id, 'name': 'BR: Break', 'dayofweek': '0',
            'hour_from': 9, 'hour_to': 9.25, 'day_period': 'morning', 'non_teaching': cls.non_teaching_br.id,
        })
        cls.env['resource.calendar.attendance'].create({
            'calendar_id': cls.framework.id, 'name': 'BR: Break', 'dayofweek': '0',
            'hour_from': 16, 'hour_to': 16.25, 'day_period': 'afternoon', 'non_teaching': cls.non_teaching_br.id,
        })

        cls.teacher_a = cls.env['hr.employee'].create({'name': 'Stale Breaks Tour Teacher A', 'employee_type': 'teacher'})
        schedule_a = cls.env['resource.calendar'].create({'name': 'Test Schedule A (Stale Breaks Tour)'})
        cls.teacher_a.resource_calendar_id = schedule_a
        # Afternoon only, with a gap exactly matching the framework's own afternoon break.
        schedule_a.apply_schedule_changes([
            {'dayofweek': '0', 'hour_from': 15, 'hour_to': 16, 'day_period': 'afternoon',
             'non_teaching': cls.non_teaching_g.id, 'name': 'Guard'},
            {'dayofweek': '0', 'hour_from': 16.25, 'hour_to': 17, 'day_period': 'afternoon',
             'non_teaching': cls.non_teaching_g.id, 'name': 'Guard'},
        ])

        cls.teacher_b = cls.env['hr.employee'].create({'name': 'Stale Breaks Tour Teacher B', 'employee_type': 'teacher'})
        schedule_b = cls.env['resource.calendar'].create({'name': 'Test Schedule B (Stale Breaks Tour)'})
        cls.teacher_b.resource_calendar_id = schedule_b
        # Morning only, with a gap exactly matching the framework's own morning break.
        schedule_b.apply_schedule_changes([
            {'dayofweek': '0', 'hour_from': 8.75, 'hour_to': 9, 'day_period': 'morning',
             'non_teaching': cls.non_teaching_g.id, 'name': 'Guard'},
            {'dayofweek': '0', 'hour_from': 9.25, 'hour_to': 10, 'day_period': 'morning',
             'non_teaching': cls.non_teaching_g.id, 'name': 'Guard'},
        ])

    def test_working_schedule_stale_breaks_tour(self):
        # To observe this tour in a real browser during development:
        #   self.start_tour("/odoo", "ems_working_schedule_stale_breaks", login="admin", watch=True)
        self.start_tour("/odoo", "ems_working_schedule_stale_breaks", login="admin")
