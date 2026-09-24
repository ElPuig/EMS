# -*- coding: utf-8 -*-
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def _drop_old_planning_unique_constraint(cr):
    """ems.planning's own unique_study_subject SQL constraint was renamed to
    unique_study_subject_course this version - but Registry.finalize_constraints() (odoo/modules/
    registry.py) only swaps a model's _sql_constraints for real at the very end of load_modules(),
    after every module's migrations have already run (same reasoning documented in
    migrations/18.0.0.25.0/post-migrate.py's _merge_duplicate_student_ids). The OLD constraint is
    therefore still live in the database throughout this whole script, and would block
    _replicate_plannings_across_history below from creating more than one planning per
    study+subject. Drop it explicitly; finalize_constraints() adds the new one afterwards as
    normal - this is purely about not blocking a write already made under this same migration
    inside the transition window."""
    cr.execute('ALTER TABLE ems_planning DROP CONSTRAINT IF EXISTS ems_planning_unique_study_subject')


def _backfill_current_course_id(env):
    """Defensive safety net for some OTHER already-existing install that somehow never
    configured current_course_id (this dev DB / the real production it mirrors already has one
    set - this is a no-op for it). Never overrides an already-configured company. Runs BEFORE
    _replicate_plannings_across_history below, which needs a real current course."""
    companies = env['res.company'].search([('current_course_id', '=', False)])
    if not companies:
        return
    course = env['ems.course'].search([('is_current', '=', True)], limit=1)
    if course:
        companies.write({'current_course_id': course.id})
        _logger.info("Migration 18.0.0.28.0: backfilled current_course_id on %s company(ies).",
                     len(companies))


def _replicate_plannings_across_history(env):
    """Issue #503: ems.planning gains course_id. Every existing planning was, until now, a
    single timeless row valid for every course - to keep grade corrections on an OLD course
    finding the ponderations that were actually in force then (not today's), replicate each one
    across every course up to and including the current one, not just backfill the current
    course onto the existing row.

    Idempotent (checks existing_keys before copying, same pattern as course_transition_wizard.
    _apply_planning_rollover): safe to re-run this migration after a later fix is added to this
    same not-yet-released version, without needing to unwind the database by hand first."""
    current = env.company.current_course_id
    if not current:
        return
    courses = env['ems.course'].search([('start', '<=', current.start)], order='start asc')
    if not courses:
        return
    plannings = env['ems.planning'].search([('course_id', '=', courses[0].id)])
    if not plannings:
        return
    existing_keys = {
        (planning.study_id.id, planning.subject_id.id, planning.course_id.id)
        for planning in env['ems.planning'].search([('course_id', 'in', courses.ids)])
    }
    created = 0
    for planning in plannings:
        for course in courses[1:]:
            if (planning.study_id.id, planning.subject_id.id, course.id) in existing_keys:
                continue
            # install_mode=True: check_ponderation/check_course_id_required (models/planning/
            # planning.py) already skip themselves under this context, same as the original CSV
            # load - needed because some pre-existing plannings may not sum to 100 (see
            # plans/ems_planning_outcome_ponderation_over_100.md - _fix_subject_1665_outcome_
            # ponderation below cleans up the one confirmed case, but this replication step
            # itself must not block on it). planning_outcome_ids is a plain one2many, copy=False
            # by default (confirmed empirically 2026-09-23) - copy() alone silently drops the
            # outcome lines, so they must be rebuilt explicitly here too.
            planning.with_context(install_mode=True).copy({
                'course_id': course.id,
                'planning_outcome_ids': [(0, 0, {
                    'outcome_id': outcome.outcome_id.id,
                    'ponderation': outcome.ponderation,
                }) for outcome in planning.planning_outcome_ids],
            })
            created += 1
    if created:
        _logger.info(
            "Migration 18.0.0.28.0: replicated %s planning(s) across %s course(s) (%s to %s).",
            created, len(courses), courses[0].name, courses[-1].name)


def _fix_subject_1665_outcome_ponderation(env):
    """5 plannings for subject 'MP 1665' (ASIX/DAM/DAW/AIF/AD) summed to 106%, not 100% - a
    manual UI edit on 2026-07-31 added a 6th learning outcome's weight (RA6, added to the shared
    curriculum catalog the same day) without adjusting the other 5, and since
    ems.planning_outcome only became 'living data' (frozen, see res.company.
    _EMS_LIVING_CUSTOM_DATA_MODELS) as part of this same version, the very next upgrade before
    that fix landed silently reverted the 5 CSV-managed lines back to their original values,
    leaving the stray 6th line orphaned. See plans/ems_planning_outcome_ponderation_over_100.md
    for the full investigation. Developer-confirmed weights (2026-09-23): RA1=15, RA2=20,
    RA3=15, RA4=20, RA5=15, RA6=15.

    Rebuilds planning_outcome_ids from scratch for every ems.planning of this subject, across
    every course _replicate_plannings_across_history has created by the time this runs -
    sidesteps having to tell apart a CSV-tracked line from a stray/duplicate one (a copy()'d
    planning's outcome lines never carry an xmlid regardless of which of the two the source line
    was), and is naturally idempotent: re-running this always rebuilds to the same 6 correct
    lines."""
    weights = {'1665_01RA': 15, '1665_02RA': 20, '1665_03RA': 15,
               '1665_04RA': 20, '1665_05RA': 15, '1665_06RA': 15}
    outcomes_by_code = {
        outcome.code: outcome
        for outcome in env['ems.outcome'].search([('code', 'in', list(weights))])
    }
    if len(outcomes_by_code) != len(weights):
        _logger.warning(
            "Migration 18.0.0.28.0: expected 6 outcomes for subject 1665, found %s - skipping "
            "the ponderation fix, check ems.outcome data manually.", len(outcomes_by_code))
        return
    plannings = env['ems.planning'].search([('subject_id.code', '=', '1665')])
    if not plannings:
        return
    plannings.mapped('planning_outcome_ids').unlink()
    for planning in plannings:
        planning.with_context(install_mode=True).write({
            'planning_outcome_ids': [(0, 0, {
                'outcome_id': outcomes_by_code[code].id, 'ponderation': weight,
            }) for code, weight in weights.items()],
        })
    _logger.info(
        "Migration 18.0.0.28.0: rebuilt outcome ponderation for %s 'MP 1665' planning(s) "
        "(RA1=15, RA2=20, RA3=15, RA4=20, RA5=15, RA6=15).", len(plannings))


def migrate(cr, version):
    _drop_old_planning_unique_constraint(cr)
    env = api.Environment(cr, SUPERUSER_ID, {})
    _backfill_current_course_id(env)
    _replicate_plannings_across_history(env)
    _fix_subject_1665_outcome_ponderation(env)
