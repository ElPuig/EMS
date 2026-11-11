# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    _rename_walkout_justification_reason(cr)


def _rename_walkout_justification_reason(cr):
    """Issue #800: the justification reason "Labour strike" is the student walkout's: its xmlid
    becomes attendance_justification_reason_walkout (before the data files reload, which reference
    the new one) and its English name "Student walkout", so that "strike" only means the
    disciplinary record (ems.strike). The record is noupdate, so the file cannot rename it: only
    while the English name is still the seeded one (a centre that renamed it keeps its name). The
    Catalan and Spanish names do not change."""
    cr.execute("""
        UPDATE ir_model_data SET name = 'attendance_justification_reason_walkout'
         WHERE module = 'ems' AND name = 'attendance_justification_reason_strike'
        RETURNING res_id
    """)
    row = cr.fetchone()
    if not row:
        return
    cr.execute("""
        UPDATE ems_attendance_justification_reason
           SET name = jsonb_set(name, '{en_US}', '"Student walkout"')
         WHERE id = %s AND name->>'en_US' = 'Labour strike'
    """, [row[0]])
    _logger.info("Migration #800: justification reason renamed to Student walkout.")
