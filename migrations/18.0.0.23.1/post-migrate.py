# -*- coding: utf-8 -*-
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def _archive_orphaned_calendar_rows(cr):
    """Every resource.calendar.attendance row still active=True on an already-archived
    calendar - exactly what 'ems_working_schedule.action_archive()' 's new cascade
    (models/employees/working_schedule.py) would already have done, applied retroactively to
    state that predates it. Found via the Guard Duty Board still showing a departed/reassigned
    teacher's stale guard-duty slot - see plans/course_transition_stale_teacher_assignments.md."""
    cr.execute("""
        UPDATE resource_calendar_attendance rca
        SET active = false
        FROM resource_calendar rc
        WHERE rca.calendar_id = rc.id AND rc.active = false AND rca.active = true
    """)
    _logger.info(
        "Migration 18.0.0.23.1: archived %d leftover resource.calendar.attendance row(s) on an "
        "already-archived calendar.", cr.rowcount)


def _resync_teaching_from_calendars(env):
    """Resyncs ems.teaching for every real teacher from their CURRENT calendar - reuses the same
    fix now applied going forward ('hr.employee._teaching_entries_from_calendar()' +
    'ems.teaching.sync_from_schedule()', see models/employees/teaching.py and
    models/employees/employee.py). Searches each teacher's live calendar state rather than
    assuming anything about this database's own shape - safe/idempotent for a teacher whose
    ems.teaching was already correct (no net change), and also what clears a stale group
    tutor_id wherever the tutorship ems.teaching row itself goes away
    ('ems.teaching.unlink()' 's own cleanup) - no separate pass needed for that case.

    'active_test=False' is deliberate here (unlike the ongoing fix, which only ever resyncs a
    course transition's own 'affected_teachers' or an explicit 'regenerate_all_from_calendars()'
    scope): this one-time backfill must also reach an ALREADY-archived/departed teacher (found
    empirically running this migration the first time - Priscila Rodríguez's own case, the
    report's original example, was otherwise silently skipped by the default active-only search
    and kept 6 stale 'ems.teaching' rows). An archived employee's 'resource_calendar_id' still
    reflects their real final calendar state, so resyncing from it is exactly as safe/correct as
    for an active teacher."""
    teachers = env['hr.employee'].with_context(active_test=False).search([
        ('employee_type', '=', 'teacher'),
        ('resource_calendar_id', '!=', False),
        ('resource_calendar_id.is_framework', '=', False),
    ])
    for teacher in teachers:
        env['ems.teaching'].sync_from_schedule(teacher, teacher._teaching_entries_from_calendar())
    _logger.info("Migration 18.0.0.23.1: resynced ems.teaching for %d teacher(s) from their current calendar.", len(teachers))


def _backfill_stale_tutor_ids(env):
    """Defensive pass for a group tutor_id set by hand with no matching calendar/tutorship
    teaching row to begin with, so '_resync_teaching_from_calendars()' 's own unlink() hook
    never had anything to react to. Searches live state (is there STILL a matching active
    tutorship ems.teaching for this exact group+teacher, right now) rather than assuming."""
    groups = env['ems.group'].search([('tutor_id', '!=', False)])
    cleared = env['ems.group']
    for group in groups:
        has_tutorship_teaching = env['ems.teaching'].search_count([
            ('teacher_id', '=', group.tutor_id.id), ('group_id', '=', group.id),
            ('subject_id.is_tutorship', '=', True), ('active', '=', True),
        ])
        if not has_tutorship_teaching:
            group.tutor_id = False
            cleared |= group
    _logger.info("Migration 18.0.0.23.1: cleared a stale tutor_id on %d group(s).", len(cleared))


def _backfill_stale_delegate_ids(env):
    """Clears a group's delegate_id wherever the current delegate is no longer actually a
    member of it - same check 'res.partner._ems_clear_stale_delegate()' applies going forward
    (models/contacts/contact.py)."""
    groups = env['ems.group'].search([('delegate_id', '!=', False)])
    cleared = env['ems.group']
    for group in groups:
        if group.delegate_id.main_group_id != group:
            group.delegate_id = False
            cleared |= group
    _logger.info("Migration 18.0.0.23.1: cleared a stale delegate_id on %d group(s).", len(cleared))


def migrate(cr, _version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    _archive_orphaned_calendar_rows(cr)
    _resync_teaching_from_calendars(env)
    _backfill_stale_tutor_ids(env)
    _backfill_stale_delegate_ids(env)
