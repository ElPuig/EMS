# -*- coding: utf-8 -*-

from datetime import datetime, time

import pytz

from odoo import models


class EmsEmployeeWorkday(models.Model):
    """What an employee is expected to work on a given day. Shared by the automatic check-out
    (hr.attendance, employee_autocheckout.py) and the daily pending-tasks digest (res.users,
    models/shared/task_digest.py)."""
    _inherit = 'hr.employee'

    def _ems_local_day_bounds(self, work_date):
        """Start and end of 'work_date' in the employee's own timezone, tz-aware."""
        self.ensure_one()
        employee_tz = pytz.timezone(self._get_tz())
        return (
            employee_tz.localize(datetime.combine(work_date, time.min)),
            employee_tz.localize(datetime.combine(work_date, time.max)),
        )

    def _ems_expected_intervals(self, work_date):
        """(start, end) pairs, tz-aware, of every stretch the employee is expected to work on
        work_date - approved absences and public holidays already subtracted: Odoo's own
        '_get_expected_attendances' asks the calendar with compute_leaves=True (see
        hr.attendance._get_closing_hour() for why the raw 'attendance_ids' are not enough).
        Empty for an employee with no working schedule at all."""
        self.ensure_one()
        if not self.resource_calendar_id:
            return []
        day_start, day_end = self._ems_local_day_bounds(work_date)
        return [(start, end) for start, end, *_rest in self._get_expected_attendances(day_start, day_end)]

    def _ems_framework_intervals(self, framework, work_date):
        """(start, end) pairs, tz-aware, of 'framework''s periods on work_date, in the employee's
        own timezone. Deliberately without subtracting any absence: the automatic check-out only
        uses it for a day nothing was expected of the employee, so there is nothing left to
        subtract from."""
        self.ensure_one()
        if not framework:
            return []
        day_start, day_end = self._ems_local_day_bounds(work_date)
        resource = self.resource_id
        attendances = framework._attendance_intervals_batch(
            day_start, day_end, resource, tz=day_start.tzinfo)[resource.id]
        return [(start, end) for start, end, *_rest in attendances]
