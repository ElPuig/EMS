# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, _version):
    # By this point Odoo has already created the new 'non_teaching' integer/FK column (from the
    # Many2one field definition) and loaded 'ems.non_teaching_type''s seed data
    # (data/main/ems.non_teaching_type.csv). Backfill every real attendance row by joining the old
    # varchar code (saved off in pre-migrate.py as 'non_teaching_legacy') to the new model's 'code',
    # then drop the legacy column — see pre-migrate.py for why this is split across both phases.
    cr.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'resource_calendar_attendance' AND column_name = 'non_teaching_legacy'
    """)
    if not cr.fetchone():
        return

    cr.execute("""
        UPDATE resource_calendar_attendance rca
        SET non_teaching = nt.id
        FROM ems_non_teaching_type nt
        WHERE rca.non_teaching_legacy = nt.code
    """)
    _logger.info("Migration 18.0.0.21.0: backfilled 'non_teaching' on %d attendance row(s) from their legacy code.", cr.rowcount)

    cr.execute("""
        SELECT rca.id, rca.non_teaching_legacy FROM resource_calendar_attendance rca
        WHERE rca.non_teaching_legacy IS NOT NULL AND rca.non_teaching IS NULL
    """)
    unmatched = cr.fetchall()
    if unmatched:
        _logger.warning(
            "Migration 18.0.0.21.0: %d attendance row(s) had a 'non_teaching_legacy' code with no matching "
            "ems.non_teaching_type (needs manual review): %s", len(unmatched), unmatched,
        )

    cr.execute("ALTER TABLE resource_calendar_attendance DROP COLUMN non_teaching_legacy")
    _logger.info("Migration 18.0.0.21.0: dropped 'resource_calendar_attendance.non_teaching_legacy'.")
