# -*- coding: utf-8 -*-

import logging

_logger = logging.getLogger(__name__)


def _unsubscribe_involved_people(cr):
    """Issue #753: the people involved in an agreement no longer follow it (the minute already tells
    them what was agreed, and following it brought them every follow-up by email). Unsubscribe the
    ones who are only involved: not those who are also responsible for it, nor whoever created it."""
    cr.execute("""
        DELETE FROM mail_followers follower
         USING ems_quality_action_involved_employee_rel involved
          JOIN hr_employee employee ON employee.id = involved.employee_id
          JOIN res_users usr ON usr.id = employee.user_id
          JOIN ems_quality_action action ON action.id = involved.action_id
          LEFT JOIN res_users creator ON creator.id = action.create_uid
         WHERE follower.res_model = 'ems.quality.action'
           AND follower.res_id = involved.action_id
           AND follower.partner_id = usr.partner_id
           AND follower.partner_id IS DISTINCT FROM creator.partner_id
           AND NOT EXISTS (
               SELECT 1
                 FROM ems_quality_action_employee_rel responsible
                 JOIN hr_employee resp_employee ON resp_employee.id = responsible.employee_id
                 JOIN res_users resp_user ON resp_user.id = resp_employee.user_id
                WHERE responsible.action_id = involved.action_id
                  AND resp_user.partner_id = follower.partner_id)
    """)
    _logger.info("Agreements: %s people involved no longer follow them", cr.rowcount)


def migrate(cr, version):
    _unsubscribe_involved_people(cr)
