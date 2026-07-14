# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, _version):
    # 'resource_calendar_attendance.non_teaching' changes from a Selection (varchar column) to a
    # Many2one (integer FK) to the new 'ems.non_teaching_type' model. Odoo's own schema sync cannot
    # convert existing varchar codes ('BR', 'G'...) into integer foreign keys, so the old column is
    # renamed out of the way here, before Odoo creates the new 'non_teaching' integer column for the
    # Many2one field. The backfill (mapping old codes to the new model's records, using the seed data
    # loaded during this same upgrade) happens in post-migrate.py, once both the new column and the
    # new model's rows actually exist.
    cr.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'resource_calendar_attendance' AND column_name = 'non_teaching'
    """)
    if cr.fetchone():
        cr.execute("ALTER TABLE resource_calendar_attendance RENAME COLUMN non_teaching TO non_teaching_legacy")
        _logger.info("Migration 18.0.0.21.0: renamed 'resource_calendar_attendance.non_teaching' to 'non_teaching_legacy' ahead of its Many2one conversion.")
