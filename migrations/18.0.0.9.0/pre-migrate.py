# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)

def migrate(cr, _version):
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
