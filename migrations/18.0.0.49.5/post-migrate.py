# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    _student_support_chooses_level_or_tutoring(cr)


def _student_support_chooses_level_or_tutoring(cr):
    """Issue #846: student support (ATAL) moves from 'tutoring' to the new 'level_or_tutoring' code,
    so its blocks count in their level's row unless they say tutoring. A type the centre gave another
    code keeps it. A clean installation gets it from _ems_seed_declaration_codes()."""
    cr.execute("""
        UPDATE ems_non_teaching_type
           SET declaration_code = 'level_or_tutoring'
         WHERE code = 'ATAL' AND declaration_code = 'tutoring'
    """)
    _logger.info("Migration #846: %s student support type(s) now choose level or tutoring.", cr.rowcount)
