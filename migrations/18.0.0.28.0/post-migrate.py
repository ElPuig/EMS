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
    course onto the existing row."""
    current = env.company.current_course_id
    if not current:
        return
    courses = env['ems.course'].search([('start', '<=', current.start)], order='start asc')
    if not courses:
        return
    plannings = env['ems.planning'].search([])
    for planning in plannings:
        planning.course_id = courses[0].id
        # Odoo's ORM batches a plain field write like the one above rather than flushing it to
        # the DB immediately - without an explicit flush here, the copy() calls below insert
        # against the STILL-unflushed old course_id, tripping the (study_id, subject_id,
        # course_id) unique constraint against this very row (confirmed empirically 2026-09-23:
        # dropping this flush reproduces "duplicate key ... already exists" reliably).
        planning.flush_recordset(['course_id'])
        for course in courses[1:]:
            # install_mode=True: check_ponderation/check_course_id_required (models/planning/
            # planning.py) already skip themselves under this context, same as the original CSV
            # load - needed because 5 pre-existing plannings (all "MP 1665: Digitalització
            # aplicada als sectors productius", one per study) already sum to 106%, not 100%,
            # apparently since before check_ponderation existed at all (never modified since, so
            # never re-validated). This migration's job is to replicate that already-live
            # history unchanged, not to silently fix unrelated pre-existing data quality on the
            # way - see plans/ems_planning_outcome_ponderation_over_100.md.
            #
            # planning_outcome_ids is a plain one2many, copy=False by default (confirmed
            # empirically 2026-09-23) - copy() alone silently drops the outcome lines, so they
            # must be rebuilt explicitly here too.
            planning.with_context(install_mode=True).copy({
                'course_id': course.id,
                'planning_outcome_ids': [(0, 0, {
                    'outcome_id': outcome.outcome_id.id,
                    'ponderation': outcome.ponderation,
                }) for outcome in planning.planning_outcome_ids],
            })
    if plannings:
        _logger.info(
            "Migration 18.0.0.28.0: replicated %s planning(s) across %s course(s) (%s to %s).",
            len(plannings), len(courses), courses[0].name, courses[-1].name)


def migrate(cr, version):
    _drop_old_planning_unique_constraint(cr)
    env = api.Environment(cr, SUPERUSER_ID, {})
    _backfill_current_course_id(env)
    _replicate_plannings_across_history(env)
