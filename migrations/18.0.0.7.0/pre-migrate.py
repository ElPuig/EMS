import logging

_logger = logging.getLogger(__name__)

def migrate(cr, _version):
    cr.execute("""
        UPDATE ir_model_data
        SET noupdate = False
        WHERE module = 'ems'
          AND model = 'res.partner.relation.type'
    """)
    _logger.info(
        "Migration: reset noupdate=False for %d ems relation type records in ir_model_data.",
        cr.rowcount,
    )

    cr.execute("""
        UPDATE ir_model_data
        SET name = 'relation_type_tutor'
        WHERE module = 'ems'
          AND model = 'res.partner.relation.type'
          AND name = 'relation_type_has_tutor'
    """)
    _logger.info(
        "Migration: renamed ir_model_data entry relation_type_has_tutor -> relation_type_tutor (%d rows).",
        cr.rowcount,
    )
