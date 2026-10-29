import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Issue #472: the students' and families' names stored all in capitals or all in lower case
    get capital initials, as every new or edited one now does (res.partner.create()/write()).
    post-migrate: it goes through the ORM. A clean install has no such names, so it needs no
    post_init_hook counterpart."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    fixed = env['res.partner']._ems_normalize_stored_person_names()
    _logger.info("Issue #472: capital initials given to %s student/family name(s).", fixed)
