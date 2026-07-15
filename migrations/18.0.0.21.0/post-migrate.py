# -*- coding: utf-8 -*-
import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)

# Activity types whose recipients used to be derived from a security group, now
# configured in Academic Management > Configuration > Task Assignment.
SEEDED_TASK_ASSIGNMENTS = [
    ('mail_activity_student_document_review', 'group_secretary'),
    ('mail_activity_enrollment_comment', 'group_secretary'),
]


def _migrate_non_teaching_type(cr):
    # By this point Odoo has already created the new 'non_teaching' integer/FK column (from the
    # Many2one field definition) and loaded 'ems.non_teaching_type''s seed data
    # (data/main/ems.non_teaching_type.csv). Backfill every real attendance row by joining the old
    # varchar code (saved off in pre-migrate.py as 'non_teaching_legacy') to the new model's 'code',
    # then drop the legacy column — see pre-migrate.py for why this is split across both phases.
    cr.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'resource_calendar_attendance' AND column_name = 'non_teaching_legacy'
    """)
    if not cr.fetchone():
        return

    cr.execute("""
        UPDATE resource_calendar_attendance rca
        SET non_teaching = nt.id
        FROM ems_non_teaching_type nt
        WHERE rca.non_teaching_legacy = nt.code
    """)
    _logger.info("Migration 18.0.0.21.0: backfilled 'non_teaching' on %d attendance row(s) from their legacy code.", cr.rowcount)

    cr.execute("""
        SELECT rca.id, rca.non_teaching_legacy FROM resource_calendar_attendance rca
        WHERE rca.non_teaching_legacy IS NOT NULL AND rca.non_teaching IS NULL
    """)
    unmatched = cr.fetchall()
    if unmatched:
        _logger.warning(
            "Migration 18.0.0.21.0: %d attendance row(s) had a 'non_teaching_legacy' code with no matching "
            "ems.non_teaching_type (needs manual review): %s", len(unmatched), unmatched,
        )

    cr.execute("ALTER TABLE resource_calendar_attendance DROP COLUMN non_teaching_legacy")
    _logger.info("Migration 18.0.0.21.0: dropped 'resource_calendar_attendance.non_teaching_legacy'.")


def _migrate_attendance_template_teacher_ids(cr):
    # 'ems.attendance_template.teacher_id' (Many2one) becomes 'teacher_ids' (Many2many), to support
    # real co-teaching (several teachers sharing one template/session). By this point Odoo has already
    # created the new 'ems_attendance_template_teacher_rel' relation table from the Many2many field
    # definition, and pre-migrate.py has saved the old values off as 'teacher_id_legacy' (ahead of
    # Odoo's own schema sync dropping the original 'teacher_id' column) — copy them into the new
    # relation table, then drop the legacy column.
    cr.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'ems_attendance_template' AND column_name = 'teacher_id_legacy'
    """)
    if not cr.fetchone():
        return

    cr.execute("""
        INSERT INTO ems_attendance_template_teacher_rel (ems_attendance_template_id, hr_employee_id)
        SELECT id, teacher_id_legacy FROM ems_attendance_template WHERE teacher_id_legacy IS NOT NULL
        ON CONFLICT DO NOTHING
    """)
    _logger.info("Migration 18.0.0.21.0: migrated %d 'ems.attendance_template.teacher_id' value(s) to 'teacher_ids'.", cr.rowcount)

    cr.execute("ALTER TABLE ems_attendance_template DROP COLUMN teacher_id_legacy")
    _logger.info("Migration 18.0.0.21.0: dropped 'ems_attendance_template.teacher_id_legacy'.")


