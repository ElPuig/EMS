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

    courses = [
        (2025, 2026, 'ems_course_25_26'),
        (2026, 2027, 'ems_course_26_27'),
        (2027, 2028, 'ems_course_27_28'),
        (2028, 2029, 'ems_course_28_29'),
    ]

    for start, end, ext_id in courses:
        cr.execute("""
            UPDATE ir_model_data
            SET name = %s, noupdate = true
            WHERE module = 'ems'
              AND model = 'ems.course'
              AND name != %s
              AND res_id = (SELECT id FROM ems_course WHERE start = %s AND "end" = %s)
        """, (ext_id, ext_id, start, end))
        if cr.rowcount:
            _logger.info("Migration: renamed ir_model_data for ems.course %s-%s -> %s (%d rows)", start, end, ext_id, cr.rowcount)

        cr.execute("""
            INSERT INTO ir_model_data (module, name, model, res_id, noupdate)
            SELECT 'ems', %s, 'ems.course', ec.id, true
            FROM ems_course ec
            WHERE ec.start = %s AND ec."end" = %s
              AND NOT EXISTS (
                  SELECT 1 FROM ir_model_data imd
                  WHERE imd.module = 'ems'
                    AND imd.model = 'ems.course'
                    AND imd.res_id = ec.id
              )
        """, (ext_id, start, end))
        if cr.rowcount:
            _logger.info("Migration: inserted ir_model_data for ems.course %s-%s as %s (%d rows)", start, end, ext_id, cr.rowcount)
