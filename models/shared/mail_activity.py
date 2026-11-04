# -*- coding: utf-8 -*-

from datetime import timedelta

from odoo import models


class MailActivity(models.Model):
    """Snoozing a task (issue #727): Odoo's own "Snooze 7d" plus "Snooze 1d" and "Snooze 3d"
    (My Activities, the to-do tray's "View all activities"). The daily summary only lists what
    is due, so a snoozed task leaves it until its new due date. See
    docs/en/developers/shared/daily_summary.md."""
    _inherit = 'mail.activity'

    def _ems_snooze(self, days):
        """Moves the due date `days` on from today, or from the due date when that is later.
        Today is the company's: Odoo's own action_snooze counts from the server's (UTC) date,
        a day behind just after local midnight."""
        today = self.env['ems.datetime_utils'].get_local_today()
        for activity in self.filtered('active'):
            activity.date_deadline = max(activity.date_deadline, today) + timedelta(days=days)

    def action_snooze(self):
        self._ems_snooze(7)

    def action_ems_snooze_1d(self):
        self._ems_snooze(1)

    def action_ems_snooze_3d(self):
        self._ems_snooze(3)
