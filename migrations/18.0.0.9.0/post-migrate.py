import logging

_logger = logging.getLogger(__name__)

def migrate(cr, _version):
    # Populate auto_checkin_mode from the old auto_checkin boolean
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
        WHERE auto_checkin_mode IS NULL OR auto_checkin_mode = ''
    """)
    _logger.info("Migration: populated auto_checkin_mode from auto_checkin (%d rows)", cr.rowcount)
