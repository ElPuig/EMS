import logging

_logger = logging.getLogger(__name__)


def _freeze_custom_data(cr):
    """From this version on every '__import__' record is frozen (data/custom/ seeds a record
    once, the centre maintains it through the app afterwards), but that freeze only runs from
    res.company._register_hook(), after this upgrade's data files have already reloaded - so the
    CSVs would still revert everything edited through the app one last time. Freezing the
    existing xmlids here, before the reload, prevents it. Raw SQL on pre-existing columns only,
    so it is safe in pre-migrate."""
    cr.execute("""
        UPDATE ir_model_data SET noupdate = TRUE
        WHERE module = '__import__' AND COALESCE(noupdate, FALSE) = FALSE
    """)
    if cr.rowcount:
        _logger.info("Migration 18.0.0.36.0: froze %s data/custom record(s) against CSV resync.", cr.rowcount)


def migrate(cr, _version):
    _freeze_custom_data(cr)
