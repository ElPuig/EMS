import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    _unfollow_contact_creators(env)


def _unfollow_contact_creators(env):
    """Issue #586: creating a contact used to make you follow it, so whoever registered students
    and families (the administrator account above all) received by email every message later
    written on their chatter. Creating one no longer does; this removes the follows already
    there, except those of someone who has written on that contact. A clean install has none."""
    count = env['res.partner']._ems_unfollow_contact_creators()
    _logger.info("Issue #586: %s follow(s) of a contact by whoever created it removed.", count)
