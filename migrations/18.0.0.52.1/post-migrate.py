# -*- coding: utf-8 -*-
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    _realign_enrollments_with_main_group(cr)


def _realign_enrollments_with_main_group(cr):
    """Issue #875: students moved to another study by hand kept their enrollment on the old one,
    and the portal kept reading it (e.g. convalidations offered the old study's modules). Realigns
    those enrollments with the student's main group, see sale.order._ems_realign_study_with_group()."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    orders = env['sale.order']._ems_realign_study_with_group()
    _logger.info("Issue #875: %s enrollment(s) realigned with the student's main group: %s",
                 len(orders), ', '.join(orders.mapped('name')))
