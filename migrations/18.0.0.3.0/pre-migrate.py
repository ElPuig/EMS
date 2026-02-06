import logging

_logger = logging.getLogger(__name__)
def migrate(cr, version):
    table_rename = [
        ('ems_attendance_status', 'ems_attendance_session_line'),
        ('ems_attendance_session', 'ems_attendance_session_header'),
    ]

    for old_table, new_table in table_rename:
        _logger.info(f"Migration: Renaming table '{old_table}' to '{new_table}'.")
        cr.execute("SELECT 1 FROM information_schema.tables WHERE table_name = %s", (old_table,))
        if cr.fetchone():
            cr.execute('ALTER TABLE "%s" RENAME TO "%s"' % (old_table, new_table))           
        else:
            _logger.info(f"Migration: Table '{old_table}' not found, skipped.")

    column_rename = [
        ('ems_attendance_issue_status', 'attendance_status_id', 'attendance_session_line_id')
    ]

    for table, old_column, new_column in column_rename:
        _logger.info(f"Migration: Renaming column '{table}.{old_column}' to '{table}.{new_column}'.")
        cr.execute("SELECT 1 FROM information_schema.tables WHERE table_name = %s", (table,))
        if cr.fetchone():
            cr.execute('ALTER TABLE "%s" RENAME COLUMN "%s" TO "%s"' % (table, old_column, new_column))            
        else:
            _logger.info(f"Migration: Table '{old_table}' not found, skipped.")