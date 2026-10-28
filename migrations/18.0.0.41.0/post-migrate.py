import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Issue #707: detected absences are reviewed by the teacher's Head of Studies first. Those
    already waiting: the ones the teacher was already reminded of (or reported) go on as if a
    justification had been requested, the rest wait for review with their task
    (ems.absence_pending._ems_start_review_circuit). post-migrate: it goes through the ORM and
    the new state, field and activity type. A clean install has no detected absences, so it needs
    no post_init_hook counterpart."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['ems.absence_pending']._ems_start_review_circuit()
    _logger.info("Issue #707: detected absences moved to the review circuit.")
