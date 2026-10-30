import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Issue #731: a check-in recorded afterwards discarded a detected absence as soon as it fell
    on its day, even outside the hours the reviewer had narrowed it to. Those still missed come
    back at the stage of the review they had reached
    (ems.absence_pending._ems_reopen_wrongly_discarded). post-migrate: it goes through the ORM. A
    clean install has nothing discarded, so it needs no post_init_hook counterpart."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['ems.absence_pending']._ems_reopen_wrongly_discarded()
    _logger.info("Issue #731: detected absences wrongly discarded by a check-in reopened.")
    # Issue #735: a detected absence is claimed again when the absence request that resolved it
    # falls through; those linked to one refused, cancelled or deleted before it go back to the
    # review. Nothing to do on a clean install either.
    env['ems.absence_pending']._ems_reopen_dropped_requests()
    _logger.info("Issue #735: detected absences whose absence request fell through reopened.")
