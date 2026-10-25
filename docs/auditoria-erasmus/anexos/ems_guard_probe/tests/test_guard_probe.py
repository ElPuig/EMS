# -*- coding: utf-8 -*-
"""The fixture of TestGuardDutyBoard.test_report_guard_duty_board_marks_a_wc_guard, and what decides
the order of the guards it prints: the guards of Monday 9-10 as the board returns them (id, sequence,
teacher, WC), the same search with a final 'id' tie-break, and the 200 bytes the test reads after the
plain guard's name. Logged as GUARD_PROBE; nothing asserted."""

import json
import logging

from odoo.tests.common import tagged

from odoo.addons.ems.tests.test_guard_duty_board import GuardDutyBoardCase

_logger = logging.getLogger(__name__)


@tagged('post_install', '-at_install')
class TestGuardProbe(GuardDutyBoardCase):

    def test_probe(self):
        calendar_wc = self._new_calendar(self.teacher_guard, 'Test Calendar Guard (PDF WC)')
        calendar_wc.apply_schedule_changes([{'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
                                             'non_teaching': self.non_teaching_guard_wc.id, 'name': 'Guard (WC)'}])
        calendar_plain = self._new_calendar(self.teacher_a, 'Test Calendar A (PDF Plain Guard)')
        calendar_plain.apply_schedule_changes([{'dayofweek': '0', 'hour_from': 9, 'hour_to': 10,
                                                'day_period': 'morning', 'non_teaching': self.non_teaching_guard.id,
                                                'name': 'Guard'}])
        Attendance = self.env['resource.calendar.attendance']
        domain = [('calendar_id.is_framework', '=', False), ('calendar_id.active', '=', True),
                  ('calendar_id.employee_id', '!=', False), ('dayofweek', '=', '0'), ('hour_from', '<', 10),
                  ('hour_to', '>', 9), ('non_teaching', '!=', False)]

        def describe(records):
            return [(record.id, record.sequence, record.week_type, record.hour_from, record.calendar_id.employee_id.name,
                     bool(record.non_teaching.name and 'WC' in record.non_teaching.name)) for record in records]
        content, _type = self.env['ir.actions.report'].with_context(guard_duty_weekday='0')._render_qweb_pdf(
            'ems.report_guard_duty_board', [self.course.id])
        plain = content.find(self.teacher_a.name.encode())
        _logger.info("GUARD_PROBE %s", json.dumps({
            'search_order': describe(Attendance.search(domain)),
            'search_order_with_id': describe(Attendance.search(domain, order='sequence, week_type, dayofweek, hour_from, id')),
            'window_after_plain_guard': content[plain:plain + 200].decode(errors='replace'),
            'test_would_fail': b'(WC)' in content[plain:plain + 200],
        }, ensure_ascii=False))
