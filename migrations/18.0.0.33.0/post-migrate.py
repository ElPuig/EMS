import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def _align_user_names_with_employees(env):
    """Issue #542: a name fixed on the employee form never reached its EMS user (native hr only
    syncs user -> employee), nor its Google account. Give every user whose name drifted the
    employee's name, which is the one the centre maintains, and queue the same fix for the
    Google account. post-migrate: goes through the ORM (see CLAUDE.md, Migrations)."""
    employees = env['hr.employee'].with_context(active_test=False).search([('user_id', '!=', False)])
    renamed = employees.filtered(lambda employee: employee.user_id.name != employee.name)
    for employee in renamed:
        _logger.info("EMS user %s renamed from %r to %r.",
                     employee.user_id.login, employee.user_id.name, employee.name)
    renamed._sync_user_name()
    renamed._gw_enqueue_rename()


def migrate(cr, version):
    _align_user_names_with_employees(api.Environment(cr, SUPERUSER_ID, {}))
