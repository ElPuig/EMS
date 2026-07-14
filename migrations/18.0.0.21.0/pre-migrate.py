# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, _version):
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
