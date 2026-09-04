# -*- coding: utf-8 -*-
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def _backfill_null_original_check_times(env):
    """One-time backfill for ems.attendance_correction.create()'s own bug, fixed in this same
    version (models/attendance/attendance_correction.py): attendance_id is readonly="1" in the
    form and only ever reaches create() via the "Request Correction" button's
    default_attendance_id context - never explicit in vals. Odoo only merges that context
    default into vals inside the base create() (_add_missing_default_values), which runs AFTER
    this model's own override, so every correction request created before this fix browsed an
    empty hr.attendance recordset while snapshotting original_check_in/original_check_out,
    silently saving both as NULL - action_accept() on such a request then crashed with
    AttributeError: 'bool' object has no attribute 'astimezone'. Found via issue #396 (a Head
    of Studies unable to accept a teacher's request) on the real production data: the very
    first correction request ever created had exactly this problem.

    Backfills each field independently from its still-linked attendance_id's current
    check_in/check_out (attendance_id is ondelete="cascade", so a surviving correction row
    always has one). Safe because original_check_in/original_check_out are only ever written
    once, at create() time, and never touched again anywhere else in the codebase - a non-NULL
    value here is always the real original, never something this backfill should overwrite.
    active_test=False so an already-archived request is reached too, same reasoning as
    18.0.0.23.1's own _resync_teaching_from_calendars()."""
    corrections = env['ems.attendance_correction'].with_context(active_test=False).search([
        '|', ('original_check_in', '=', False), ('original_check_out', '=', False),
    ])
    fixed = env['ems.attendance_correction']
    for correction in corrections:
        values = {}
        if not correction.original_check_in and correction.attendance_id.check_in:
            values['original_check_in'] = correction.attendance_id.check_in
        if not correction.original_check_out and correction.attendance_id.check_out:
            values['original_check_out'] = correction.attendance_id.check_out
        if values:
            correction.write(values)
            fixed |= correction
    _logger.info(
        "Migration 18.0.0.23.2: backfilled original_check_in/original_check_out on %d "
        "ems.attendance_correction row(s) left NULL by the pre-fix create() bug (issue #396).",
        len(fixed))


def migrate(cr, _version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    _backfill_null_original_check_times(env)
