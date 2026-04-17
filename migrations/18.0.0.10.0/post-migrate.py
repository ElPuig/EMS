# -*- coding: utf-8 -*-
import logging
from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, _version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    employees = env['hr.employee'].search([('role_ids.group_id', '!=', False)])
    if not employees:
        _logger.info("Migration 18.0.0.10.0: no employees with role-bound groups to sync.")
        return
    employees._sync_security_groups()
    _logger.info("Migration 18.0.0.10.0: synced security groups for %d employees.", len(employees))
