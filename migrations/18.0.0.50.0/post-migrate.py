# -*- coding: utf-8 -*-
import json
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    _mark_requests_section(cr)
    _walkout_classes_off_the_roll_call(cr)
    _walkout_rejection_reasons_for_any_document(cr)
    _walkout_rejection_reasons_by_cause_archived(cr)
    _student_support_chooses_level_or_tutoring(cr)
    env = api.Environment(cr, SUPERUSER_ID, {})
    _drop_stale_plan_score_translations(cr)
    _delete_internationalisation_merits(cr)
    _recompute_staff_scores(env)


def _mark_requests_section(cr):
    """Issue #822: a meeting held by email writes the participants' answers under "Any other
    business", found by its section kind. The centre's "Precs i preguntes" section was seeded as
    plain text, and data/custom records are frozen, so its new kind is set here (a clean install
    gets it from the CSV). Writing through the ORM recomputes the kind stored on every minute's and
    type's copy of the section."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    section = env.ref('__import__.minute_section_requests', raise_if_not_found=False)
    if section and section.kind == 'text':
        section.kind = 'requests'
        _logger.info("Migration #822: section %s is now the one for any other business.", section.code)


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


def _walkout_rejection_reasons_by_cause_archived(cr):
    """Issue #844: a collective decision not to attend class is judged only on its procedure (a protest
    shown by a document, a group from 3rd of ESO, notice in time), never on who calls it or where, so the
    reasons "the call does not include the group's level or studies", "the call is for another sector" and
    "the call is for another autonomous community" are archived (the proposals already rejected with one
    keep it). The catalog is noupdate (the centre edits it), so the data file only reaches a clean install."""
    cr.execute("""
        UPDATE ems_student_walkout_rejection_reason r SET active = FALSE
          FROM ir_model_data d
         WHERE d.model = 'ems.student_walkout.rejection_reason' AND d.res_id = r.id AND d.module = 'ems'
           AND d.name IN ('student_walkout_rejection_level', 'student_walkout_rejection_sector',
                          'student_walkout_rejection_region')
    """)
    _logger.info("Migration #844: %s walkout rejection reason(s) by cause archived.", cr.rowcount)


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


# The staff criteria whose points changed on 2026-11-18 (adriamt: favour job shadowings and teaching
# over courses): the mobility plan gained the activity of proposal A (max 2.5), the last staff mobility
# went down to max 1, and the internationalisation criterion was dropped; the centre projects went up to
# max 2 and the languages to B2 1.5, C1 2, C2 2.5.
STAFF_SCORE_FIELDS = ('score_plan', 'score_last_mobility', 'score_projects', 'score_staff_language', 'score_total',
                      'score_complete', 'is_eligible')


def _drop_stale_plan_score_translations(cr):
    """The rating's "Score (max 2)" became "Score (max 2.5)". The upgrade writes the new English
    label, but loads the .po files without overwriting existing values, so the Catalan and Spanish
    labels kept "max. 2". Dropping those two keys here (post-migrate runs before the translations
    load) lets the .po fill them in again."""
    cr.execute("""
        UPDATE ir_model_fields
           SET field_description = field_description - 'ca_ES' - 'es_ES'
         WHERE model = 'ems.erasmus.plan_rating' AND name = 'score'
    """)
    if cr.rowcount:
        _logger.info("Migration 18.0.0.50.0: reset the translations of the plan rating's score.")


def _delete_internationalisation_merits(cr):
    """The internationalisation criterion no longer exists: its merits count for nothing and their
    kind is gone from the list."""
    cr.execute("DELETE FROM ems_erasmus_application_merit WHERE kind = 'internationalisation'")
    if cr.rowcount:
        _logger.info("Migration 18.0.0.50.0: deleted %s internationalisation merits.", cr.rowcount)


def _recompute_staff_scores(env):
    """The stored staff scores were computed with the old maximums: recompute them. The lines of a
    published resolution are a frozen copy and keep what was published."""
    applications = env['ems.erasmus.application'].with_context(active_test=False).search(
        [('call_id.audience', '=', 'staff')])
    if not applications:
        return
    for name in STAFF_SCORE_FIELDS:
        env.add_to_compute(applications._fields[name], applications)
    applications.flush_recordset()
    _logger.info("Migration 18.0.0.50.0: recomputed the scores of %s staff applications.", len(applications))
