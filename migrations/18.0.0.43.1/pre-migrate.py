import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    _convalidation_grade_type(cr)


def _convalidation_grade_type(cr):
    """Issue #738: a convalidated subject's "Without grade" checkbox becomes a grade type with a
    third option (a fixed 5). The new column is created and filled here from the old one, which
    then goes, so Odoo finds it already set and every line keeps how it was convalidated. Raw SQL
    on a pre-existing column, so pre-migrate. A clean install has no lines to carry over, so it
    needs no post_init_hook counterpart."""
    cr.execute("""
        SELECT 1 FROM information_schema.columns
         WHERE table_name = 'ems_convalidation_line' AND column_name = 'without_grade'
    """)
    if not cr.fetchone():
        return
    cr.execute("ALTER TABLE ems_convalidation_line ADD COLUMN IF NOT EXISTS grade_type varchar")
    cr.execute("""
        UPDATE ems_convalidation_line
           SET grade_type = CASE WHEN without_grade THEN 'without_grade' ELSE 'grade' END
    """)
    _logger.info("Set the grade type of %s convalidation lines", cr.rowcount)
    cr.execute("ALTER TABLE ems_convalidation_line DROP COLUMN without_grade")
