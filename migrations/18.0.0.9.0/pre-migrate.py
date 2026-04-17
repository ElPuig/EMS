# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)

def migrate(cr, _version):
    # Uninstall account_peppol and account_peppol_selfbilling (account_peppol_response is missing from filesystem)
    peppol_modules = ('account_peppol', 'account_peppol_selfbilling', 'account_peppol_response')
    cr.execute(
        "UPDATE ir_module_module SET state = 'uninstalled' WHERE name IN %s AND state != 'uninstalled'",
        (peppol_modules,)
    )
    if cr.rowcount:
        _logger.info("Migration: marked %d peppol module(s) as uninstalled.", cr.rowcount)

    cr.execute(
        "DELETE FROM ir_ui_view WHERE arch_fs LIKE ANY(ARRAY['account_peppol_response/%', 'account_peppol/%', 'account_peppol_selfbilling/%'])"
    )
    if cr.rowcount:
        _logger.info("Migration: removed %d orphaned peppol view(s).", cr.rowcount)

    cr.execute(
        "DELETE FROM ir_model_data WHERE module IN %s",
        (peppol_modules,)
    )
    if cr.rowcount:
        _logger.info("Migration: removed %d peppol ir_model_data record(s).", cr.rowcount)

    peppol_model_names = (
        'peppol.registration',
        'account_peppol.service',
        'account_peppol.service.wizard',
        'account.peppol.clarification',
        'account.peppol.response',
        'account.peppol.rejection.wizard',
    )
    cr.execute(
        "DELETE FROM ir_model WHERE model IN %s",
        (peppol_model_names,)
    )
    if cr.rowcount:
        _logger.info("Migration: removed %d orphaned PEPPOL ir_model record(s).", cr.rowcount)

    # Migrate res_company.auto_checkin (Boolean) → auto_checkin_mode (Selection)
    # Must run in pre-migrate: Odoo fills the default 'disabled' for all rows between
    # pre and post, so the UPDATE would never apply if done in post-migrate.
    cr.execute("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'res_company' AND column_name = 'auto_checkin'
    """)
    if cr.fetchone():
        cr.execute("""
            ALTER TABLE res_company
            ADD COLUMN IF NOT EXISTS auto_checkin_mode VARCHAR
        """)
        cr.execute("""
            UPDATE res_company
            SET auto_checkin_mode = CASE
                WHEN auto_checkin = TRUE THEN 'first'
                ELSE                          'disabled'
            END
        """)
        _logger.info("Migration: populated auto_checkin_mode from auto_checkin (%d rows).", cr.rowcount)
        cr.execute("ALTER TABLE res_company DROP COLUMN auto_checkin")
        _logger.info("Migration: dropped column res_company.auto_checkin.")
    else:
        _logger.info("Migration: column 'auto_checkin' not found in res_company, skipped.")

    # Migrate attendance_template.group_id → group_ids (Many2many)
    cr.execute("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'ems_attendance_template' AND column_name = 'group_id'
    """)
    if cr.fetchone():
        cr.execute("""
            CREATE TABLE IF NOT EXISTS ems_attendance_template_ems_group_rel (
                ems_attendance_template_id INTEGER NOT NULL
                    REFERENCES ems_attendance_template(id) ON DELETE CASCADE,
                ems_group_id INTEGER NOT NULL
                    REFERENCES ems_group(id) ON DELETE CASCADE,
                PRIMARY KEY (ems_attendance_template_id, ems_group_id)
            )
        """)
        cr.execute("""
            INSERT INTO ems_attendance_template_ems_group_rel (ems_attendance_template_id, ems_group_id)
            SELECT id, group_id FROM ems_attendance_template
            WHERE group_id IS NOT NULL
            ON CONFLICT DO NOTHING
        """)
        _logger.info("Migration: migrated %d attendance_template group_id → group_ids.", cr.rowcount)
    else:
        _logger.info("Migration: ems_attendance_template.group_id not found, skipped.")

    # Migrate attendance_session_header.group_id → group_ids (Many2many)
    cr.execute("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'ems_attendance_session_header' AND column_name = 'group_id'
    """)
    if cr.fetchone():
        cr.execute("""
            CREATE TABLE IF NOT EXISTS ems_attendance_session_header_ems_group_rel (
                ems_attendance_session_header_id INTEGER NOT NULL
                    REFERENCES ems_attendance_session_header(id) ON DELETE CASCADE,
                ems_group_id INTEGER NOT NULL
                    REFERENCES ems_group(id) ON DELETE CASCADE,
                PRIMARY KEY (ems_attendance_session_header_id, ems_group_id)
            )
        """)
        cr.execute("""
            INSERT INTO ems_attendance_session_header_ems_group_rel (ems_attendance_session_header_id, ems_group_id)
            SELECT id, group_id FROM ems_attendance_session_header
            WHERE group_id IS NOT NULL
            ON CONFLICT DO NOTHING
        """)
        _logger.info("Migration: migrated %d attendance_session_header group_id → group_ids.", cr.rowcount)
    else:
        _logger.info("Migration: ems_attendance_session_header.group_id not found, skipped.")

    # Migrate resource_calendar_attendance.group_id → group_ids (Many2many)
    cr.execute("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'resource_calendar_attendance' AND column_name = 'group_id'
    """)
    if cr.fetchone():
        cr.execute("""
            CREATE TABLE IF NOT EXISTS resource_calendar_attendance_ems_group_rel (
                attendance_id INTEGER NOT NULL
                    REFERENCES resource_calendar_attendance(id) ON DELETE CASCADE,
                group_id INTEGER NOT NULL
                    REFERENCES ems_group(id) ON DELETE CASCADE,
                PRIMARY KEY (attendance_id, group_id)
            )
        """)
        cr.execute("""
            INSERT INTO resource_calendar_attendance_ems_group_rel (attendance_id, group_id)
            SELECT id, group_id FROM resource_calendar_attendance
            WHERE group_id IS NOT NULL
            ON CONFLICT DO NOTHING
        """)
        _logger.info("Migration: migrated %d resource_calendar_attendance group_id → group_ids.", cr.rowcount)
    else:
        _logger.info("Migration: resource_calendar_attendance.group_id not found, skipped.")

    column_rename = [
        ('ems_group', 'ems_shift', 'shift'),
    ]

    for table, old_column, new_column in column_rename:
        cr.execute(
            "SELECT 1 FROM information_schema.columns WHERE table_name = %s AND column_name = %s",
            (table, old_column)
        )
        if cr.fetchone():
            cr.execute('ALTER TABLE "%s" RENAME COLUMN "%s" TO "%s"' % (table, old_column, new_column))
            _logger.info("Migration: renamed column '%s.%s' → '%s.%s'.", table, old_column, table, new_column)
        else:
            _logger.info("Migration: column '%s.%s' not found, skipped.", table, old_column)
