# -*- coding: utf-8 -*-
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def _regenerate_attendance_templates_from_calendars(env):
    """Fixes production data left behind by the bug fixed in this same version
    (`ems.attendance_template._plan_schedule_sync`, see models/attendance/attendance_template.py):
    a solo teacher who taught one subject to two or more different groups (no co-teaching) could
    have every one of their templates for that subject silently archived, with nothing recreated
    in their place, the next time their schedule was resynced (a working-schedules re-import, or a
    live edit on their own Schedule tab) - even though their calendar stayed completely correct.

    Rather than trying to detect which teachers were actually hit (a targeted detection would risk
    fragmenting a co-taught template if it missed one side of it - a real teacher who splits a
    reconstructed group differently from before), this reuses the exact same
    `_regenerate_all_from_calendars()` full rebuild already used by `migrations/18.0.0.22.0` for the
    original calendar-driven-templates rollout: archive every active template, rebuild an
    equivalent set from each teacher's CURRENT (correct) calendar. Safe to run again - archiving
    never touches real attendance-session history (see that method's own docstring) - at the cost
    of every already-correct template also getting a new id/color even though nothing about it
    actually changes."""
    skipped = env['ems.attendance_template']._regenerate_all_from_calendars()
    _logger.info(
        "Migration 18.0.0.23.5: archived every pre-existing ems.attendance_template and "
        "regenerated a fresh, calendar-backed set from each teacher's current working schedule "
        "(repair for the same-subject/several-groups sync bug fixed in this version).")
    if not skipped:
        return

    weekdays = dict(env['ems.attendance_schedule'].weekdays_selection)
    for item in skipped:
        entry, other = item['entry'], item['conflicts_with_entry']
        _logger.warning(
            "Migration 18.0.0.23.5: SKIPPED regenerating a template for %s (%s, %s %s-%s, %s) - "
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
        "Migration 18.0.0.23.5: %d entrie(s) skipped due to unresolved room conflicts - see the "
        "warnings above for exactly which ones and what each one conflicted with.", len(skipped))


def _delete_unused_archived_attendance_templates(env):
    """One-off backlog cleanup for `ems.attendance_template.py`'s `_archive_or_delete()` (added
    this same version, see models/attendance/attendance_template.py): from now on, a superseded
    template with no real attendance history gets deleted outright instead of archived forever -
    but that only affects templates archived FROM THIS POINT ON. Every template ALREADY sitting
    archived from before this fix (found from a real complaint: repeatedly re-importing working
    schedules to fix small details, several times in one day, leaves hundreds of never-used
    archived templates behind) needs this separate one-time sweep, since it was never touched by
    the sync pipeline's own archive-or-delete decision at the time it was archived.

    Reuses `_has_real_sessions()` (checks every schedule line, active or archived, for a real
    `attendance_session_ids` entry) as the exact same safety predicate `unlink()` itself enforces -
    this can never delete a template with real history, and the DB-level `ON DELETE RESTRICT` on
    `ems_attendance_session_header.attendance_schedule_id` would refuse the delete outright even if
    it somehow did."""
    archived = env['ems.attendance_template'].with_context(active_test=False).search([('active', '=', False)])
    unused = archived.filtered(lambda template: not template._has_real_sessions())
    count = len(unused)
    unused.unlink()
    _logger.info(
        "Migration 18.0.0.23.5: deleted %d already-archived ems.attendance_template record(s) "
        "with no real attendance history (backlog cleanup for repeated working-schedule "
        "re-imports before this version's archive-or-delete fix).", count)


def migrate(cr, _version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    _regenerate_attendance_templates_from_calendars(env)
    _delete_unused_archived_attendance_templates(env)
