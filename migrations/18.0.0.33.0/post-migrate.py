# -*- coding: utf-8 -*-
import logging

from odoo import SUPERUSER_ID, api

from odoo.addons.ems import _disable_login_presence_control, _fix_native_presence_translations

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    # Issue #555: the presence dot follows the attendance check-in/out only, never whether someone
    # has EMS open in a browser. Fresh installs get the same from post_init_hook.
    env = api.Environment(cr, SUPERUSER_ID, {})
    _disable_login_presence_control(env)
    _logger.info("Migration 18.0.0.33.0: disabled login-based presence control for every company.")
    _fix_native_presence_translations(env)
    _logger.info("Migration 18.0.0.33.0: fixed the presence dot's missing/wrong ca_ES/es_ES labels.")
