# -*- coding: utf-8 -*-

import logging
from collections import defaultdict
from datetime import timedelta

import pytz

from odoo import SUPERUSER_ID, _, api, fields, models, tools
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

DAILY_SUMMARY_TEMPLATE = 'ems.daily_summary_body'
# Tasks listed per activity type; the rest are only counted ("and N more").
TASKS_MAX_PER_TYPE = 20
# How many days ahead the next moment is looked for before falling back (a tutor on long leave,
# a tutor without schedule...).
LOOKAHEAD_DAYS = 14
# Moments at the end of the day the reported data belongs to; the others are the next one after now.
END_OF_DAY_MOMENTS = ('teacher_end', 'students_end')
# Sent informative notices are kept this long (for support), then deleted.
NOTICE_RETENTION_DAYS = 30


class EmsDailySummaryUsers(models.Model):
    """The daily summary: one message per person, at the moment they chose in their profile,
    with their pending tasks, their students' attendance issues (tutors) and the informative
    notices queued for them (ems.info_notice). Sent as a notification, so it reaches their email
    or their Odoo inbox as their own "Notification" preference says. See
    docs/en/developers/shared/daily_summary.md."""
    _inherit = 'res.users'

    ems_digest_moment = fields.Selection(
        selection=[
            ('teacher_start', "When my working day starts"),
            ('teacher_end', "When my working day ends"),
            ('students_end', "When my students' classes end (tutors)"),
            ('fixed_time', "At a fixed time"),
        ],
        string="Daily summary", default='teacher_start', required=True,
        help="When you receive the EMS daily summary: your pending tasks, your students' attendance "
             "issues if you are a tutor, and the notices for your information. It is only sent when "
             "there is something in it, and includes everything since the previous one.")
    ems_digest_time = fields.Float(
        string="Daily summary time",
        default=lambda self: self.env.company.attendance_issue_tutor_default,
        help="Every working day of the centre, at this time.")
    # When the next summary is due (naive UTC): set as soon as something is waiting for it, and
    # moved on after each one. Empty while there is nothing to send.
    ems_digest_next = fields.Datetime(string="Next daily summary", readonly=True, copy=False)
    ems_digest_last_sent = fields.Datetime(string="Last daily summary", readonly=True, copy=False)
    # Whether the user actually tutors a group: only then do their students' classes give a
    # moment. Not the ems.group_tutor role, which Department Chiefs, Heads of Studies and the
    # Director also get.
    ems_is_tutor = fields.Boolean(string="Is a group tutor", compute='_compute_ems_is_tutor', compute_sudo=True)

    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS + ['ems_digest_moment', 'ems_digest_time', 'ems_is_tutor']

    @property
    def SELF_WRITEABLE_FIELDS(self):
        return super().SELF_WRITEABLE_FIELDS + ['ems_digest_moment', 'ems_digest_time']

    def _compute_ems_is_tutor(self):
        tutors = self.env['ems.group'].search([('tutor_id.user_id', 'in', self.ids)]).tutor_id.user_id
        for user in self:
            user.ems_is_tutor = user in tutors

    @api.constrains('ems_digest_time')
    def _check_ems_digest_time(self):
        for user in self:
            if not 0 <= user.ems_digest_time < 24:
                raise ValidationError(_("The daily summary time must be between 00:00 and 23:59."))

    def write(self, vals):
        res = super().write(vals)
        if {'ems_digest_moment', 'ems_digest_time'} & set(vals):
            # A summary already waiting moves to the new moment.
            for user in self.sudo().filtered('ems_digest_next'):
                user._ems_digest_reschedule()
        return res

    # --- when -------------------------------------------------------------------------------

    def _ems_local_today(self, now):
        return self.env['ems.datetime_utils'].utc_datetime_to_local(pytz.utc.localize(now)).date()

    def _ems_effective_digest_moment(self):
        """The user's moment; the students' classes only give one to a group tutor, anyone else
        gets the end of their own working day instead."""
        self.ensure_one()
        moment = self.ems_digest_moment or 'teacher_start'
        if moment == 'students_end' and not self.ems_is_tutor:
            return 'teacher_end'
        return moment

    def _ems_digest_moment_on(self, day):
        """Naive UTC moment of the user's summary on `day`, or None when there is none that day
        (no working day for them, no class for their students, no school day). The working day
        is their employee's (absences and public holidays subtracted) or, without an employee,
        the centre's default schedule framework."""
        self.ensure_one()
        moment = self._ems_effective_digest_moment()
        company = self.company_id
        datetime_utils = self.env['ems.datetime_utils']
        if moment == 'fixed_time':
            if not company._ems_default_framework_intervals(day):
                return None
            return datetime_utils.datetime_to_odoo(datetime_utils.time_float_to_utc_datetime(day, self.ems_digest_time))
        if moment == 'students_end':
            hour_to = self.employee_id._ems_students_day_end(day)
            if hour_to is None:
                return None
            return datetime_utils.datetime_to_odoo(datetime_utils.time_float_to_utc_datetime(day, hour_to))
        intervals = self._ems_workday_intervals(day)
        if not intervals:
            return None
        edge = max(end for _start, end in intervals) if moment == 'teacher_end' else min(start for start, _end in intervals)
        return edge.astimezone(pytz.utc).replace(tzinfo=None)

    def _ems_digest_fallback(self, day):
        """When the chosen moment can't be found: the end of the centre's day, or the company's
        default time (attendance_issue_tutor_default) without a schedule framework for that day."""
        self.ensure_one()
        intervals = self.company_id._ems_default_framework_intervals(day)
        if intervals:
            return max(end for _start, end in intervals).astimezone(pytz.utc).replace(tzinfo=None)
        datetime_utils = self.env['ems.datetime_utils']
        return datetime_utils.datetime_to_odoo(datetime_utils.time_float_to_utc_datetime(
            day, self.company_id.attendance_issue_tutor_default))

    def _ems_digest_eta(self, issue_date=None, fallback=True):
        """Naive UTC moment the user's next summary is due, always after now; for an end-of-day
        moment, the end of `issue_date` (the day the reported data belongs to) when it hasn't
        passed yet. A roll-call taken once that day's moment has passed waits for the next one:
        due now, each roll-call click went out in its own email (issue #588).

        `fallback`: when no moment of theirs is found (a day off for an end-of-day moment, two
        weeks of leave...), the end of the centre's day rather than nothing. Only what must
        not wait for them (their students' attendance issues) uses it: their pending tasks are
        not sent on days they don't work."""
        self.ensure_one()
        now = fields.Datetime.now()
        today = self._ems_local_today(now)
        issue_date = issue_date or today
        if self._ems_effective_digest_moment() in END_OF_DAY_MOMENTS:
            due = self._ems_digest_moment_on(issue_date) or (fallback and self._ems_digest_fallback(issue_date))
            if due and due > now:
                return due
        days = [today + timedelta(days=offset) for offset in range(LOOKAHEAD_DAYS)]
        due = next((candidate for candidate in map(self._ems_digest_moment_on, days) if candidate and candidate > now), None)
        if due or not fallback:
            return due
        # The fallback always finds one: the company's default time, tomorrow at the latest.
        return next(candidate for candidate in map(self._ems_digest_fallback, days) if candidate > now)

    def _ems_digest_reschedule(self):
        """Sets when the next summary is due, or clears it when nothing is waiting for one."""
        for user in self:
            if not user._ems_digest_has_content():
                user.ems_digest_next = False
            else:
                user.ems_digest_next = user._ems_digest_eta(fallback=user._ems_digest_has_issues())

    def _ems_digest_schedule_for(self, issue_date):
        """Something for the summary arrived about `issue_date` (a tutor's attendance issue):
        the summary is due no later than that day's moment."""
        for user in self:
            due = user._ems_digest_eta(issue_date)
            if not user.ems_digest_next or due < user.ems_digest_next:
                user.ems_digest_next = due

    def _ems_workday_intervals(self, work_date, empty_schedule_as_framework=False):
        """(start, end) pairs, tz-aware, of the user's working day on work_date: their employee's
        (hr.employee._ems_workday_intervals: own schedule, absences and public holidays
        subtracted) or, without an employee, the company's default schedule framework.
        `empty_schedule_as_framework`: an employee whose schedule has no period at all (a teacher
        not scheduled yet) also gets the framework, rather than no working day ever."""
        self.ensure_one()
        employee = self.employee_id
        if employee and not (empty_schedule_as_framework and not employee.resource_calendar_id.attendance_ids):
            return employee._ems_workday_intervals(work_date)
        return self.company_id._ems_default_framework_intervals(work_date)

    def _ems_workday_start(self, work_date, empty_schedule_as_framework=False):
        """Naive UTC start of the user's working day on work_date (_ems_workday_intervals), or
        None when it is not a working day for them."""
        intervals = self._ems_workday_intervals(work_date, empty_schedule_as_framework)
        if not intervals:
            return None
        return min(start for start, _end in intervals).astimezone(pytz.utc).replace(tzinfo=None)

    def _ems_workday_started(self, today, now, cache):
        """Whether the user's working day `today` has already started at `now` (naive UTC): never
        on a day that is no working day for them. What the absence reminders wait for, so nobody
        gets one outside their working hours (issue #696); somebody not scheduled yet goes by the
        centre's own working day. `cache`, a dict, keeps the answer per user for one run of a
        scheduled action: working out a working day reads the schedule."""
        self.ensure_one()
        if self.id not in cache:
            start = self._ems_workday_start(today, empty_schedule_as_framework=True)
            cache[self.id] = bool(start) and start <= now
        return cache[self.id]

    # --- the scheduled action ---------------------------------------------------------------

    @api.model
    def _cron_ems_daily_summary(self):
        """Run every few minutes: works out when the summary of whoever has something waiting is
        due, and sends the ones due by now. Also deletes the informative notices sent long ago."""
        now = fields.Datetime.now()
        candidates = self.sudo().search([
            ('id', 'in', self._ems_digest_candidate_ids()),
            ('id', '!=', SUPERUSER_ID),
            ('share', '=', False),
        ])
        candidates.filtered(lambda user: not user.ems_digest_next)._ems_digest_reschedule()
        for user in candidates.filtered(lambda user: user.ems_digest_next and user.ems_digest_next <= now):
            try:
                with self.env.cr.savepoint():
                    user._ems_send_daily_summary()
            except Exception:
                _logger.exception("EMS daily summary: could not send the summary of user %s (id=%d).",
                                  user.login, user.id)
        # A summary that was due but has nothing left to send (the tasks were done meanwhile).
        self.sudo().search([('ems_digest_next', '!=', False), ('id', 'not in', candidates.ids)]).ems_digest_next = False
        self.env['ems.info_notice'].sudo().search([
            ('sent_date', '<', now - timedelta(days=NOTICE_RETENTION_DAYS))]).unlink()

    @api.model
    def _ems_digest_candidate_ids(self):
        """Ids of the users with something for their summary: open activities, attendance issues
        of their students not reported yet, informative notices not sent yet."""
        activities = self.env['mail.activity'].sudo()._read_group([('user_id', '!=', False)], ['user_id'])
        notices = self.env['ems.info_notice'].sudo()._read_group([('sent_date', '=', False)], ['user_id'])
        issues = self.env['ems.attendance_issue_tutor'].sudo()._ems_pending_tutors()
        return list({user.id for user, in activities + notices} | set(issues.user_id.ids))

    # --- what -------------------------------------------------------------------------------

    def _ems_digest_has_issues(self):
        self.ensure_one()
        return bool(self.employee_ids and self.env['ems.attendance_issue_tutor'].sudo()._ems_pending_tutors(self.employee_ids))

    def _ems_digest_has_content(self):
        self.ensure_one()
        return bool(
            self.env['mail.activity'].sudo().search_count([('user_id', '=', self.id)], limit=1)
            or self.env['ems.info_notice'].sudo().search_count([('user_id', '=', self.id), ('sent_date', '=', False)], limit=1)
            or self._ems_digest_has_issues())

    def _ems_digest_task_groups(self):
        """The user's open activities by type: a list of dicts with 'type', 'count', 'activities'
        (at most TASKS_MAX_PER_TYPE, soonest due first) and 'more' (how many were left out)."""
        self.ensure_one()
        activities = self.env['mail.activity'].sudo().with_context(lang=self.lang).search(
            [('user_id', '=', self.id)], order='date_deadline, id')
        by_type = defaultdict(lambda: self.env['mail.activity'])
        for activity in activities:
            by_type[activity.activity_type_id] |= activity
        return [{
            'type': activity_type,
            'count': len(of_type),
            'activities': of_type[:TASKS_MAX_PER_TYPE],
            'more': max(len(of_type) - TASKS_MAX_PER_TYPE, 0),
        } for activity_type, of_type in sorted(by_type.items(), key=lambda item: (item[0].sequence, item[0].id))]

    def _ems_digest_notice_groups(self, notices):
        """The informative notices by the record they are about (a student, usually): a list of
        dicts with 'record' and 'notices', in the order they were queued."""
        groups = {}
        for notice in notices:
            key = (notice.res_model, notice.res_id)
            if key not in groups:
                groups[key] = {'record': self.env[notice.res_model].sudo().browse(notice.res_id).with_context(lang=self.lang),
                               'notices': notice.browse()}
            groups[key]['notices'] |= notice
        return list(groups.values())

    def _ems_daily_summary_content(self):
        """What the user's summary would say now, in their language: a dict with 'subject',
        'body', and the issue 'statuses' and 'notices' it reports, or None when it would be
        empty. Also used to show it in the user manuals' screenshots."""
        self.ensure_one()
        user = self.sudo()
        env = user.with_context(lang=user.lang).env
        tasks = user._ems_digest_task_groups()
        IssueTutor = env['ems.attendance_issue_tutor'].sudo()
        statuses = IssueTutor._tutor_report_pending_statuses(user.employee_ids.ids) if user.employee_ids else env['ems.attendance_issue_status']
        notices = env['ems.info_notice'].sudo().search([('user_id', '=', user.id), ('sent_date', '=', False)], order='id')
        if not (tasks or statuses or notices):
            return None
        task_count = sum(group['count'] for group in tasks)
        parts = []
        if task_count:
            parts.append(env._("pending tasks: %(count)s", count=task_count))
        if statuses:
            parts.append(env._("attendance issues"))
        if notices:
            parts.append(env._("notices: %(count)s", count=len(notices)))
        return {
            'subject': env._("EMS: daily summary (%(contents)s)", contents=", ".join(parts)),
            'body': env['ir.qweb']._render(DAILY_SUMMARY_TEMPLATE, {
                'user': user,
                'base_url': user.get_base_url(),
                'task_groups': tasks,
                'tutor_days': IssueTutor._tutor_report_days(statuses),
                'notice_groups': user._ems_digest_notice_groups(notices),
                'format_date': lambda value: tools.format_date(env, value),
            }),
            'statuses': statuses,
            'notices': notices,
        }

    def _ems_send_daily_summary(self):
        """Sends the summary, if there is anything in it, marks what it reported and moves on to
        the next one. Returns the message, or False."""
        self.ensure_one()
        user = self.sudo()
        content = user._ems_daily_summary_content()
        message = False
        if content:
            partner = user.partner_id.with_context(lang=user.lang)
            message = partner.message_notify(
                partner_ids=partner.ids, author_id=self.env.ref('base.partner_root').id,
                subject=content['subject'], body=content['body'], record_name=content['subject'],
                email_layout_xmlid='mail.mail_notification_light')
            content['statuses'].write({'tutor_notified': True})
            content['statuses'].attendance_issue_student_id.attendance_issue_tutor_id.write({'summary_message_id': message.id})
            content['notices'].write({'sent_date': fields.Datetime.now()})
            user.ems_digest_last_sent = fields.Datetime.now()
        user._ems_digest_reschedule()
        return message
