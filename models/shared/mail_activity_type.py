# -*- coding: utf-8 -*-

import logging

from odoo import SUPERUSER_ID, api, fields, models

_logger = logging.getLogger(__name__)


class MailActivityType(models.Model):
    _inherit = "mail.activity.type"

    ems_task_assignment = fields.Boolean(
        string="Managed by EMS",
        help="Set on the activity types EMS schedules automatically, so that they "
             "show up under Academic Management > Configuration > Task Assignment.")
    ems_assignee_ids = fields.Many2many(
        string="Assigned to", comodel_name="res.users",
        relation="ems_mail_activity_type_assignee_rel",
        column1="activity_type_id", column2="user_id",
        domain=[("share", "=", False)],
        help="Users who get the task when EMS schedules it. This list is independent "
             "from the security groups: holding an administrator role does not put "
             "anyone here, and being listed here grants no extra access rights.")

    def _ems_task_users(self):
        """Return the users that must get a task of this type.

        The system user (OdooBot) and archived users are always skipped, whatever
        the configuration says: nobody ever reads their inbox.
        """
        self.ensure_one()
        return self.sudo().ems_assignee_ids.filtered(
            lambda user: user.active and user.id != SUPERUSER_ID)

    @api.model
    def _ems_get_task_users(self, xmlid):
        """Recipients configured for the activity type identified by ``xmlid``."""
        activity_type = self.env.ref(xmlid, raise_if_not_found=False)
        users = activity_type._ems_task_users() if activity_type else self.env["res.users"]
        if not users:
            _logger.warning(
                "No recipient configured for activity type %s: no task will be scheduled. "
                "Set one in Academic Management > Configuration > Task Assignment.", xmlid)
        return users
