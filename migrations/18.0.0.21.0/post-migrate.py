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


def migrate(cr, _version):
    _migrate_non_teaching_type(cr)
    _migrate_attendance_template_teacher_ids(cr)
    _seed_task_assignment_recipients(cr)
