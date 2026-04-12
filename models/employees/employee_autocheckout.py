# -*- coding: utf-8 -*-

import logging
from datetime import datetime, timezone

from odoo import models, _

_logger = logging.getLogger(__name__)


class ems_attendance(models.Model):
    _inherit = 'hr.attendance'
    _description = 'HR Attendance: auto check-out extension.'

    def _get_last_working_hour(self, employee, work_date):
        """Return the last hour_to (as naive UTC datetime) for the employee on work_date.
        Returns None if the employee has no working schedule for that day."""
        if not employee.resource_calendar_id:
            return None

        weekday = str(work_date.weekday())  # '0'=Monday … '6'=Sunday
        slots = employee.resource_calendar_id.attendance_ids.filtered(
            lambda a: a.dayofweek == weekday
        ).sorted(key=lambda a: a.hour_to, reverse=True)

        if not slots:
            return None

        utils = self.env['ems.datetime_utils']
        return utils.datetime_to_odoo(utils.time_float_to_utc_datetime(work_date, slots[0].hour_to))

    def _cron_auto_check_out(self):
        """Override of Odoo's native auto check-out cron.
        Delegates to the native behaviour or to the EMS behaviour depending on the
        company setting 'auto_checkout_mode':
          - 'native': original Odoo logic (check-out after exceeding max scheduled hours).
          - 'ems':    EMS logic (check-out at the employee's last scheduled working hour)."""

        if self.env.company.auto_checkout_mode != 'ems':
            return super()._cron_auto_check_out()

        now = datetime.now(timezone.utc).replace(tzinfo=None)

        open_attendances = self.sudo().search([
            ('check_out', '=', False),
            ('check_in', '<', now),
            ('employee_id.company_id.auto_check_out', '=', True),
            ('employee_id.resource_calendar_id.flexible_hours', '=', False),
        ])

        if not open_attendances:
            _logger.info("EMS auto-checkout: no open attendances to process.")
            return

        _logger.info("EMS auto-checkout: processing %d open attendance(s).", len(open_attendances))

        for attendance in open_attendances:
            try:
                work_date = attendance.check_in.date()
                check_out = self._get_last_working_hour(attendance.employee_id, work_date)

                if check_out is None:
                    _logger.warning(
                        "EMS auto-checkout: employee %s (id=%d) has no working schedule "
                        "for %s — skipping.",
                        attendance.employee_id.name, attendance.employee_id.id, work_date,
                    )
                    continue

                # Only close if the expected check_out has already passed
                if check_out > now:
                    continue

                # Sanity check: check_out must be after check_in
                if check_out <= attendance.check_in:
                    _logger.warning(
                        "EMS auto-checkout: computed check_out (%s) is not after check_in "
                        "(%s) for employee %s (attendance id=%d) — skipping.",
                        check_out, attendance.check_in,
                        attendance.employee_id.name, attendance.id,
                    )
                    continue

                attendance.sudo().write({
                    'check_out': check_out,
                    'out_mode': 'auto_check_out',
                })
                attendance.message_post(
                    body=_('This attendance was automatically checked out at the end of the scheduled working hours.')
                )
                _logger.info(
                    "EMS auto-checkout: employee %s checked out at %s (attendance id=%d).",
                    attendance.employee_id.name, check_out, attendance.id,
                )

            except Exception:
                _logger.exception(
                    "EMS auto-checkout: unexpected error processing attendance id=%d "
                    "for employee %s — skipping.",
                    attendance.id, attendance.employee_id.name,
                )
