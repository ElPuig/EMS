# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)


def _revoke_implied_block_admin(cr):
    # group_academic_admin used to imply group_secretary_admin/group_quality_admin/
    # group_coexistence_admin/group_settings_admin (see security/groups.xml), so any user
    # holding Academic Administrator also silently held Administrator in every other block.
    # That implication is removed in this same version so the blocks stay independent -
    # revoke the memberships that existed only because of it, for every user except
    # root/admin (who keep full access to every block through explicit membership, added
    # directly on each of those groups instead).
    block_admin_groups = (
        'group_secretary_admin',
        'group_quality_admin',
        'group_coexistence_admin',
        'group_settings_admin',
    )
    for group_name in block_admin_groups:
        cr.execute("""
            DELETE FROM res_groups_users_rel
            WHERE gid = (
                SELECT res_id FROM ir_model_data WHERE module = 'ems' AND name = %s
            )
            AND uid IN (
                SELECT uid FROM res_groups_users_rel
                WHERE gid = (
                    SELECT res_id FROM ir_model_data WHERE module = 'ems' AND name = 'group_academic_admin'
                )
            )
            AND uid NOT IN (
                SELECT res_id FROM ir_model_data WHERE module = 'base' AND name IN ('user_root', 'user_admin')
            )
        """, (group_name,))
        _logger.info(
            "Migration 18.0.0.21.0: revoked %d user(s) from 'ems.%s' that held it only "
            "through the removed group_academic_admin implication.", cr.rowcount, group_name,
        )


def migrate(cr, _version):
    _revoke_implied_block_admin(cr)

    # 'resource_calendar_attendance.non_teaching' changes from a Selection (varchar column) to a
    # Many2one (integer FK) to the new 'ems.non_teaching_type' model. Odoo's own schema sync cannot
    # convert existing varchar codes ('BR', 'G'...) into integer foreign keys, so the old column is
    # renamed out of the way here, before Odoo creates the new 'non_teaching' integer column for the
    # Many2one field. The backfill (mapping old codes to the new model's records, using the seed data
    # loaded during this same upgrade) happens in post-migrate.py, once both the new column and the
    # new model's rows actually exist.
    cr.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'resource_calendar_attendance' AND column_name = 'non_teaching'
    """)
    if cr.fetchone():
        cr.execute("ALTER TABLE resource_calendar_attendance RENAME COLUMN non_teaching TO non_teaching_legacy")
        _logger.info("Migration 18.0.0.21.0: renamed 'resource_calendar_attendance.non_teaching' to 'non_teaching_legacy' ahead of its Many2one conversion.")

    # 'ems.attendance_template.teacher_id' (Many2one) becomes 'teacher_ids' (Many2many), to support
    # real co-teaching. Odoo's schema sync DROPS a removed field's column outright as soon as it
    # notices the field is gone (ir.model.fields.unlink() -> _drop_column()) — this happens before
    # post-migrate.py ever runs, so the old teacher_id values must be saved off here first, ahead of
    # that drop, exactly like 'non_teaching' above. The backfill into the new
    # 'ems_attendance_template_teacher_rel' relation table happens in post-migrate.py, once that table
    # actually exists.
    cr.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'ems_attendance_template' AND column_name = 'teacher_id'
    """)
    if cr.fetchone():
        cr.execute("ALTER TABLE ems_attendance_template RENAME COLUMN teacher_id TO teacher_id_legacy")
        _logger.info("Migration 18.0.0.21.0: renamed 'ems_attendance_template.teacher_id' to 'teacher_id_legacy' ahead of its Many2many conversion.")

    # The 'group_head_of_department' res.groups XML ID is renamed to 'group_department_chief', to
    # better reflect the role and because it now also grants write access to 'ems.group'. Renamed
    # here, before the module's data files reload, so the data loader resolves the new XML ID against
    # the existing record (same res.groups row, same users already assigned) instead of creating a
    # disconnected new one.
    cr.execute(
        "UPDATE ir_model_data SET name = %s WHERE module = 'ems' AND name = %s",
        ('group_department_chief', 'group_head_of_department'),
    )
    _logger.info("Migration 18.0.0.21.0: renamed XML ID 'group_head_of_department' → 'group_department_chief'.")
