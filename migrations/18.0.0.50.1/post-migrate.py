# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    _fill_closed_case_file_tutor(cr)


def _fill_closed_case_file_tutor(cr):
    """Issue #817: the case file now stores its own tutor (computed from the student's group while
    they have one). A case file already closed by the withdrawal belongs to a student with no
    group, so the new column came out empty: take the tutor the student had that course from their
    academic history, which freezes it just before the exit."""
    cr.execute("""
        UPDATE ems_ex_officio_withdrawal withdrawal
           SET tutor_id = record.tutor_id
          FROM ems_student_year_record record
         WHERE withdrawal.tutor_id IS NULL
           AND record.student_id = withdrawal.student_id
           AND record.course_id = withdrawal.course_id
           AND record.tutor_id IS NOT NULL
    """)
    _logger.info("Ex officio case files: tutor restored from the academic history on %s", cr.rowcount)
