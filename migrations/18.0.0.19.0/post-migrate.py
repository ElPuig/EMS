# -*- coding: utf-8 -*-
import logging
from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, _version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    old_action = env.ref('ems.action_attendance_session_tree', raise_if_not_found=False)
    new_action = env.ref('ems.action_attendance_passlist', raise_if_not_found=False)
    if not old_action or not new_action:
        _logger.warning(
            "Migration 18.0.0.19.0: attendance actions not found, skipping home action fix."
        )
        return

    users = env['res.users'].with_context(active_test=False).search([('action_id', '=', old_action.id)])
    users.write({'action_id': new_action.id})
    _logger.info(
        "Migration 18.0.0.19.0: updated %d users' home action from History to Current.",
        len(users),
    )
