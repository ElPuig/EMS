import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Issue #698: the teacher follows the detected absences they have been asked to act on, so
    the reviewer's messages reach them. Those already asked before this version get their teacher
    as follower (ems.absence_pending._ems_follow_asked_teachers). post-migrate: it goes through
    the ORM. A clean install has no detected absences, so it needs no post_init_hook counterpart."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['ems.absence_pending']._ems_follow_asked_teachers()
    _logger.info("Issue #698: teachers now follow the detected absences they were asked about.")
