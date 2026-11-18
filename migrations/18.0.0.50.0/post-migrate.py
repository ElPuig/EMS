# -*- coding: utf-8 -*-
import json
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    _walkout_classes_off_the_roll_call(cr)
    _walkout_rejection_reasons_for_any_document(cr)


def _walkout_classes_off_the_roll_call(cr):
    """Issue #844: a student walkout no longer justifies anything; every student who joins one is off
    the roll-calls of its day ("not required to attend: student walkout"). For the calls already closed
    or validated, the justifications their validation created are removed (their classes become
    absences again for a moment) and every class of the day of a student who joined is taken off the
    roll-call. No family is emailed about past days (ems_skip_family_notification). The column that
    linked the justification (ems_student_walkout.justification_id, a field this version removes) is
    read here and then dropped. A clean install has no such data, so post_init_hook needs nothing."""
    env = api.Environment(cr, SUPERUSER_ID, {'ems_skip_family_notification': True})
    cr.execute("SELECT 1 FROM information_schema.columns "
               "WHERE table_name = 'ems_student_walkout' AND column_name = 'justification_id'")
    removed = 0
    if cr.fetchone():
        cr.execute("SELECT justification_id FROM ems_student_walkout WHERE justification_id IS NOT NULL")
        justifications = env['ems.attendance_justification'].browse([row[0] for row in cr.fetchall()]).exists()
        removed = len(justifications)
        justifications.unlink()
        cr.execute("ALTER TABLE ems_student_walkout DROP COLUMN justification_id")
    walkouts = env['ems.student_walkout'].search([('state', 'in', ('closed', 'validated'))])
    for walkout in walkouts:
        walkout._ems_apply_walkout_lines()
    _logger.info("Migration #844: %s walkout justification(s) removed; the classes of the students who "
                 "join %s closed or validated walkout(s) taken off the roll-call.", removed, len(walkouts))


# The reasons as seeded by issue #800 and as issue #844 leaves them (en_US, ca_ES, es_ES).
OLD_DOCUMENT_REASON = "The attached document is not a valid call"
NEW_DOCUMENT_REASON = {
    'en_US': "The attached document does not support the proposal",
    'ca_ES': "El document adjunt no justifica la proposta",
    'es_ES': "El documento adjunto no justifica la propuesta",
}


def _walkout_rejection_reasons_for_any_document(cr):
    """Issue #844: a walkout is supported by any document (a union's call, the minute of the group's
    assembly...), so "no official call of a students' union" is archived and "the attached document is
    not a valid call" becomes "the attached document does not support the proposal". The catalog is
    noupdate (the centre edits it): a reason the centre renamed is left as it is. Raw SQL on existing
    columns. A clean install loads the new data file."""
    cr.execute("""
        UPDATE ems_student_walkout_rejection_reason r SET active = FALSE
          FROM ir_model_data d
         WHERE d.model = 'ems.student_walkout.rejection_reason' AND d.res_id = r.id AND d.module = 'ems'
           AND d.name = 'student_walkout_rejection_no_call'
    """)
    cr.execute("""
        UPDATE ems_student_walkout_rejection_reason r SET name = %s::jsonb
          FROM ir_model_data d
         WHERE d.model = 'ems.student_walkout.rejection_reason' AND d.res_id = r.id AND d.module = 'ems'
           AND d.name = 'student_walkout_rejection_document' AND r.name->>'en_US' = %s
    """, (json.dumps(NEW_DOCUMENT_REASON), OLD_DOCUMENT_REASON))
    _logger.info("Migration #844: walkout rejection reasons for any supporting document (%s renamed).", cr.rowcount)
