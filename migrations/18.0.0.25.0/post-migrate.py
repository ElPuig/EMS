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


def _map_apply_on_to_route_flags(env):
    """apply_on_enrollment / sendable_during_course replaced a single apply_on selection that only
    ever existed in intermediate builds of this same, unreleased version.

    A database upgrading straight from 18.0.0.24.x never had that column: the two new Boolean
    columns are filled from their field defaults (applies to enrollment, not sendable), which is
    exactly right for every form that existed before this version. A database that did run an
    intermediate build (a dev box) still has apply_on: map it across, so a form created as "sent
    during the course" does not silently turn into an enrollment one, then drop the leftover
    column - Odoo never drops the column of a removed field on its own.
    """
    env.cr.execute("""
        SELECT 1 FROM information_schema.columns
         WHERE table_name = 'ems_authorization_template' AND column_name = 'apply_on'
    """)
    if not env.cr.fetchone():
        return
    env.cr.execute("""
        UPDATE ems_authorization_template
           SET apply_on_enrollment = coalesce(apply_on <> 'standalone', true),
               sendable_during_course = coalesce(apply_on = 'standalone', false)
    """)
    _logger.info("Migration 18.0.0.25.0: mapped apply_on onto the route flags for %s form(s).",
                 env.cr.rowcount)
    env.cr.execute("ALTER TABLE ems_authorization_template DROP COLUMN apply_on")


def migrate(cr, version):
    """No post_init_hook counterpart, deliberately: a fresh database has no authorization rows to
    backfill, no templates predating the route flags (their defaults cover the data/custom
    CSV load), and no ir.rule carrying the old domain - the data file loads the correct one on first
    install."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    _backfill_authorization_target(env)
    _map_apply_on_to_route_flags(env)
