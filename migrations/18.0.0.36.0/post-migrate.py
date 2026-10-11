import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    _unfollow_administrator_from_contacts(env)


def _unfollow_administrator_from_contacts(env):
    """Issue #586: the administrator account followed every contact it had created, so each
    message on a student's or family's chatter was also emailed to the EMS mailbox. Creating a
    contact no longer makes anyone follow it; this removes the follows already there. A clean
    install has none."""
    count = env['res.partner']._ems_unfollow_administrator()
    _logger.info("Issue #586: administrator removed as a follower of %s contact(s).", count)
