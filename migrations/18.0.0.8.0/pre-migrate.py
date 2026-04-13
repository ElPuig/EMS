import logging

_logger = logging.getLogger(__name__)

def migrate(cr, _version):
    cr.execute("""
        DELETE FROM ir_ui_view
        WHERE id IN (
            SELECT res_id FROM ir_model_data
            WHERE module = 'sale_project'
            AND model = 'ir.ui.view'
        )
    """)
    _logger.info("Migration: removed %d orphaned sale_project views", cr.rowcount)

    cr.execute("""
        DELETE FROM ir_model_data
        WHERE module = 'sale_project'
        AND model = 'ir.ui.view'
    """)
    _logger.info("Migration: cleaned %d sale_project ir_model_data entries", cr.rowcount)
