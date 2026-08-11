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


def _seed_enrollment_default(env):
    """is_enrollment_default stopped being a column of data/custom/ems.course.csv in this
    version: it is live state the centre moves when it opens the next campaign, and a
    synced column reverted that move on every upgrade. Installations that had none flagged
    (or whose only flag came from the file and was a legacy NULL, see the backfill above)
    get one seeded; the helper leaves an already-flagged instance alone.
    """
    course = env['ems.course']._ems_seed_enrollment_default()
    if course:
        _logger.info(
            "Migration 18.0.0.22.0: no course was flagged as the enrollment default; "
            "seeded '%s'.", course.name)


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


def _backfill_missing_teacher_calendars(env):
    """See plans/calendar_driven_attendance_templates.md's "Migration requirement" section - a
    teacher already in the database before commit bc29e04b (18.0.0.20.0, 2026-07-12, hr.employee.
    create()'s own auto-calendar override) - or one whose employee_type only became 'teacher'
    later, which write() has no equivalent logic for - can be missing a personal resource.calendar
    entirely. '_write_teacher_schedule()' silently no-ops on an empty resource_calendar_id, which
    is how this surfaced: a real import left a real teacher (Óscar Bagan, this dev DB) with real
    ems.teaching rows but an empty Schedule tab. Mirrors hr.employee.create()'s own logic exactly
    via the shared '_ems_create_personal_calendar' helper (models/employees/employee.py) - active
    or archived, since an archived teacher's historical schedule should still be attributable to a
    real calendar, not silently unattributable forever."""
    employees = env['hr.employee'].with_context(active_test=False).search([
        ('employee_type', '=', 'teacher'), ('resource_calendar_id', '=', False),
    ])
    if employees:
        employees._ems_create_personal_calendar()
        _logger.info(
            "Migration 18.0.0.22.0: created a personal resource.calendar for %d teacher(s) missing one.",
            len(employees))


def _restore_attendance_schedule_student_rel(cr):
    """Reads back '_ems_migration_template_student_backup' (see
    'pre-migrate.py::_backup_attendance_template_student_rel') now that ems.attendance_schedule's
    own 'student_ids' relation table exists, and copies each (template, student) pair onto EVERY
    one of that template's current schedule lines - matching the exact effective roster every line
    already had under the old, template-wide field (every line shared one roster), so day one after
    this upgrade looks identical to a teacher/admin; they're then free to customize a line's own
    roster afterward, which is the whole point of this move (see
    plans/calendar_driven_attendance_templates.md, point 1). 'ON CONFLICT DO NOTHING' guards
    against a re-run of this migration, not against any real duplication risk in the join itself
    (each schedule line belongs to exactly one template)."""
    cr.execute("""
        SELECT to_regclass('_ems_migration_template_student_backup')
    """)
    if not cr.fetchone()[0]:
        return
    cr.execute("""
        INSERT INTO ems_attendance_schedule_res_partner_rel (ems_attendance_schedule_id, res_partner_id)
        SELECT DISTINCT schedule.id, backup.student_id
        FROM _ems_migration_template_student_backup backup
        JOIN ems_attendance_schedule schedule ON schedule.attendance_template_id = backup.template_id
        ON CONFLICT DO NOTHING
    """)
    _logger.info(
        "Migration 18.0.0.22.0: restored %d ems.attendance_schedule.student_ids row(s) from the "
        "pre-migrate backup of ems.attendance_template.student_ids.", cr.rowcount)
    cr.execute("DROP TABLE _ems_migration_template_student_backup")
    # NOTE: confirmed empirically (2026-08-11) that Odoo's own schema sync does NOT drop a
    # Many2many's old relation table on its own just because the field was removed from the model
    # (unlike a plain column, which IS dropped - see the "Gotcha confirmed while converting
    # ems.course.xml" style note in CLAUDE.md for that different case) - the old table would
    # otherwise sit around forever as orphaned, inaccessible garbage now that the restore above
    # has copied everything it held into the new field.
    cr.execute("DROP TABLE IF EXISTS ems_attendance_template_res_partner_rel")


