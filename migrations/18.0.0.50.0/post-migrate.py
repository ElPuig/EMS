# -*- coding: utf-8 -*-
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    _walkout_classes_off_the_roll_call(cr)


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
