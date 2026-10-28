import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

# The activities that wait for the Head: Odoo's approval and EMS's document validation.
HEAD_ACTIVITY_XMLIDS = ('hr_holidays.mail_act_leave_approval', 'ems.mail_activity_absence_document_validate')


def migrate(cr, version):
    """Issue #693: an Area Manager is now the Head of their own absence, instead of the Director.
    Their stored approver is recomputed, and the requests they have not validated yet pass to them
    with their activity and followers, without emailing anybody. post-migrate: it goes through the
    ORM. A clean install computes the approver from the start, so it needs no post_init_hook
    counterpart."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    managers = env['hr.department'].search([('is_top_level', '=', True)]).manager_id.with_context(
        active_test=False)
    managers._compute_leave_manager()
    managers.flush_recordset()

    leaves = env['hr.leave'].search([
        ('employee_id', 'in', managers.ids),
        ('ems_status', 'in', ['pending', 'pending_validation']),
    ])
    activity_types = [env.ref(xmlid).id for xmlid in HEAD_ACTIVITY_XMLIDS]
    for leave in leaves:
        approver = leave.employee_id.leave_manager_id
        activities = leave.activity_ids.filtered(
            lambda activity: activity.activity_type_id.id in activity_types and activity.user_id != approver)
        activities.with_context(mail_activity_quick_update=True).write({'user_id': approver.id})
    leaves._ems_sync_followers(announce=False)
    _logger.info("Issue #693: %s Area Managers are the Head of their own absence (%s open requests "
                 "handed over).", len(managers), len(leaves))
