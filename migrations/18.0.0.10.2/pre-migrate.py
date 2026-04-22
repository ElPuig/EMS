import logging

_logger = logging.getLogger(__name__)

_SUBJECTS = [
    'subject_OPT1', 'subject_OPT2', 'subject_OPT3',
    'subject_OPT4', 'subject_OPT5', 'subject_OPT6',
]

_STUDIES = [
    'study_btx_171_2022', 'study_eso_175_2022'
]

def migrate(cr, version):
    # SUBJECTS
    placeholders = ', '.join(['%s'] * len(_SUBJECTS))
    cr.execute(
        f"""
        UPDATE ir_model_data
           SET module = '__import__'
         WHERE module = 'ems'
           AND model  = 'ems.subject'
           AND name IN ({placeholders})
        """,
        _SUBJECTS,
    )
    _logger.info(
        "Migration: updated module ems → __import__ for %d OPT subject external IDs.",
        cr.rowcount,
    )

    # STUDIES
    placeholders = ', '.join(['%s'] * len(_STUDIES))
    cr.execute(
        f"""
        UPDATE ir_model_data
           SET module = 'ems'
         WHERE module = '__import__'
           AND model  = 'ems.study'
           AND name IN ({placeholders})
        """,
        _STUDIES,
    )
    _logger.info(
        "Migration: updated module __import__ → ems for %d ESO and BTX studies external IDs.",
        cr.rowcount,
    )
