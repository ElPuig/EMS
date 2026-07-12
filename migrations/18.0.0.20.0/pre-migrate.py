# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)

def migrate(cr, _version):
    # 'res_company.default_schedule_framework_id' is required. Backfill any company that doesn't
    # have it set yet with the module's own default framework, before Odoo applies the NOT NULL
    # constraint while reloading the field definitions.
    cr.execute("""
        UPDATE res_company SET default_schedule_framework_id = (
            SELECT res_id FROM ir_model_data
            WHERE module = 'ems' AND name = 'schedule_framework_default'
        )
        WHERE default_schedule_framework_id IS NULL
    """)
    if cr.rowcount:
        _logger.info("Migration: set default_schedule_framework_id on %d company(ies).", cr.rowcount)
