# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    _rename_justification_notes_to_details(cr)


def _rename_justification_notes_to_details(cr):
    """Issue #795: a justification's free text is now the details of its reason. Every existing
    justification becomes 'Other' (post-migrate), whose details are its old notes. Renamed before
    the schema sync, so Odoo neither drops the old column nor creates an empty one."""
    cr.execute("""
        SELECT 1 FROM information_schema.columns
         WHERE table_name = 'ems_attendance_justification' AND column_name = 'notes'
    """)
    if cr.fetchone():
        cr.execute("ALTER TABLE ems_attendance_justification RENAME COLUMN notes TO details")
        _logger.info("Migration #795: justification notes renamed to details.")
