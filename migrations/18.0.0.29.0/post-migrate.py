import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def _revoke_stale_groups_of_archived_employees(env):
    """Issue #510: hr.employee._sync_security_groups() used to look employees up with a plain
    search(), which skips archived ones - so a departed teacher whose tutorship (and with it
    role_tutor) was cleared after archiving them kept the Tutor group. Revokes every role/job-
    managed group an archived employee's user still holds that their current roles/job neither
    grant nor imply. Active employees are deliberately left alone: a managed group granted by
    hand is legitimate there, and cannot be told apart from a stale one."""
    Role = env['ems.role'].with_context(active_test=False)
    Job = env['hr.job'].with_context(active_test=False)
    managed = Role.search([('group_id', '!=', False)]).group_id | Job.search([('group_id', '!=', False)]).group_id
    employees = env['hr.employee'].with_context(active_test=False).search([
        ('active', '=', False), ('user_id', '!=', False),
    ])
    for employee in employees:
        granted = employee._ems_role_job_groups()
        stale = (employee.user_id.groups_id & managed) - granted - granted.trans_implied_ids
        if stale:
            employee.user_id.write({'groups_id': [(3, group.id) for group in stale]})
            _logger.info(
                "Migration 18.0.0.29.0: revoked %s from archived employee %s.",
                ", ".join(stale.mapped('full_name')), employee.name)


def migrate(cr, _version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    _revoke_stale_groups_of_archived_employees(env)
