# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    _rename_walkout_validation(cr)


def _rename_walkout_validation(cr):
    """Issue #844: validating a student walkout no longer justifies anything, so its state `justified`
    is now `validated` (also as the state a call was rejected from) and the Head of Studies' task is
    "Validate the student walkout" (xmlid mail_activity_student_walkout_justify becomes
    mail_activity_student_walkout_validate before the data files reload, which reference the new one).
    Raw SQL: the columns already exist. A clean install has none of it."""
    cr.execute("UPDATE ems_student_walkout SET state = 'validated' WHERE state = 'justified'")
    states = cr.rowcount
    cr.execute("UPDATE ems_student_walkout SET rejected_from_state = 'validated' WHERE rejected_from_state = 'justified'")
    cr.execute("""
        UPDATE ir_model_data SET name = 'mail_activity_student_walkout_validate'
         WHERE module = 'ems' AND name = 'mail_activity_student_walkout_justify'
           AND NOT EXISTS (SELECT 1 FROM ir_model_data
                            WHERE module = 'ems' AND name = 'mail_activity_student_walkout_validate')
    """)
    _logger.info("Migration #844: %s validated student walkout(s) renamed from 'justified'.", states)