def _seed_task_assignment_recipients(cr):
    env = api.Environment(cr, SUPERUSER_ID, {})

    # Seed the new recipient lists with whoever receives these tasks today, so nobody
    # silently stops being notified on upgrade. Members of the source group included the
    # administrators only through the implied_ids chain (group_academic_admin used to
    # imply group_secretary_admin, which implied group_secretary) - that implication was
    # removed in this same version (see security/groups.xml), but any admin already
    # notified through it is kept here on purpose so the behaviour does not change under
    # anyone's feet; the centre removes them from the new screen when it sees fit.
    #
    # OdooBot is the one exception: it is the system user behind crons and imports, its
    # inbox is read by nobody, and it only ever landed in the group through that same
    # chain. Seeding it would just create tasks nobody will ever see.
    for type_xmlid, group_xmlid in SEEDED_TASK_ASSIGNMENTS:
        activity_type = env.ref(f'ems.{type_xmlid}', raise_if_not_found=False)
        group = env.ref(f'ems.{group_xmlid}', raise_if_not_found=False)
        if not activity_type or not group:
            _logger.warning(
                "Task Assignment: could not seed %s from %s (record not found).",
                type_xmlid, group_xmlid)
            continue

        # data/main/ems.mail_activity_type.xml declares the flag, but that file is
        # noupdate="1" and these records already exist here, so Odoo skips it: the
        # flag has to be set by hand on an existing database.
        activity_type.ems_task_assignment = True

        # Idempotent: never overwrite a list the centre has already configured.
        if activity_type.ems_assignee_ids:
            continue

        users = group.users.filtered(lambda user: user.id != SUPERUSER_ID)
        activity_type.ems_assignee_ids = [(6, 0, users.ids)]
        _logger.info(
            "Task Assignment: seeded %s with %d user(s): %s",
            type_xmlid, len(users), ', '.join(users.mapped('login')) or '-')


def _remap_image_visibility_values(cr):
    # The photo-visibility feature's selection values changed mid-development, before ever
    # shipping (all/teachers/directive -> public/private/no_photo, with the 'teachers' tier
    # dropped entirely). Must run before anything below reads image_visibility - an old,
    # unmapped value would just silently fail every `== 'public'`/`== 'private'` check.
    # 'teachers' -> 'public': it's the tier being removed, and 'public' is the least
    # surprising choice (doesn't hide a photo from anyone who could already see it).
    cr.execute("""
        UPDATE res_users SET image_visibility = CASE image_visibility
            WHEN 'all' THEN 'public'
            WHEN 'teachers' THEN 'public'
            WHEN 'directive' THEN 'private'
            ELSE image_visibility
        END
        WHERE image_visibility IN ('all', 'teachers', 'directive')
    """)
    _logger.info(
        "Migration 18.0.0.21.0: remapped %d 'res.users.image_visibility' value(s) to the new "
        "public/private/no_photo selection.", cr.rowcount,
    )


def _copy_teacher_photo_to_user(cr):
    # Before this version, creating/linking a teacher's/ASP's EMS user (via the
    # "Create Google account" button, see google_workspace_integration.py) never
    # copied the employee's photo onto the new res.users. Backfill it once here for
    # whoever is already linked. Uses the ORM (not raw SQL) because image_1920 is an
    # attachment-backed field (ir_attachment, not a plain column) on both hr.employee
    # and res.partner - only Model.write() creates/dedupes that attachment correctly.
    env = api.Environment(cr, SUPERUSER_ID, {})
    # image_1920 is attachment-backed (no column, see Binary/Image field's
    # attachment=True), so it can't be searched with a normal ORM domain -
    # find candidates straight from ir_attachment instead.
    cr.execute("""
        SELECT e.id FROM hr_employee e
        JOIN ir_attachment a
            ON a.res_model = 'hr.employee' AND a.res_field = 'image_1920' AND a.res_id = e.id
        WHERE e.employee_type IN ('teacher', 'asp') AND e.user_id IS NOT NULL
    """)
    employees = env['hr.employee'].browse(row[0] for row in cr.fetchall())
    copied = 0
    for employee in employees:
        user = employee.user_id
        # Never overwrite a photo the user already has - except the SVG initials
        # avatar Odoo auto-generates on res.users/res.partner when no image is set
        # (see res.users.create()/avatar.mixin._avatar_generate_svg()): that one is
        # a placeholder, not a real photo, and should still be replaced.
        cr.execute("""
            SELECT mimetype FROM ir_attachment
            WHERE res_model = 'res.partner' AND res_field = 'image_1920' AND res_id = %s
        """, (user.partner_id.id,))
        row = cr.fetchone()
        has_real_photo = bool(row) and row[0] != 'image/svg+xml'
        if not has_real_photo:
            user.image_1920 = employee.image_1920
            copied += 1
    _logger.info(
        "Migration 18.0.0.21.0: copied photo from %d teacher/ASP employee(s) to their linked user.",
        copied,
    )


