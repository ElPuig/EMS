# -*- coding: utf-8 -*-

from datetime import timedelta

from odoo import _, models
from odoo.exceptions import UserError

# What the "Snooze" selector offers (static/src/js/backend/activity_snooze/).
SNOOZE_DAYS = (1, 3, 7)


class MailActivity(models.Model):
    """Snoozing a task (issue #727): in My Activities (the to-do tray's "View all activities")
    each row has a bell that opens a popover with 1, 3 or 7 days, and the list's header a
    "Snooze" button that offers the same in a small dialog for the selected tasks. The daily
    summary only lists what is due, so a snoozed task leaves it until its new due date. See
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

    def action_ems_snooze(self, days):
        """Called by the Snooze selector, for one task (the row's popover) or several (the
        header's dialog)."""
        if days not in SNOOZE_DAYS:
            raise UserError(_("A task can only be snoozed for 1, 3 or 7 days."))
        self._ems_snooze(days)

    def action_ems_snooze_dialog(self):
        """The list header's "Snooze": the same selector as the row's, in a small dialog, for the
        selected tasks. A client action with target 'new' is shown in a dialog, and the list
        reloads once it closes."""
        return {
            'type': 'ir.actions.client',
            'tag': 'ems.activity_snooze_dialog',
            'target': 'new',
            'name': _("Snooze"),
            'params': {'activity_ids': self.ids},
        }
