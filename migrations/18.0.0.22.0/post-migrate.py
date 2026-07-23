# -*- coding: utf-8 -*-
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def _enable_unaccent(cr):
    # Odoo automatically wraps ilike/like search domains (list/kanban search bars,
    # name_search, filters...) with the SQL unaccent() function whenever the
    # PostgreSQL 'unaccent' extension is present (see odoo/modules/db.py::has_unaccent
    # and odoo/modules/registry.py) - no EMS code changes are needed, just the
    # extension. Detection happens once per registry load, so this only takes effect
    # after the Odoo service restart that follows this migration.
    cr.execute("CREATE EXTENSION IF NOT EXISTS unaccent;")
    _logger.info("Migration 18.0.0.22.0: enabled PostgreSQL 'unaccent' extension for accent-insensitive search.")


def _archive_existing_ex_students(env):
    """Withdrawal now archives the student (active=False), mirroring hr.employee
    (see toggle_active/EmsWithdrawalWizard.action_apply in
    models/contacts/contact.py and models/contacts/graduation_wizard.py). Alumni
    and withdrawal records converted before this change stayed active=True
    forever — bring the existing ones in line. Reuses the same helpers and the
    same ordering the wizard itself uses: archiving must run after revoking the
    portal (res.partner.write() refuses to archive a contact still linked to an
    active portal user); if that revoke fails for a given record, it's skipped
    and logged instead of aborting the whole batch.
    """
    ex_students = env['res.partner'].search([
        ('contact_type', 'in', ('alumni', 'withdrawal')),
        ('active', '=', True),
    ])
    archived = skipped = 0
    for student in ex_students:
        student._ems_revoke_student_portal()
        if student._has_active_portal_user():
            skipped += 1
            continue
        student.write({'active': False})
        archived += 1
    if archived:
        _logger.info(
            "Migration 18.0.0.22.0: archived %d existing alumni/withdrawal record(s).", archived)
    if skipped:
        _logger.warning(
            "Migration 18.0.0.22.0: %d alumni/withdrawal record(s) kept active — "
            "portal access could not be revoked.", skipped)


def _backfill_google_ws_suspended(env):
    """google_ws_suspended (added in 18.0.0.19.0/18.0.0.19.2) defaulted every
    pre-existing row to False, including staff/students whose account was
    already suspended in Google before the field existed — the header buttons
    then offered "Suspend" instead of "Reactivate" for them. There is no way to
    ask Google for the real state from a migration, so this aligns the flag
    with the same signal the app itself already treats as "suspended": an
    archived teacher/ASP, or a contact converted to alumni/withdrawal (run
    after _archive_existing_ex_students so their 'active' is already correct).
    """
    employees = env['hr.employee'].with_context(active_test=False).search([
        ('active', '=', False),
        ('work_email', '!=', False),
        ('google_ws_suspended', '=', False),
    ])
    if employees:
        employees.write({'google_ws_suspended': True})
        _logger.info(
            "Migration 18.0.0.22.0: marked %d pre-existing employee Google account(s) as suspended.",
            len(employees))

    students = env['res.partner'].with_context(active_test=False).search([
        ('contact_type', 'in', ('alumni', 'withdrawal')),
        ('student_email', '!=', False),
        ('google_ws_suspended', '=', False),
    ])
    if students:
        students.write({'google_ws_suspended': True})
        _logger.info(
            "Migration 18.0.0.22.0: marked %d pre-existing student Google account(s) as suspended.",
            len(students))


def migrate(cr, _version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    _enable_unaccent(cr)
    _archive_existing_ex_students(env)
    _backfill_google_ws_suspended(env)