def _recompute_employee_image_1920(cr):
    # New in this version: hr.employee.image_1920 becomes a compute+store field driven by
    # image_private/image_visibility (see models/employees/employee.py, the teacher photo
    # visibility feature), with a fallback to the linked user's photo (effective_photo) for
    # employees who never had a photo of their own directly on hr.employee - common for anyone
    # whose photo only ever lived on their res.users/res.partner record.
    #
    # Odoo does not retroactively recompute an already-populated store=True field just because
    # its compute function changed - only genuinely new/NULL stored values get recomputed
    # automatically during the schema sync that runs before this script. image_1920 already
    # existed before this version, so every employee keeps whatever value it held pre-upgrade
    # (often blank) until something explicitly recomputes it - do that here, once, for everyone.
    #
    # CRITICAL ORDERING - DO NOT SKIP THE BACKFILL BELOW: image_private is a brand new field,
    # empty for every employee at this point. An employee who already has their own photo
    # directly on hr.employee (attachment on image_1920) but has NO linked user (so no fallback
    # either) would have that photo permanently DELETED by the recompute below if image_private
    # isn't seeded from their legacy image_1920 value first (Binary field writes of a falsy
    # value delete the underlying ir_attachment). This is not a hypothetical: an earlier version
    # of this script skipped the backfill and destroyed real, irrecoverable employee photos in
    # development before being caught - keep both steps, in this order, always.
    env = api.Environment(cr, SUPERUSER_ID, {})
    cr.execute("""
        SELECT DISTINCT res_id FROM ir_attachment
        WHERE res_model = 'hr.employee' AND res_field = 'image_1920'
    """)
    employees_with_legacy_photo = env['hr.employee'].with_context(active_test=False).browse(
        row[0] for row in cr.fetchall())
    backfilled = 0
    for employee in employees_with_legacy_photo:
        if not employee.image_private:
            # Read BEFORE anything below recomputes image_1920 - at this point it still holds
            # each employee's legacy, pre-upgrade value.
            employee.image_private = employee.image_1920
            backfilled += 1

    employees = env['hr.employee'].with_context(active_test=False).search([])
    # image_visibility is itself compute+store, mirroring user_id.image_visibility - a raw SQL
    # UPDATE on res_users (see _remap_image_visibility_values) does not trigger the ORM's
    # dependency-based recompute, so hr_employee.image_visibility can still hold a stale,
    # no-longer-valid string (e.g. 'all'/'directive') at this point. Recompute it explicitly
    # before image_1920, which depends on it.
    employees._compute_image_visibility()
    employees._compute_image_1920()
    _logger.info(
        "Migration 18.0.0.21.0: backfilled 'image_private' from the legacy 'image_1920' for %d "
        "employee(s), then recomputed 'image_1920' (photo visibility fallback) for %d "
        "employee(s) total.", backfilled, len(employees),
    )


def _sync_partner_photo_from_employee(cr):
    # Mirrors, once for existing data, what res.users.write()'s _sync_partner_photo
    # (models/employees/user.py) will do from now on every time "My Profile" is saved: back up
    # each employee-linked contact's current (real, pre-feature) photo into its own
    # image_private before anything overwrites image_1920, then push whatever
    # hr.employee.image_1920 now resolves to (real photo, or the initials placeholder - see
    # _recompute_employee_image_1920 above, which must run before this). Only touches contacts
    # actually linked to an employee - not every res.partner in the database.
    env = api.Environment(cr, SUPERUSER_ID, {})
    cr.execute("""
        SELECT DISTINCT u.id FROM res_users u
        JOIN hr_employee e ON e.user_id = u.id
    """)
    users = env['res.users'].browse(row[0] for row in cr.fetchall())
    backfilled = 0
    for user in users:
        partner = user.partner_id.sudo()
        employee = user.employee_id.sudo()
        if not partner.image_private:
            partner.image_private = partner.image_1920
            backfilled += 1
        partner.image_1920 = employee.image_1920
    _logger.info(
        "Migration 18.0.0.21.0: backfilled res.partner.image_private for %d employee-linked "
        "contact(s) and synced 'image_1920' for %d user(s) total.", backfilled, len(users),
    )


def migrate(cr, _version):
    _migrate_non_teaching_type(cr)
    _migrate_attendance_template_teacher_ids(cr)
    _seed_task_assignment_recipients(cr)
    _remap_image_visibility_values(cr)
    _copy_teacher_photo_to_user(cr)
    _recompute_employee_image_1920(cr)
    _sync_partner_photo_from_employee(cr)
