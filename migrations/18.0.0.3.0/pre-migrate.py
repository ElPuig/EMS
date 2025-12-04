import logging

_logger = logging.getLogger(__name__)
def migrate(cr, version):
    operations = [
        ('ems_attendance_status', 'ems_attendance_session_status'),
        ('ems_attendance_session', 'ems_attendance_session_header'),
    ]

    for old_table, new_table in operations:
        _logger.info(f"Migration: Renaming table '{old_table}' to '{new_table}'.")
        cr.execute("SELECT 1 FROM information_schema.tables WHERE table_name = %s", (old_table,))
        if cr.fetchone():
            cr.execute('ALTER TABLE "%s" RENAME TO "%s"' % (old_table, new_table))
            cr.execute("""
                UPDATE ir_model_data
                SET name = %s
                WHERE module = 'mi_modulo' AND name = %s
            """, ('model_' + new_table, 'model_' + old_table))
        else:
            _logger.info(f"Migration: Table '{old_table}' not found, skipped.")