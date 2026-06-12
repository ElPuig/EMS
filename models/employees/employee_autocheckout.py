# -*- coding: utf-8 -*-

import logging
from datetime import datetime, timedelta, timezone

from odoo import models, fields, _

_logger = logging.getLogger(__name__)


class ems_attendance(models.Model):
    _inherit = 'hr.attendance'
    _description = 'HR Attendance: auto check-in/check-out extension.'

    in_mode = fields.Selection(selection_add=[('auto_check_in', 'Automatic Check-In')])

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
          - 'ems':    EMS logic (check-out at the employee's last scheduled working hour,
                      with hourly retries between auto_checkout_time and auto_checkout_retry_until)."""

        if self.env.company.auto_checkout_mode != 'ems':
            return super()._cron_auto_check_out()

        # Only run within the configured retry window (e.g. 01:00–06:00 local time)
        utils = self.env['ems.datetime_utils']
        now_local = utils.get_local_datetime()
        now_float = utils.time_to_float(now_local.time())
        start = self.env.company.auto_checkout_time
        end   = self.env.company.auto_checkout_retry_until

        # Window may cross midnight (e.g. 23:00 → 04:00)
        if start <= end:
            in_window = start <= now_float < end
        else:
            in_window = now_float >= start or now_float < end

        if not in_window:
            _logger.info(
                "EMS auto-checkout: outside retry window (%.2f–%.2f), skipping.",
                start, end,
            )
            return

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

                # If the employee checked in after their last scheduled hour, the computed
                # check_out would be before check_in (invalid). Fall back to check_in + 1h
                # and notify for manual correction.
                fallback = check_out <= attendance.check_in
                if fallback:
                    check_out = attendance.check_in + timedelta(hours=1)
                    _logger.warning(
                        "EMS auto-checkout: computed check_out was before check_in for employee %s "
                        "(attendance id=%d) — using check_in + 1h fallback (%s).",
                        attendance.employee_id.name, attendance.id, check_out,
                    )
                    if check_out > now:
                        continue

                attendance.sudo().write({
                    'check_out': check_out,
                    'out_mode': 'auto_check_out',
                })

                if fallback:
                    partners = (
                        attendance.employee_id.user_id.partner_id
                        | attendance.employee_id.parent_id.user_id.partner_id
                    )
                    attendance.message_post(
                        body=_(
                            'Automatic check-out could not use the scheduled working hours '
                            'because the check-in time (%s) is after the last scheduled hour. '
                            'The check-out has been set to one hour after check-in (%s). '
                            'Please review and correct the actual check-out time.'
                        ) % (attendance.check_in, check_out),
                        partner_ids=partners.ids,
                    )
                else:
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
