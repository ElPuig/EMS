# -*- coding: utf-8 -*-
import logging
from datetime import timedelta

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def _find_stale_attendance_ids(cr):
    """Candidates: still open, or closed on a different calendar day than they were
    opened (both symptoms of the bug fixed in this same version - see
    'employee_autocheckout.py::_get_day_start_and_day'). Restricted to the same
    eligibility criteria the feature itself already uses, so an employee
    deliberately excluded from auto-checkout is never touched here either."""
    cr.execute("""
        SELECT a.id
          FROM hr_attendance a
          JOIN hr_employee e ON e.id = a.employee_id
          JOIN res_company c ON c.id = e.company_id
     LEFT JOIN resource_calendar rc ON rc.id = e.resource_calendar_id
         WHERE c.auto_check_out = true
           AND COALESCE(rc.flexible_hours, false) = false
           AND (a.check_out IS NULL OR a.check_in::date != a.check_out::date)
    """)
    return [row[0] for row in cr.fetchall()]


def _close_stale_attendances_same_day(env):
    """Repair for production data left behind by issue #422: attendances that stayed
    open for real, or that only got closed days later by the employee's own next
    kiosk badge-in (a different calendar day), producing nonsensical multi-day
    worked_hours (e.g. 60+ hours in one day). Per the developer (2026-09-09): force
    each one closed on the SAME calendar day it was opened, at the employee's last
    scheduled working hour that day, or 14:00 local time if no schedule is found for
    that day - "no pasa nada si hay días sin fichar, estamos en pruebas."."""
    attendance_ids = _find_stale_attendance_ids(env.cr)
    if not attendance_ids:
        _logger.info("Migration 18.0.0.24.0: no stale attendances found, nothing to do.")
        return

    _logger.info("Migration 18.0.0.24.0: closing %d stale attendance(s) same-day.", len(attendance_ids))
    utils = env['ems.datetime_utils']
    fixed, failed = 0, 0

    for attendance in env['hr.attendance'].browse(attendance_ids):
        work_date = attendance.check_in.date()
        check_out = attendance._get_last_working_hour(attendance.employee_id, work_date)
        if not check_out or check_out <= attendance.check_in:
            check_out = utils.datetime_to_odoo(utils.time_float_to_utc_datetime(work_date, 14.0))
        if check_out <= attendance.check_in:
            # 14:00 fallback still before check_in (e.g. an evening check-in) -
            # same "check_in + 1h" fallback _auto_close_attendance() itself uses.
            check_out = attendance.check_in + timedelta(hours=1)

        try:
            with env.cr.savepoint():
                attendance.write({'check_out': check_out, 'out_mode': 'auto_check_out'})
            fixed += 1
        except Exception:
            failed += 1
            _logger.exception(
                "Migration 18.0.0.24.0: could not close attendance id=%d, left as-is.",
                attendance.id,
            )

    _logger.info("Migration 18.0.0.24.0: closed %d attendance(s), %d left unfixed.", fixed, failed)


