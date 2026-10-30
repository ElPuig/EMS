import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """post-migrate: both steps go through the ORM. A clean install has no detected absences, so
    neither needs a post_init_hook counterpart."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    # First reopen, so the entries it brings back to an asked stage get their follower too.
    _reopen_wrongly_discarded(env)
    _follow_asked_teachers(env)


def _reopen_wrongly_discarded(env):
    """Issue #731: a check-in recorded afterwards discarded a detected absence as soon as it fell
    on its day, even outside the hours the reviewer had narrowed it to. Those still missed come
    back at the stage of the review they had reached
    (ems.absence_pending._ems_reopen_wrongly_discarded)."""
    env['ems.absence_pending']._ems_reopen_wrongly_discarded()
    _logger.info("Issue #731: detected absences wrongly discarded by a check-in reopened.")


def _follow_asked_teachers(env):
    """Issue #698: the teacher follows the detected absences they have been asked to act on, so
    the reviewer's messages reach them. Those already asked before this version get their teacher
    as follower (ems.absence_pending._ems_follow_asked_teachers)."""
    env['ems.absence_pending']._ems_follow_asked_teachers()
    _logger.info("Issue #698: teachers now follow the detected absences they were asked about.")
