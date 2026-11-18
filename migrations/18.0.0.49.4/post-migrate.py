# -*- coding: utf-8 -*-
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    _mark_requests_section(cr)


def _mark_requests_section(cr):
    """Issue #822: a meeting held by email writes the participants' answers under "Any other
    business", found by its section kind. The centre's "Precs i preguntes" section was seeded as
    plain text, and data/custom records are frozen, so its new kind is set here (a clean install
    gets it from the CSV). Writing through the ORM recomputes the kind stored on every minute's and
    type's copy of the section."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    section = env.ref('__import__.minute_section_requests', raise_if_not_found=False)
    if section and section.kind == 'text':
        section.kind = 'requests'
        _logger.info("Migration #822: section %s is now the one for any other business.", section.code)
