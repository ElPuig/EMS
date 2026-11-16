# -*- coding: utf-8 -*-
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    _fix_shared_email_portals(cr)


def _fix_shared_email_portals(cr):
    """Issue #833: a student whose main email is also a family member's signs into the portal with
    the corporate email, and the login with the shared email is the family's. Installations that
    granted these portals before have students holding the family's login (and the family left
    out) and students left without any user: res.partner._ems_fix_shared_email_portals() brings
    both to the rule. A clean installation has no such data, so post_init_hook needs nothing."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    students = env['res.partner']._ems_students_sharing_email_with_family()
    summary = students._ems_fix_shared_email_portals()
    _logger.info("Migration #833: %s student(s) share the main email with their family; "
                 "%s portal access(es) granted.", len(students), len(summary['granted']))
    for issue in summary['issues']:
        _logger.info("Migration #833: %s", issue)