def _regenerate_attendance_templates_from_calendars(env):
    """See plans/calendar_driven_attendance_templates.md's "Production migration sequencing"
    section, step 1. An earlier version of this migration tried to detect and merge exact-duplicate
    templates one pair at a time (`ems.attendance_template._check_unique_teaching_assignment`,
    point 2, would otherwise reject data that predates it) - abandoned (developer's own call,
    2026-08-11) once it became clear this whole class of stale/orphaned data is moot the instant
    every active template is archived and rebuilt from each teacher's CURRENT
    resource.calendar.attendance rows anyway: an exact duplicate can never survive a rebuild that
    groups by (subject, group-set, teacher-set), by construction. `regenerate_all_from_calendars()`
    (ems.attendance_template) does the archive+rebuild; called here, inside this same migration, so
    it finishes before the Odoo service is reachable by any user after this upgrade - nobody ever
    sees an intermediate state with no active templates.

    This IS a breaking change: a teacher whose working schedule was never (re)loaded onto their
    personal `resource.calendar` (e.g. one of the 8 pre-2026-07-12 teachers `_backfill_missing_
    teacher_calendars` above gives a calendar to, but not a schedule) ends up with zero active
    templates after this migration - they will not be able to take attendance until their schedule
    is imported/entered for real. There is no way to route around this: the whole point of points
    1-4 is that a template only ever exists as a consequence of a real calendar.

    A SECOND, narrower case of the same breaking change: `regenerate_all_from_calendars()` itself
    drops one side of any unresolved room conflict it finds (see that method's own docstring, and
    `ems.attendance_template._drop_unresolved_conflicts` - a real, recurring pattern confirmed by
    the developer 2026-08-11: a support/reinforcement teacher recorded under their own subject_id,
    physically sharing a room/slot with the group's main teacher, which the general-purpose
    co-teaching detection can't recognise since the subject genuinely differs). Every dropped entry
    is logged below by name so whoever runs this migration knows exactly which pairs need a manual
    fix afterward (Employees > Schedule tab) - deliberately not guessed at automatically."""
    skipped = env['ems.attendance_template'].regenerate_all_from_calendars()
    _logger.info(
        "Migration 18.0.0.22.0: archived every pre-existing ems.attendance_template and "
        "regenerated a fresh, calendar-backed set from each teacher's current working schedule.")
    if not skipped:
        return

    weekdays = dict(env['ems.attendance_schedule'].weekdays_selection)
    for item in skipped:
        entry, other = item['entry'], item['conflicts_with_entry']
        _logger.warning(
            "Migration 18.0.0.22.0: SKIPPED regenerating a template for %s (%s, %s %s-%s, %s) - "
            "unresolved room conflict with %s (%s, %s %s-%s, %s). This is not corrected "
            "automatically - review both teachers' real working schedules by hand and re-sync "
            "the one that's wrong.",
            item['teacher'].display_name, env['ems.subject'].browse(entry['subject_id']).display_name,
            weekdays.get(entry['dayofweek']), entry['hour_from'], entry['hour_to'],
            env['ems.space'].browse(entry['space_id']).display_name,
            item['conflicts_with_teacher'].display_name,
            env['ems.subject'].browse(other['subject_id']).display_name,
            weekdays.get(other['dayofweek']), other['hour_from'], other['hour_to'],
            env['ems.space'].browse(other['space_id']).display_name,
        )
    _logger.warning(
        "Migration 18.0.0.22.0: %d entrie(s) skipped due to unresolved room conflicts - see the "
        "warnings above for exactly which ones and what each one conflicted with.", len(skipped))


def migrate(cr, _version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    _enable_unaccent(cr)
    _archive_existing_ex_students(env)
    _backfill_google_ws_suspended(env)
    _backfill_attendance_status_id(cr)
    _backfill_special_type(cr)
    _backfill_iban_trust(env)
    _backfill_null_course_enrollment_default(cr)
    _seed_enrollment_default(env)
    _recompute_authorization_flags(env)
    _backfill_attendance_template_study_ids(cr)
    _backfill_calendar_employee_and_course(env)
    _backfill_missing_teacher_calendars(env)
    _restore_attendance_schedule_student_rel(cr)
    _regenerate_attendance_templates_from_calendars(env)
