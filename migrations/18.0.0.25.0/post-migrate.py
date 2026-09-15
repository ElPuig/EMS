# -*- coding: utf-8 -*-
import logging

from odoo import SUPERUSER_ID, _, api

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


def _flag_unresolved_duplicate_student_id(env, student_id, partners, reason):
    """Schedules a generic To-Do activity (mail.mail_activity_data_todo - no EMS-specific
    activity type exists for this rare, defensive case, so reusing Odoo's own generic one avoids
    a throwaway data/i18n record) on every contact in an unresolved duplicate-IDALU group,
    assigned to the Administrator (base.user_admin always exists; a migration script has no way
    to know which real person administers contacts on someone else's installation).

    On the contact's own form this shows as a persistent to-do banner, and in the assignee's
    Activities menu/systray - unlike the server log line next to this call, which only reaches
    whoever happens to be watching the log during this exact upgrade window.

    Scheduled on EVERY contact in the group, not just one: whichever duplicate someone happens to
    open first, they see it. De-duplicated by checking for an already-open activity with the same
    summary first, so a left-untouched group doesn't grow a fresh to-do on every single upgrade
    until it's actually resolved.
    """
    summary = _('Duplicate Student ID (IDALU) %(student_id)s needs a manual Merge',
                student_id=student_id)
    reason = reason.rstrip('.')
    admin = env.ref('base.user_admin', raise_if_not_found=False)
    if not admin:
        return
    for partner in partners:
        if partner.activity_ids.filtered(lambda a: a.summary == summary):
            continue
        partner.activity_schedule(
            act_type_xmlid='mail.mail_activity_data_todo',
            summary=summary,
            note=_(
                'Contacts %(ids)s share the Student ID (IDALU) %(student_id)s, which must be '
                'unique. EMS could not merge them automatically: %(reason)s. Open Contacts, '
                'select them and use the Merge action by hand once you have decided which '
                'record should hold the data.',
                ids=', '.join(str(partner_id) for partner_id in partners.ids),
                student_id=student_id, reason=reason,
            ),
            user_id=admin.id,
        )


def _merge_duplicate_student_ids(env):
    """Issue #460: student_id (IDALU) becomes unique, backed by a database UNIQUE constraint.
    Any pre-existing installation may already carry duplicate IDALUs from before the constraint
    existed - typically a returning former student registered again as a brand-new contact
    instead of reopening their old one (the exact scenario the new duplicate-IDALU error message
    already points a secretary to fix by hand via Merge, see models/contacts/contact.py).

    The schema sync that adds the constraint (odoo/modules/registry.py::_add_sql_constraints)
    runs automatically before this post-migrate script and defers a failing constraint to
    registry.finalize_constraints(), which only runs after every module has finished loading -
    so fixing the data here, before that final retry, is what lets the constraint actually end up
    installed by the end of this same upgrade.

    Auto-resolve only the unambiguous case: a group of contacts sharing one IDALU where exactly
    one of them is active. Those are merged via the same base.partner.merge.automatic.wizard the
    developer already uses interactively (models/contacts/partner_merge_wizard.py's own
    _update_values() hands the IDALU to the destination) - the active contact as destination, so
    no live data is ever the one discarded. A group with zero or more than one active contact, or
    one the wizard itself refuses (e.g. two contacts linked to different res.users logins), is a
    data decision a migration script should not make blindly: left untouched, logged, AND flagged
    with a persistent to-do activity (see _flag_unresolved_duplicate_student_id below) - a log
    line alone is only seen by whoever happens to be watching the server log during the exact
    upgrade window, which on someone else's EMS installation may be nobody.

    Idempotent: once every duplicate is merged away, the SELECT below returns nothing and this
    is a no-op on every later upgrade. A left-untouched group gets re-flagged on every upgrade
    until it's actually resolved (activity_schedule() is safe to call again - see its own
    dedup note below), so the to-do can't be silently lost by marking it done too early.
    """
    env.cr.execute("""
        SELECT student_id FROM res_partner
         WHERE student_id IS NOT NULL AND student_id != ''
         GROUP BY student_id HAVING count(*) > 1
    """)
    duplicated_ids = [row[0] for row in env.cr.fetchall()]
    if not duplicated_ids:
        return

    Partner = env['res.partner'].with_context(active_test=False)
    wizard = env['base.partner.merge.automatic.wizard'].create({})
    merged_count = 0
    left_untouched = []
    for student_id in duplicated_ids:
        partners = Partner.search([('student_id', '=', student_id)])
        active_partners = partners.filtered('active')
        if len(active_partners) != 1:
            reason = "no single active contact holds this Student ID"
            _flag_unresolved_duplicate_student_id(env, student_id, partners, reason)
            left_untouched.append((student_id, partners.ids))
            continue
        try:
            wizard._merge(partners.ids, active_partners)
            merged_count += 1
        except Exception as exc:
            _logger.exception(
                "Migration 18.0.0.25.0: could not auto-merge duplicate Student ID (IDALU) %s "
                "(contacts %s) - left untouched, needs a manual Merge.", student_id, partners.ids)
            _flag_unresolved_duplicate_student_id(env, student_id, partners, str(exc))
            left_untouched.append((student_id, partners.ids))

    if merged_count:
        _logger.info(
            "Migration 18.0.0.25.0: auto-merged %s duplicate Student ID (IDALU) group(s) - each "
            "archived duplicate merged into its active contact.", merged_count)
    if left_untouched:
        _logger.warning(
            "Migration 18.0.0.25.0: %s duplicate Student ID (IDALU) group(s) left untouched "
            "(not exactly one active contact in the group) - the database UNIQUE constraint "
            "stays absent for these until resolved by hand via Merge: %s",
            len(left_untouched), left_untouched)


def migrate(cr, version):
    """No post_init_hook counterpart, deliberately: a fresh database has no authorization rows to
    backfill, no templates predating the route flags (their defaults cover the data/custom
    CSV load), no ir.rule carrying the old domain - the data file loads the correct one on first
    install - and no pre-existing contacts that could carry a duplicate Student ID from before
    issue #460's constraint existed."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    _backfill_authorization_target(env)
    _map_apply_on_to_route_flags(env)
    _merge_duplicate_student_ids(env)