def _backfill_calendar_to_schedule_link(env):
    """Bottom-up sync redesign (see models/attendance/attendance_schedule.py's
    '_relocate_via_calendar_blocks'/'_archive_via_calendar_blocks' docstrings and
    docs/en/developers/attendance/attendance_template.md's "Bottom-up sync redesign" section):
    the design invariant those two shared methods (and 'ems.group._resolve_or_flag_pending_block')
    now rely on is that every active 'ems.attendance_schedule' line always has at least one real
    'resource.calendar.attendance' row pointing at it via 'attendance_schedule_id' - the calendar is
    always the entry point, never the other way round.

    That FK is only ever set by 'ems.attendance_template._link_calendar_attendance', called at the
    end of '_sync_from_schedule_batch' - a calendar block created or resynced before this FK column
    existed (added 2026-08-11) or before the automatic create/write/unlink hook existed (added the
    same day as this migration, see the bottom-up sync redesign's Phase 4) never went through that
    step, so it can be missing the link even though a matching schedule line genuinely exists.

    Rather than writing a bespoke matching query here, this reuses the exact same full
    archive-and-rebuild-from-calendar tool already used by 'migrations/18.0.0.22.0' and
    'migrations/18.0.0.23.1'/'18.0.0.23.5' for the original calendar-driven-templates rollout -
    '_regenerate_all_from_calendars()' rebuilds every active template/line straight from each
    teacher's current calendar and links every calendar row it touches by construction, so running
    it once more here closes this exact gap without inventing new logic. Confirmed via a dry run
    against this project's own dev database (2026-09-08, rolled back, never committed): 11
    pre-existing unlinked lines dropped to 0, with zero unresolved room conflicts."""
    skipped = env['ems.attendance_template']._regenerate_all_from_calendars()
    _logger.info(
        "Migration 18.0.0.24.0: archived every pre-existing ems.attendance_template and "
        "regenerated a fresh, calendar-linked set from each teacher's current working schedule "
        "(backfill for calendar blocks that predate the attendance_schedule_id FK/automatic sync "
        "hook).")
    if not skipped:
        return

    weekdays = dict(env['ems.attendance_schedule'].weekdays_selection)
    for item in skipped:
        entry, other = item['entry'], item['conflicts_with_entry']
        _logger.warning(
            "Migration 18.0.0.24.0: SKIPPED regenerating a template for %s (%s, %s %s-%s, %s) - "
            "unresolved room conflict with %s (%s, %s %s-%s, %s). This is not corrected "
            "automatically - review both teachers' real working schedules by hand and re-sync "
            "the one that's wrong.",
            item['teacher'].display_name, env['ems.subject'].browse(entry['subject_id']).display_name,
            weekdays.get(entry['dayofweek']), entry['hour_from'], entry['hour_to'],
            env['ems.space'].browse(entry['space_id']).display_name,
            item['conflicts_with_teacher'].display_name,
            env['ems.subject'].browse(other['subject_id']).display_name,
            weekdays.get(other['dayofweek']), other['hour_from'], other['hour_to'],
            env['ems.space'].browse(other['space_id']).display_name,
        )
    _logger.warning(
        "Migration 18.0.0.24.0: %d entrie(s) skipped due to unresolved room conflicts - see the "
        "warnings above for exactly which ones and what each one conflicted with.", len(skipped))


def _sync_time_off_groups(env):
    """Take back the Time Off groups Odoo hands out when hr_holidays is installed.

    hr_holidays grants its Administrator group to 'base.default_user', the template every new
    user is copied from, and Odoo propagates that to the existing users at install time. On this
    centre's database that handed every internal user 'group_hr_holidays_manager' plus, by
    implication, 'group_hr_holidays_user' and 'hr.group_hr_user' - so every teacher could read
    every colleague's absence reason and supporting document, and every employee record besides.

    This is also what grants the approver group to whoever is actually named as an employee's
    'leave_manager_id', which no group chain can express, and what removes it from the members of
    the secretariat, who used to inherit it from 'ems.group_secretary' (that implication is
    dropped declaratively in security/groups.xml, but Odoo's implied-group writes are additive
    and never revoke what a user already materialised).

    The same call runs from post_init_hook for installations created from now on.
    """
    revoked = env['res.users']._ems_sync_time_off_groups()
    for xmlid, logins in revoked.items():
        _logger.info(
            "Migration 18.0.0.24.0: revoked %s from %s user(s): %s",
            xmlid, len(logins), ', '.join(sorted(logins)))
    if not revoked:
        _logger.info("Migration 18.0.0.24.0: no Time Off group had to be revoked.")


