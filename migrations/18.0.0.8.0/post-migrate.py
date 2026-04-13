import logging

_logger = logging.getLogger(__name__)

def migrate(cr, _version):
    cr.execute("""
        UPDATE ems_course SET is_current = True
        WHERE start = 2025 AND "end" = 2026
    """)
    _logger.info("Migration: set is_current=True on course 2025-2026 (%d rows)", cr.rowcount)

    cr.execute("""
        UPDATE ems_course SET is_current = False
        WHERE start != 2025 OR "end" != 2026
    """)
    _logger.info("Migration: set is_current=False on other courses (%d rows)", cr.rowcount)
