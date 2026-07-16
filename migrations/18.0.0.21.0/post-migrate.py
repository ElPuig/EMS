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


def _sync_employee_photo_to_user(cr):
    # New in this version: hr.employee.image_1920 and the linked user's photo are always kept
    # equal from now on (see models/employees/employee.py and user.py write() overrides). This
    # feature has never been deployed before, in any form - no image_visibility/image_private
    # data exists to migrate - so the only thing needed here is a one-time copy from each
    # employee's current photo to their linked user, matching what write() will maintain
    # automatically from now on.
    env = api.Environment(cr, SUPERUSER_ID, {})
    cr.execute("""
        SELECT id FROM hr_employee WHERE user_id IS NOT NULL
    """)
    employees = env['hr.employee'].with_context(active_test=False).browse(
        row[0] for row in cr.fetchall())
    for employee in employees:
        employee.user_id.partner_id.image_1920 = employee.image_1920
    _logger.info(
        "Migration 18.0.0.21.0: synced 'image_1920' from %d employee(s) to their linked user.",
        len(employees),
    )


def migrate(cr, _version):
    _migrate_non_teaching_type(cr)
    _migrate_attendance_template_teacher_ids(cr)
    _seed_task_assignment_recipients(cr)
    _copy_teacher_photo_to_user(cr)
    _sync_employee_photo_to_user(cr)
