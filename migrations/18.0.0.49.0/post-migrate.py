# -*- coding: utf-8 -*-
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    _seed_walkout_levels(cr)


def _seed_walkout_levels(cr):
    """Issue #800: the levels whose groups may call a student walkout start as the law allows
    (ESO from the 3rd year, BTX and the vocational training cycles); the same as post_init_hook
    does on a new installation. From then on the centre sets them in Settings."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['ems.level']._ems_seed_walkout_levels()
    _logger.info("Migration #800: student walkout levels seeded.")
