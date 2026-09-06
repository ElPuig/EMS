# -*- coding: utf-8 -*-
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def _archive_departed_teacher_calendars(env):
    """Retroactively applies 'hr.employee.action_archive()' 's new cascade to its own personal
    calendar (models/employees/employee.py) to a teacher already archived before that cascade
    existed. Archiving a teacher directly - a mid-course departure that never goes through
    '_apply_calendar_rollover()' - left their 'resource.calendar', and every attendance row still
    on it, active indefinitely: found via a real departed teacher (David Tomás) still appearing
    on the Guard Duty Board 2026-09-06, the same root cause already fixed once for the
    course-transition-rollover path (migrations/18.0.0.23.1/post-migrate.py's
    '_archive_orphaned_calendar_rows', a distinct gap). 'employee_id == employee' mirrors the new
    cascade's own guard - never touches a framework or a calendar shared with another employee.
    Calling 'action_archive()' (not a raw UPDATE) reuses 'ems_working_schedule.action_archive()'
    's own existing cascade to 'attendance_ids' for free.

    In post-migrate, not pre-migrate, despite operating on pre-existing columns only: confirmed
    empirically (2026-09-06) that 'resource.calendar.employee_id' is not yet a resolvable ORM
    field from within pre-migrate's own environment ('AttributeError: 'resource.calendar' object
    has no attribute 'employee_id'') - the registry pre-migrate scripts run against isn't fully
    set up yet, unlike a plain 'cr.execute()'. Any migration that needs real ORM field/method
    access (not just raw SQL) belongs in post-migrate regardless of whether the columns
    themselves are new."""
    employees = env['hr.employee'].with_context(active_test=False).search([('active', '=', False)])
    archived = env['resource.calendar']
    for employee in employees:
        calendar = employee.resource_calendar_id
        if calendar.employee_id == employee and calendar.active:
            calendar.action_archive()
            archived |= calendar
    _logger.info(
        "Migration 18.0.0.23.4: archived %d departed teacher(s)' own calendar (and any "
        "remaining active attendance rows on it).", len(archived))


def migrate(cr, _version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    _archive_departed_teacher_calendars(env)
