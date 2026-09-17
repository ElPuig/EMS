# -*- coding: utf-8 -*-

import logging
from datetime import datetime, time, timedelta, timezone

import pytz

from odoo import api, models, fields, _

_logger = logging.getLogger(__name__)


class ems_attendance(models.Model):
    _inherit = 'hr.attendance'
    _description = 'HR Attendance: auto check-in/check-out extension.'

    in_mode = fields.Selection(selection_add=[('auto_check_in', 'Automatic Check-In')])

    @api.model_create_multi
    def create(self, vals_list):
        """Before opening a new check-in, try to auto-close any stale open
        attendance the employee already has (e.g. the nightly cron missed a
        run). Only closes attendances whose scheduled check-out has already
        passed, so a genuinely ongoing session from today is never touched."""
        for vals in vals_list:
            employee_id = vals.get('employee_id')
            if not employee_id or vals.get('check_out'):
                continue

            open_attendance = self.sudo().search(
                [('employee_id', '=', employee_id)] + self._get_stale_attendance_domain(),
                limit=1,
            )
            if open_attendance:
                open_attendance._close_stale_attendance_safely()

        return super().create(vals_list)

    @api.model
    def _get_stale_attendance_domain(self):
        """Shared eligibility criteria for an open attendance this model is
        allowed to auto-close - used by both create()'s per-employee lookup and
        the cron's company-wide one."""
        return [
            ('check_out', '=', False),
            ('employee_id.company_id.auto_check_out', '=', True),
            ('employee_id.resource_calendar_id.flexible_hours', '=', False),
        ]

    def _close_stale_attendance_safely(self):
        """Shared by create()'s check-in-triggered backup and the nightly cron:
        isolate a close failure in its own savepoint (so it can't poison the rest
        of the caller's transaction/batch) and notify the Academic Admins instead
        of letting it propagate uncontrolled or fail silently."""
        self.ensure_one()
        try:
            with self.env.cr.savepoint():
                self._auto_close_attendance()
        except Exception:
            _logger.exception(
                "EMS auto-checkout: unexpected error processing attendance id=%d "
                "for employee %s — skipping.",
                self.id, self.employee_id.name,
            )
            try:
                self._notify_close_failure()
            except Exception:
                _logger.exception(
                    "EMS auto-checkout: could not notify about the failure above "
                    "for attendance id=%d.", self.id,
                )

    def _auto_close_attendance(self):
        """Close this open attendance using the last scheduled working hour
        for its check-in date (with a check_in+1h fallback), regardless of
        the current time of day. Returns True if it was closed, False if it
        could not be (no schedule for that day, or the scheduled check-out
        hasn't happened yet)."""
        self.ensure_one()
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        work_date = self.check_in.date()
        check_out = self._get_last_working_hour(self.employee_id, work_date)

        if check_out is None:
            _logger.warning(
                "EMS auto-checkout: employee %s (id=%d) has no working schedule "
                "for %s — skipping.",
                self.employee_id.name, self.employee_id.id, work_date,
            )
            return False

        if check_out > now:
            return False

        fallback = check_out <= self.check_in
        if fallback:
            check_out = self.check_in + timedelta(hours=1)
            _logger.warning(
                "EMS auto-checkout: computed check_out was before check_in for employee %s "
                "(attendance id=%d) — using check_in + 1h fallback (%s).",
                self.employee_id.name, self.id, check_out,
            )
            if check_out > now:
                return False

        self.sudo().write({
            'check_out': check_out,
            'out_mode': 'auto_check_out',
        })

        if fallback:
            partners = (
                self.employee_id.user_id.partner_id
                | self.employee_id.parent_id.user_id.partner_id
            )
            self.message_post(
                body=_(
                    'Automatic check-out could not use the scheduled working hours '
                    'because the check-in time (%s) is after the last scheduled hour. '
                    'The check-out has been set to one hour after check-in (%s). '
                    'Please review and correct the actual check-out time.'
                ) % (
                    self._format_local_for_employee(self.employee_id, self.check_in),
                    self._format_local_for_employee(self.employee_id, check_out),
                ),
                partner_ids=partners.ids,
            )
        else:
            self.message_post(
                body=_('This attendance was automatically checked out at the end of the scheduled working hours.')
            )

        _logger.info(
            "EMS auto-checkout: employee %s checked out at %s (attendance id=%d).",
            self.employee_id.name, check_out, self.id,
        )
        return True

    def _get_day_start_and_day(self, employee, dt):
        """Odoo core's own version leaves microseconds untouched, so a check_in
        stamped via datetime.now() (has microseconds) and a check_out set to a
        'clean' value (none) on the same calendar day produce two distinct
        day-start instants for the exact same date. hr.attendance.overtime's
        create() then self-collides against its own UNIQUE(employee_id, date)
        index trying to insert both in the same statement. Normalizing here fixes
        it at the single source create()/write()/both crons all go through."""
        day_start, day = super()._get_day_start_and_day(employee, dt)
        return day_start.replace(microsecond=0), day

    def _format_local_for_employee(self, employee, dt):
        """Format a naive-UTC datetime (Odoo ORM's own storage convention) in the
        employee's own timezone, for a message the employee (or their manager) will
        actually read - e.g. the fallback notification below. Interpolating the raw
        naive-UTC value directly (str(dt)/%s) silently shows server time instead of
        the reader's own time: unlike the backend list/form views, message_post()'s
        body is plain text, so no client-side tz conversion ever applies to it.
        Found 2026-09-17: a forced check-out email showed times 2h behind what the
        same record's backend view showed for the same reader (UTC vs. Europe/Madrid
        CEST). Resolves the employee's own tz the same way '_get_last_working_hour'
        already does, rather than 'ems.datetime_utils.current_tz()' - that one
        resolves the *acting user's* (or company's) tz, which is right for its own
        callers but not for a message addressed to this specific employee."""
        employee_tz = pytz.timezone(employee._get_tz())
        return pytz.utc.localize(dt).astimezone(employee_tz).strftime('%Y-%m-%d %H:%M:%S')

    def _get_last_working_hour(self, employee, work_date):
        """End of the last stretch the employee was actually expected to work on work_date, as
        a naive UTC datetime, or None when nothing was expected of them at all.

        Asks the calendar what was expected rather than reading its raw weekly 'attendance_ids':
        an approved absence becomes a 'resource.calendar.leaves' row on that same calendar (see
        docs/en/developers/employees/absence.md), and Odoo's own '_get_expected_attendances'
        already subtracts those - it calls '_work_intervals_batch' with compute_leaves=True.
        Reading the untouched timetable instead closed the attendance at the end of a day the
        employee had permission to miss part of, crediting them hours they were on approved
        leave for. Only an approved absence counts: a request still awaiting its approver never
        becomes a resource leave, so it correctly changes nothing here.

        None means the same thing to the caller in both of the cases that produce it - the
        employee never works that weekday, or an absence covers the whole of it: either way
        there is no scheduled hour to close at, and leaving the attendance open for a human to
        correct is more honest than closing it at an invented time.
        """
        if not employee.resource_calendar_id:
            return None

        employee_tz = pytz.timezone(employee._get_tz())
        day_start = employee_tz.localize(datetime.combine(work_date, time.min))
        day_end = employee_tz.localize(datetime.combine(work_date, time.max))
        expected = employee._get_expected_attendances(day_start, day_end)
        if not expected:
            return None

        last_end = max(interval_end for _interval_start, interval_end, *_rest in expected)
        return last_end.astimezone(pytz.utc).replace(tzinfo=None)

    def _cron_auto_check_out(self):
        """Delegates to native Odoo or EMS checkout logic based on company's auto_checkout_mode."""

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

        open_attendances = self.sudo().search(self._get_stale_attendance_domain())

        if not open_attendances:
            _logger.info("EMS auto-checkout: no open attendances to process.")
            return

        _logger.info("EMS auto-checkout: processing %d open attendance(s).", len(open_attendances))

        for attendance in open_attendances:
            attendance._close_stale_attendance_safely()

    def _notify_close_failure(self):
        """A close failing silently is exactly how this went unnoticed for days
        (issue #422) - schedule an activity for the Academic Admins so a
        stuck-open attendance surfaces immediately instead of only in the server log.
        Scheduled on employee_id, not on self: hr.attendance only inherits
        mail.thread (no mail.activity.mixin), while hr.employee already does -
        also a more natural place for "this employee's attendance data needs
        review" than the attendance record itself. Uses activity_schedule()
        (same pattern as ems.attendance_correction._find_approver's callers)
        rather than a plain message_post(partner_ids=...): a chatter note whose
        only recipients are non-followers wasn't kept once its associated
        outgoing-email attempt got cleaned up, in testing.

        Known, accepted gap (2026-09, verified empirically, not chased further):
        when this runs nested inside the very create() call that goes on to
        raise its own native "already checked in" validation right after (i.e.
        this is the *employee's own* check-in attempt, not the cron), the
        scheduled activity is not reliably kept either - something in that
        specific combination (notify, then a same-call ORM failure) discards it,
        even though the failure itself stays correctly isolated (the stale
        attendance is never wrongly left half-closed, and the new check-in is
        still correctly blocked). Calling this from a separate, already-returned
        call (the cron's own loop, one call per record) is unaffected. Low
        impact either way: the same stuck attendance gets picked up by the next
        cron run or the employee's next real check-in regardless."""
        self.ensure_one()
        admins = self.env['res.users'].sudo().search([
            ('groups_id', '=', self.env.ref('ems.group_academic_admin').id),
        ])
        for admin in admins:
            self.employee_id.sudo().activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=admin.id,
                summary=_('Automatic check-out failed'),
                note=_(
                    'Automatic check-out failed for %(employee)s\'s attendance (id=%(id)d) '
                    'due to an unexpected error. Please review and close it manually.'
                ) % {'employee': self.employee_id.display_name, 'id': self.id},
            )
