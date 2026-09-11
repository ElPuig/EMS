# -*- coding: utf-8 -*-
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def _backfill_authorization_target(env):
    """Issue #443: ems.authorization gains partner_id/course_id, which become the record's real
    anchor now that an authorization can be sent during the course with no enrollment behind it.
    Every pre-existing row got there through an enrollment, so that enrollment is where both
    values come from.

    Plain SQL rather than the ORM: this is a one-shot copy between two columns that already
    exist by the time post-migrate runs, over every historical row, and it must not fire the
    response-rule write() override. Idempotent (only touches rows still missing a value), so a
    re-run after a partially applied upgrade is safe.
    """
    env.cr.execute("""
        UPDATE ems_authorization a
           SET partner_id = o.partner_id,
               course_id = o.ems_course_id
          FROM sale_order o
         WHERE a.enrollment_id = o.id
           AND (a.partner_id IS NULL OR a.course_id IS NULL)
    """)
    _logger.info("Migration 18.0.0.25.0: backfilled student/academic year on %s authorization(s).",
                 env.cr.rowcount)

    # A row left without a student is invisible to the portal's ownership check and to the
    # student file, so it must not pass unnoticed - but it must not abort the upgrade either.
    env.cr.execute("""
        SELECT count(*) FROM ems_authorization WHERE partner_id IS NULL OR course_id IS NULL
    """)
    orphans = env.cr.fetchone()[0]
    if orphans:
        _logger.warning(
            "Migration 18.0.0.25.0: %s authorization(s) still have no student or academic year "
            "(their enrollment is gone). They will not show up in the portal until fixed by hand.",
            orphans)


def _default_template_apply_on(env):
    """Every authorization template that existed before this version was, by definition, part of
    the enrollment process - apply_on's own column default covers rows created from now on, this
    covers the ones already on file."""
    env.cr.execute("""
        UPDATE ems_authorization_template SET apply_on = 'enrollment' WHERE apply_on IS NULL
    """)
    _logger.info("Migration 18.0.0.25.0: defaulted apply_on on %s authorization template(s).",
                 env.cr.rowcount)


def migrate(cr, version):
    """No post_init_hook counterpart, deliberately: a fresh database has no authorization rows to
    backfill, no templates predating apply_on (the field's default covers the data/custom CSV
    load), and no ir.rule carrying the old domain - the data file loads the correct one on first
    install."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    _backfill_authorization_target(env)
    _default_template_apply_on(env)
