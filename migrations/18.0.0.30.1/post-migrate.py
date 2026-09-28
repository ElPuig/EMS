import logging

_logger = logging.getLogger(__name__)


def _drop_stale_data_request_menu_translations(cr):
    """The "Student Data" menu (menu_contact_data_requests) was renamed "Data request". The
    upgrade writes the new English name, but loads the .po files without overwriting existing
    values, so the Catalan and Spanish names kept the old label. Dropping those two keys here
    (post-migrate runs before the translations load) lets the .po fill them in again."""
    cr.execute("""
        UPDATE ir_ui_menu
           SET name = name - 'ca_ES' - 'es_ES'
         WHERE id = (SELECT res_id FROM ir_model_data
                      WHERE module = 'ems' AND name = 'menu_contact_data_requests')
    """)
    if cr.rowcount:
        _logger.info("Migration 18.0.0.30.1: reset the translations of the Data request menu.")


def migrate(cr, version):
    _drop_stale_data_request_menu_translations(cr)
