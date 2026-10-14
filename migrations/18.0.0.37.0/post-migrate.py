import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    _reset_absence_followers(env)


def _reset_absence_followers(env):
    """Issue #632: a staff absence request is now followed by the employee and whoever has it in
    hand at its stage (the Head, then the Director), so a message written on it reaches only the
    other side. Requests filed before were also followed by the employee's Department Chief and
    Seminar Chief, and by the Director from the Head's acknowledgement on. Nobody is told: this
    only changes who receives the messages written from now on. A clean install has no requests
    to fix."""
    leaves = env['hr.leave'].with_context(active_test=False).search([])
    leaves._ems_reset_followers()
    _logger.info("Issue #632: followers of %s absence request(s) reset to whoever has them in hand",
                 len(leaves))
