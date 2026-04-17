# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)

def migrate(cr, _version):
    # Clear arch_fs on account_peppol_response views so Odoo does not warn about missing source files
    cr.execute("UPDATE ir_ui_view SET arch_fs = NULL WHERE arch_fs LIKE 'account_peppol_response/%'")
    if cr.rowcount:
        _logger.info("Migration: cleared arch_fs on %d account_peppol_response view(s).", cr.rowcount)

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
