import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Issue #707: the detected absences already there join the new review. The ones whose teacher
    was already reminded keep waiting for the teacher; the others are still to review and get their
    review task (ems.absence_pending._ems_migrate_to_review). post-migrate: it goes through the ORM,
    and the new states, fields and activity type must already be loaded. A clean install has no
    detected absences, so it needs no post_init_hook counterpart."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    waiting, to_review = env['ems.absence_pending']._ems_migrate_to_review()
    _logger.info("Issue #707: %s detected absence(s) left waiting for the teacher, %s sent to review.",
                 waiting, to_review)