def _deactivate_native_leave_types(env):
    """Archive the absence types Odoo ships with, leaving only the centre's own nine.

    'Paid Time Off', 'Sick Time Off', 'Unpaid', 'Compensatory Days' and (from
    hr_holidays_attendance) 'Extra Hours' are none of the nine options the request form offers,
    and an employee picking one would land outside the centre's own rules entirely.

    This cannot be done from a data file: all five carry ir_model_data.noupdate = True, and it is
    that stored flag - not the loading file's own context - that decides whether an existing
    record gets written. Same call as post_init_hook's.
    """
    archived = env['hr.leave.type']._ems_deactivate_native_types()
    _logger.info(
        "Migration 18.0.0.24.0: archived %s of Odoo's own absence types%s",
        len(archived), (": " + ", ".join(archived.mapped('name'))) if archived else "")


def _fix_approval_activity_names(env):
    """Repair Odoo's Catalan name for the two Time Off approval activity types.

    'Temps de desaprovació' and 'Temps d'apagada de la segona aproximació' are machine
    translations that mean nothing, and they head every absence request in the chatter. Both
    records carry ir_model_data.noupdate = True, so a .po entry can never overwrite them - see
    mail.activity.type._ems_fix_approval_activity_names. Same call as post_init_hook's.
    """
    fixed = env['mail.activity.type']._ems_fix_approval_activity_names()
    _logger.info(
        "Migration 18.0.0.24.0: corrected the Catalan name of %s approval activity type(s)%s",
        len(fixed), (": " + ", ".join(fixed.mapped('name'))) if fixed else "")


def _recompute_leave_managers(env):
    """Make sure every employee's absence approver is the Area Manager of their top-level
    department, and not Odoo's own guess.

    'leave_manager_id' is a stored compute, and hr_holidays fills it when it creates the column -
    during this very upgrade. EMS overrides that computation (see
    ems_employee_base._compute_leave_manager: Odoo derives it from 'parent_id', which here is the
    Seminar Chief or Department Chief, the wrong person for an absence). Rather than depend on
    the two happening in the right order, recompute it explicitly afterwards.

    Archived employees included, and not for tidiness: an archived record left pointing at its
    Department Chief keeps handing that chief the approver group back, because hr_holidays
    grants it from any write of 'leave_manager_id' (hr_employee_base.write) while
    '_ems_sync_time_off_groups' only ever counts *active* employees when deciding who is
    entitled to keep it. The two disagreed on every upgrade.
    """
    employees = env['hr.employee'].with_context(active_test=False).search([])
    env.add_to_compute(employees._fields['leave_manager_id'], employees)
    employees.flush_recordset()
    without = employees.filtered(lambda employee: employee.department_id and not employee.leave_manager_id)
    _logger.info(
        "Migration 18.0.0.24.0: recomputed the absence approver of %s employee(s).", len(employees))
    if without:
        # Not an error: an Area Manager with no res.users cannot be an approver, and Odoo falls
        # back to letting an officer approve. Worth naming, because it is invisible otherwise.
        _logger.warning(
            "Migration 18.0.0.24.0: %s employee(s) have no absence approver, because their "
            "area's manager has no user account: %s",
            len(without), ', '.join(sorted(without.mapped('name'))))


def migrate(cr, _version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    # Order matters: '_sync_time_off_groups' grants the approver group from
    # 'employee.leave_manager_id', which until '_recompute_leave_managers' has run still holds
    # Odoo's own guess (derived from 'parent_id' - here the Department or Seminar Chief, the
    # wrong person entirely). Running the sync first therefore handed the approver group to
    # every Department Chief, and then quietly left it on them once the field was recomputed to
    # the real Area Manager - which is how four of them were still holding it on the development
    # database. The same call in post_init_hook has no such ordering problem, since a fresh
    # install computes 'leave_manager_id' with EMS's own method from the start.
    _recompute_leave_managers(env)
    _sync_time_off_groups(env)
    _deactivate_native_leave_types(env)
    _fix_approval_activity_names(env)
    _close_stale_attendances_same_day(env)
    _backfill_calendar_to_schedule_link(env)
