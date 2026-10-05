# -*- coding: utf-8 -*-

import logging
from collections import defaultdict

import pytz

from odoo import SUPERUSER_ID, api, fields, models

_logger = logging.getLogger(__name__)

TASK_DIGEST_TEMPLATE = 'ems.email_template_task_digest'
# Tasks listed per activity type; the rest are only counted ("and N more").
TASK_DIGEST_MAX_PER_TYPE = 20


class EmsTaskDigestUsers(models.Model):
    """Daily pending-tasks digest: one email per user and working day, at the start of their
    working hours, listing every activity still assigned to them. See
    docs/en/developers/shared/task_digest.md."""
    _inherit = 'res.users'

    ems_task_digest = fields.Boolean(
        string="Daily summary of pending tasks", default=True,
        help="Every working day, at the start of your working hours, an email listing the tasks "
             "you still have pending in EMS. Only sent when there is at least one.")
    ems_task_digest_date = fields.Date(string="Last summary of pending tasks", readonly=True, copy=False)

    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS + ['ems_task_digest']

    @property
    def SELF_WRITEABLE_FIELDS(self):
        return super().SELF_WRITEABLE_FIELDS + ['ems_task_digest']

    @api.model
    def _cron_ems_task_digest(self):
        """Run every few minutes: sends each user's digest once their working day has started.
        'now' and 'today' both come from fields.Datetime.now(), in the company's timezone."""
        now = fields.Datetime.now()
        today = self.env['ems.datetime_utils'].utc_datetime_to_local(pytz.utc.localize(now)).date()
        assigned = self.env['mail.activity'].sudo()._read_group([('user_id', '!=', False)], ['user_id'])
        users = self.sudo().search([
            ('id', 'in', [user.id for user, in assigned]),
            ('id', '!=', SUPERUSER_ID),
            ('share', '=', False),
            ('ems_task_digest', '=', True),
            '|', ('ems_task_digest_date', '=', False), ('ems_task_digest_date', '<', today),
        ])
        for user in users:
            try:
                with self.env.cr.savepoint():
                    start = user._ems_workday_start(today)
                    if start and start <= now:
                        user._ems_send_task_digest(today)
            except Exception:
                _logger.exception("EMS task digest: could not send the digest of user %s (id=%d).",
                                  user.login, user.id)

    def _ems_workday_start(self, work_date):
        """Naive UTC start of the user's working day on work_date, or None when it is not a
        working day for them: their employee's working day (hr.employee._ems_workday_intervals)
        or, without an employee, the company's default schedule framework."""
        self.ensure_one()
        if self.employee_id:
            intervals = self.employee_id._ems_workday_intervals(work_date)
        else:
            intervals = self.company_id._ems_default_framework_intervals(work_date)
        if not intervals:
            return None
        return min(start for start, _end in intervals).astimezone(pytz.utc).replace(tzinfo=None)

    def _ems_send_task_digest(self, today):
        """Queue the digest and mark the day as done - also for a user without an email address,
        so the cron does not try again every few minutes."""
        self.ensure_one()
        if self.email:
            self.env.ref(TASK_DIGEST_TEMPLATE).with_context(lang=self.lang).send_mail(self.id)
        else:
            _logger.warning("EMS task digest: user %s (id=%d) has no email address.", self.login, self.id)
        self.ems_task_digest_date = today

    def _ems_task_digest_groups(self):
        """The user's open activities by type, for the digest's template: a list of dicts with
        'type', 'count', 'activities' (at most TASK_DIGEST_MAX_PER_TYPE, soonest due first) and
        'more' (how many were left out)."""
        self.ensure_one()
        activities = self.env['mail.activity'].sudo().with_context(lang=self.lang).search(
            [('user_id', '=', self.id)], order='date_deadline, id')
        by_type = defaultdict(lambda: self.env['mail.activity'])
        for activity in activities:
            by_type[activity.activity_type_id] |= activity
        return [{
            'type': activity_type,
            'count': len(of_type),
            'activities': of_type[:TASK_DIGEST_MAX_PER_TYPE],
            'more': max(len(of_type) - TASK_DIGEST_MAX_PER_TYPE, 0),
        } for activity_type, of_type in sorted(by_type.items(), key=lambda item: (item[0].sequence, item[0].id))]

    def _ems_task_digest_count(self):
        """How many open activities the user has, for the digest's subject."""
        self.ensure_one()
        return self.env['mail.activity'].sudo().search_count([('user_id', '=', self.id)])
