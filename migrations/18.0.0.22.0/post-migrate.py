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


def _column_exists(cr, table, column):
    cr.execute("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = %s AND column_name = %s
    """, (table, column))
    return bool(cr.fetchone())


def _backfill_attendance_status_id(cr):
    """Second half of the status -> status_id migration - see the matching
    _rename_old_status_columns() in pre-migrate.py for why the old values are read from
    status_old/attendance_status_old (renamed there) rather than status/attendance_status
    directly: by the time post-migrate runs, schema sync has already added the new
    status_id/attendance_status_id columns and the ems.attendance_status seed data is
    already loaded (data files load before post-migrate), so xmlids resolve correctly
    here. Backfill from the preserved old string codes, then drop the backup columns -
    Odoo's own schema sync does not manage columns it doesn't recognize as a current
    field, so status_old/attendance_status_old would otherwise sit unused forever.
    """
    code_to_xmlid = {
        'a_attended': 'attendance_status_attended',
        'a_delayed': 'attendance_status_delayed',
        'm_miss': 'attendance_status_miss',
        'm_justified': 'attendance_status_justified',
        'a_issue': 'attendance_status_issue',
    }

    if _column_exists(cr, 'ems_attendance_session_line', 'status_old'):
        for code, xmlid in code_to_xmlid.items():
            cr.execute("""
                UPDATE ems_attendance_session_line SET status_id = (
                    SELECT res_id FROM ir_model_data WHERE module = 'ems' AND name = %s
                ) WHERE status_old = %s
            """, (xmlid, code))
        cr.execute("ALTER TABLE ems_attendance_session_line DROP COLUMN status_old")
        _logger.info(
            "Migration 18.0.0.22.0: backfilled ems_attendance_session_line.status_id "
            "and dropped the status_old backup column.")

    if _column_exists(cr, 'ems_attendance_issue_status', 'attendance_status_old'):
        for code, xmlid in code_to_xmlid.items():
            cr.execute("""
                UPDATE ems_attendance_issue_status SET attendance_status_id = (
                    SELECT res_id FROM ir_model_data WHERE module = 'ems' AND name = %s
                ) WHERE attendance_status_old = %s
            """, (xmlid, code))
        cr.execute("ALTER TABLE ems_attendance_issue_status DROP COLUMN attendance_status_old")
        _logger.info(
            "Migration 18.0.0.22.0: backfilled ems_attendance_issue_status.attendance_status_id "
            "and dropped the attendance_status_old backup column.")


def _backfill_special_type(cr):
    """Second half of the special_wpi_enrolled/special_subject_enrolled -> special_type
    migration - see the matching _rename_old_special_columns() in pre-migrate.py. A row
    with both old booleans True never actually occurred in production (confirmed via
    ems_prod_snapshot, 2026-07-30), but 'wpi' wins if it ever did, matching the old
    onchange's own precedence (its `if special_wpi_enrolled: ...` branch always checked
    first). Plain Selection value, no xmlid lookup needed (unlike attendance_status_id).
    """
    if not _column_exists(cr, 'ems_limesurvey_block', 'special_wpi_enrolled_old'):
        return
    cr.execute("""
        UPDATE ems_limesurvey_block SET special_type = CASE
            WHEN special_wpi_enrolled_old THEN 'wpi'
            WHEN special_subject_enrolled_old THEN 'subject'
            ELSE NULL
        END
    """)
    cr.execute("ALTER TABLE ems_limesurvey_block DROP COLUMN special_wpi_enrolled_old")
    cr.execute("ALTER TABLE ems_limesurvey_block DROP COLUMN special_subject_enrolled_old")
    _logger.info(
        "Migration 18.0.0.22.0: backfilled ems_limesurvey_block.special_type (%d rows "
        "checked) and dropped the special_wpi_enrolled_old/special_subject_enrolled_old "
        "backup columns.", cr.rowcount)


def _backfill_iban_trust(env):
    """Re-apply _apply_bank_account() for every already-approved IBAN document, so its
    underlying res.partner.bank ends up trusted (allow_out_payment=True) - see
    plans/student_document_iban_renewal_allow_out_payment.md. Before this version, the
    portal IBAN renewal route (controllers/portal_enrollment.py) could mark a document
    'approved' without ever touching allow_out_payment, unlike action_approve(). Confirmed
    against production data (2026-07-30): 332 already-posted direct-debit invoices ended up
    with no bank reference as a result, out of 408 students in this same inconsistent state.
    Uses the ORM (not raw SQL) to reuse _apply_bank_account()'s own IBAN-matching logic
    (base_iban-normalized search) rather than risk a raw acc_number string mismatch.
    Idempotent - documents whose bank is already trusted are simply re-confirmed as a no-op.
    """
    # install_mode=True: matches the context Odoo's own data-file loader always applies
    # (odoo/models.py's _load_records) - res_partner_bank's write() override refuses to
    # trust/untrust an account for SUPERUSER_ID unless install_mode is set (account's own
    # anti-cron safeguard), so calling _apply_bank_account() here plainly (no install_mode)
    # raises UserError("You do not have the rights to trust or un-trust accounts."). Only
    # caught because a real ./upgrade.sh run (no test_enable) exercises this path for real;
    # the original test coverage ran this migration under test_enable=True, which the same
    # check special-cases, and masked the bug.
    documents = env['ems.student.document'].with_context(install_mode=True).search([
        ('doc_type', '=', 'iban'), ('status', '=', 'approved'), ('doc_value', '!=', False),
    ])
    for document in documents:
        document._apply_bank_account()
    if documents:
        _logger.info(
            "Migration 18.0.0.22.0: re-applied trust for %d already-approved IBAN "
            "document(s), so their bank account has allow_out_payment=True.",
            len(documents))


def _backfill_null_course_enrollment_default(cr):
    """ems_course.is_enrollment_default was added to the model after ems_course_25_26 (the
    oldest row, created 2026-02-12, before ems.course.xml even declared this field) already
    existed, so its column was never backfilled and is raw SQL NULL - the only one of the 4
    courses in this state (confirmed via 'SELECT ... IS NULL'). This is invisible through the
    ORM (Boolean.convert_to_cache does bool(None) == False, same as a real False), which is
    exactly why converting data/custom/ems.course.xml to CSV in this version (noupdate=False,
    reapplied every upgrade - see CLAUDE.md's Data folder conventions) couldn't fix it on its
    own: the loader reads the current value as False through the ORM, sees the CSV's False
    matches, and skips issuing a write() - the raw NULL survives untouched forever. A one-time
    SQL backfill is the only way to actually correct it.
    """
    cr.execute("UPDATE ems_course SET is_enrollment_default = false WHERE is_enrollment_default IS NULL")
    if cr.rowcount:
        _logger.info(
            "Migration 18.0.0.22.0: backfilled %d ems_course row(s) with a legacy NULL "
            "is_enrollment_default to False.", cr.rowcount)


def _recompute_authorization_flags(env):
    # auth_image/auth_trip/auth_healt/auth_share are STORED, and until now they read
    # the enrollment of the course flagged as current. Between transitioning a study
    # and the global course flip the student holds no enrollment for the outgoing
    # course, so every signed authorization read as unsigned; they are now taken from
    # res.partner._ems_enrollment_in_force(). The stored values do not recompute on
    # their own because none of their dependencies changed - only the rule did - so
    # they are refreshed once here.
    students = env['res.partner'].search([('contact_type', 'in', ('student', 'applicant'))])
    students.modified(['sale_order_ids'])
    env.flush_all()
    _logger.info(
        "Migration 18.0.0.22.0: recomputed the authorization flags of %s contact(s).",
        len(students))


def _backfill_attendance_template_study_ids(cr):
    """Second half of the ems_attendance_template.study_id -> study_ids migration - see the
    matching _rename_old_attendance_template_study_column() in pre-migrate.py. Also backfills
    the two DOWNSTREAM related+store fields that read from the template's own study_ids
    (ems_attendance_session_header.study_ids, ems_attendance_session_line.study_ids):
    confirmed empirically (2026-08-05, on a dev box) that Odoo's own "auto-populate a brand
    new stored field" pass runs once, at schema-sync time - i.e. *before* this script gets a
    chance to backfill the template's own study_ids from study_id_old - so relying on Odoo to
    cascade the correct value down on its own does not work here; both downstream tables are
    derived directly via SQL joins instead (schedule -> template for session_header, then
    session_header -> session_line), the exact same join shape used to repair the dev box's
    own data by hand before this migration was written.
    """
    if not _column_exists(cr, 'ems_attendance_template', 'study_id_old'):
        return

    cr.execute("""
        INSERT INTO ems_attendance_template_ems_study_rel (ems_attendance_template_id, ems_study_id)
        SELECT id, study_id_old FROM ems_attendance_template WHERE study_id_old IS NOT NULL
        ON CONFLICT DO NOTHING
    """)
    template_rows = cr.rowcount

    cr.execute("""
        INSERT INTO ems_attendance_session_header_ems_study_rel (ems_attendance_session_header_id, ems_study_id)
        SELECT DISTINCT h.id, tr.ems_study_id
        FROM ems_attendance_session_header h
        JOIN ems_attendance_schedule s ON s.id = h.attendance_schedule_id
        JOIN ems_attendance_template_ems_study_rel tr ON tr.ems_attendance_template_id = s.attendance_template_id
        ON CONFLICT DO NOTHING
    """)
    header_rows = cr.rowcount

    cr.execute("""
        INSERT INTO ems_attendance_session_line_ems_study_rel (ems_attendance_session_line_id, ems_study_id)
        SELECT DISTINCT l.id, hr.ems_study_id
        FROM ems_attendance_session_line l
        JOIN ems_attendance_session_header_ems_study_rel hr ON hr.ems_attendance_session_header_id = l.attendance_session_id
        ON CONFLICT DO NOTHING
    """)
    line_rows = cr.rowcount

    cr.execute("ALTER TABLE ems_attendance_template DROP COLUMN study_id_old")
    _logger.info(
        "Migration 18.0.0.22.0: backfilled study_ids for %d attendance template(s), "
        "%d session header(s) and %d session line(s), then dropped study_id_old.",
        template_rows, header_rows, line_rows)


def _backfill_calendar_employee_and_course(env):
    """employee_id/course_id (added 18.0.0.22.0, see
    plans/course_transition_teacher_schedule_archival.md) are blank on every resource.calendar
    created before this migration - backfilled here from the same signal get_employee()'s
    reverse-search fallback already relies on: an employee whose *current* resource_calendar_id
    still points at this calendar. A calendar already orphaned by the pre-existing (teacher,
    course-name) re-minting cardinality bug (same plan) has no employee currently pointing at it
    and is left blank - unreachable via this signal, not a data-loss risk since nothing reads these
    fields yet (phase 4/5 of the same plan). course_id is set to the company's current course for
    every employee found this way, since a still-current calendar is by definition that course's
    own schedule.
    """
    calendars = env['resource.calendar'].search([
        ('employee_id', '=', False),
        ('is_framework', '=', False),
    ])
    updated = 0
    for calendar in calendars:
        employee = env['hr.employee'].search([('resource_calendar_id', '=', calendar.id)], limit=1)
        if not employee:
            continue
        calendar.write({
            'employee_id': employee.id,
            'course_id': employee.company_id.current_course_id.id,
        })
        updated += 1
    if updated:
        _logger.info(
            "Migration 18.0.0.22.0: backfilled employee_id/course_id on %d pre-existing "
            "resource.calendar record(s).", updated)


def migrate(cr, _version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    _enable_unaccent(cr)
    _archive_existing_ex_students(env)
    _backfill_google_ws_suspended(env)
    _backfill_attendance_status_id(cr)
    _backfill_special_type(cr)
    _backfill_iban_trust(env)
    _backfill_null_course_enrollment_default(cr)
    _recompute_authorization_flags(env)
    _backfill_attendance_template_study_ids(cr)
    _backfill_calendar_employee_and_course(env)
