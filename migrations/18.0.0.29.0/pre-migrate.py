import logging

_logger = logging.getLogger(__name__)


def _freeze_custom_spaces(cr):
    """ems.space joins res.company._EMS_LIVING_CUSTOM_DATA_MODELS in this version, but that
    freeze only runs from _register_hook(), after this upgrade's data files have already
    reloaded - so data/custom/ems.space.csv would still revert every classroom renamed through
    the app one last time. Freezing the existing '__import__' xmlids here, before the reload,
    prevents it. Raw SQL on pre-existing columns only, so it is safe in pre-migrate."""
    cr.execute("""
        UPDATE ir_model_data SET noupdate = TRUE
        WHERE module = '__import__' AND model = 'ems.space' AND COALESCE(noupdate, FALSE) = FALSE
    """)
    if cr.rowcount:
        _logger.info("Migration 18.0.0.29.0: froze %s data/custom classroom(s) against CSV resync.", cr.rowcount)


def migrate(cr, _version):
    _freeze_custom_spaces(cr)
