from datetime import date, datetime, time
from unittest.mock import patch

import pytz

from odoo import fields
from odoo.tests.common import TransactionCase

from .common import create_role_employee, create_role_user, mock_outgoing_email


# A fixed Wednesday: 'now' is frozen on it, so the fixtures never depend on when the suite runs.
DIGEST_DAY = date(2030, 1, 9)
WEDNESDAY = str(DIGEST_DAY.weekday())
THURSDAY = str((DIGEST_DAY.weekday() + 1) % 7)


class TestTaskDigest(TransactionCase):
    """res.users' daily pending-tasks digest (models/shared/task_digest.py): one email per user
    and working day, at the start of their working hours. See
    docs/en/developers/shared/task_digest.md."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        cls.teacher_user = create_role_user(cls, 'teacher', 'digest_teacher', email='digest.teacher@example.com')
        cls.teacher = create_role_employee(cls, cls.teacher_user)
        # employee.create() already gave the teacher their own personal (empty) calendar.
        cls.calendar = cls.teacher.resource_calendar_id
        cls._add_slot(cls.calendar, WEDNESDAY, 9.0, 14.0)
        cls.partner = cls.env['res.partner'].create({'name': 'Digest Test Record'})

    @classmethod
    def _add_slot(cls, calendar, dayofweek, hour_from, hour_to):
        cls.env['resource.calendar.attendance'].create({
            'calendar_id': calendar.id, 'name': 'Digest Slot', 'dayofweek': dayofweek,
            'hour_from': hour_from, 'hour_to': hour_to, 'day_period': 'morning',
        })

    def _calendar(self, slots):
        """A calendar whose only periods are 'slots' - (dayofweek, hour_from, hour_to). Always
        passed explicitly: resource.calendar's own default would add a standard 40h week."""
        return self.env['resource.calendar'].create({
            'name': 'Digest Test Calendar',
            'attendance_ids': [(0, 0, {
                'name': 'Digest Period', 'dayofweek': dayofweek, 'day_period': 'morning',
                'hour_from': hour_from, 'hour_to': hour_to,
            }) for dayofweek, hour_from, hour_to in slots],
        })

    def _utc(self, hour_float, day=DIGEST_DAY):
        """Naive UTC datetime of a local (company timezone) hour on 'day'."""
        tz = pytz.timezone(self.env['ems.datetime_utils'].company_tz_name())
        hour, minute = int(hour_float), round((hour_float % 1) * 60)
        return tz.localize(datetime.combine(day, time(hour, minute))).astimezone(pytz.utc).replace(tzinfo=None)

    def _run_cron(self, hour_float, day=DIGEST_DAY):
        with patch.object(fields.Datetime, 'now', return_value=self._utc(hour_float, day)):
            self.env['res.users']._cron_ems_task_digest()

    def _assign(self, user, count=1, activity_type='mail.mail_activity_data_todo', record=None, **vals):
        record = record or self.partner
        for index in range(count):
            record.activity_schedule(activity_type, user_id=user.id, summary=f'Digest task {index + 1}', **vals)

    def _digests(self, user):
        return self.env['mail.mail'].sudo().search([('model', '=', 'res.users'), ('res_id', '=', user.id)])

    # --- when -----------------------------------------------------------------------------

    def test_sent_once_at_start_of_working_day(self):
        self._assign(self.teacher_user)
        self._run_cron(8.5)
        self.assertFalse(self._digests(self.teacher_user), "Sent before the working day starts")
        self._run_cron(9.25)
        self.assertEqual(len(self._digests(self.teacher_user)), 1)
        self.assertEqual(self.teacher_user.ems_task_digest_date, DIGEST_DAY)
        self._run_cron(12.0)
        self.assertEqual(len(self._digests(self.teacher_user)), 1, "Sent twice the same day")

    def test_sent_again_the_next_working_day(self):
        self._add_slot(self.calendar, THURSDAY, 9.0, 14.0)
        self._assign(self.teacher_user)
        self._run_cron(9.25)
        self._run_cron(9.25, day=date(2030, 1, 10))
        self.assertEqual(len(self._digests(self.teacher_user)), 2)

    def test_not_sent_on_a_day_off_of_own_schedule(self):
        """Own schedule expecting nothing that day: no digest, not even from a framework that
        has periods that day."""
        framework = self._calendar([(WEDNESDAY, 8.0, 15.0)])
        self.env.company.default_schedule_framework_id = framework
        self.calendar.attendance_ids.unlink()
        self._add_slot(self.calendar, THURSDAY, 9.0, 14.0)
        self._assign(self.teacher_user)
        self._run_cron(20.0)
        self.assertFalse(self._digests(self.teacher_user))

    def test_not_sent_during_whole_day_absence(self):
        self.env['resource.calendar.leaves'].create({
            'name': 'Digest Absence', 'calendar_id': self.calendar.id,
            'resource_id': self.teacher.resource_id.id,
            'date_from': self._utc(0.0), 'date_to': self._utc(23.99),
        })
        self._assign(self.teacher_user)
        self._run_cron(20.0)
        self.assertFalse(self._digests(self.teacher_user))

    def test_without_schedule_uses_default_framework(self):
        user = create_role_user(self, 'secretary', 'digest_no_employee', email='digest.secretary@example.com')
        self.env.company.default_schedule_framework_id = self._calendar([(WEDNESDAY, 10.0, 12.0)])
        self._assign(user)
        self._run_cron(9.5)
        self.assertFalse(self._digests(user))
        self._run_cron(10.25)
        self.assertEqual(len(self._digests(user)), 1)

    def test_framework_fallback_skips_public_holiday(self):
        user = create_role_user(self, 'secretary', 'digest_holiday', email='digest.holiday@example.com')
        self.env.company.default_schedule_framework_id = self._calendar([(WEDNESDAY, 10.0, 12.0)])
        self.env['resource.calendar.leaves'].create({
            'name': 'Digest Holiday', 'date_from': self._utc(0.0), 'date_to': self._utc(23.99),
        })
        self._assign(user)
        self._run_cron(20.0)
        self.assertFalse(self._digests(user))

    # --- who ------------------------------------------------------------------------------

    def test_not_sent_without_pending_tasks(self):
        self._run_cron(12.0)
        self.assertFalse(self._digests(self.teacher_user))

    def test_not_sent_when_turned_off(self):
        self.teacher_user.ems_task_digest = False
        self._assign(self.teacher_user)
        self._run_cron(12.0)
        self.assertFalse(self._digests(self.teacher_user))

    def test_not_sent_to_archived_user(self):
        self._assign(self.teacher_user)
        self.teacher_user.active = False
        self._run_cron(12.0)
        self.assertFalse(self._digests(self.teacher_user))

    def test_user_can_turn_it_off_from_own_profile(self):
        self.teacher_user.with_user(self.teacher_user).write({'ems_task_digest': False})
        self.assertFalse(self.teacher_user.ems_task_digest)

    def test_failure_for_one_user_does_not_stop_the_others(self):
        other = create_role_user(self, 'teacher', 'digest_other', name='Digest Other Teacher',
                                 email='digest.other@example.com')
        self._add_slot(create_role_employee(self, other).resource_calendar_id, WEDNESDAY, 9.0, 14.0)
        self._assign(self.teacher_user)
        self._assign(other)
        users_class = type(self.env['res.users'])
        original = users_class._ems_send_task_digest
        failing = self.teacher_user

        def send(user, today):
            if user == failing:
                raise ValueError("Digest test failure")
            return original(user, today)

        with patch.object(users_class, '_ems_send_task_digest', send):
            self._run_cron(9.25)
        self.assertFalse(self._digests(self.teacher_user))
        self.assertEqual(len(self._digests(other)), 1)

    # --- what -----------------------------------------------------------------------------

    def test_content_lists_own_tasks_grouped_by_type(self):
        other = create_role_user(self, 'teacher', 'digest_stranger', email='digest.stranger@example.com')
        mine = self.env['res.partner'].create({'name': 'Digest Mine Record'})
        theirs = self.env['res.partner'].create({'name': 'Digest Theirs Record'})
        self._assign(self.teacher_user, record=mine)
        self._assign(self.teacher_user, activity_type='mail.mail_activity_data_call', record=mine)
        self._assign(other, record=theirs)
        self._run_cron(9.25)
        mail = self._digests(self.teacher_user)
        self.assertEqual(mail.email_to, 'digest.teacher@example.com')
        body = mail.body_html
        self.assertIn('Digest Mine Record', body)
        self.assertNotIn('Digest Theirs Record', body)
        self.assertIn(f'/mail/view?model=res.partner&amp;res_id={mine.id}', body)
        self.assertIn(self.env.ref('mail.mail_activity_data_todo').name, body)
        self.assertIn(self.env.ref('mail.mail_activity_data_call').name, body)
        self.assertIn('pending tasks (2)', mail.subject)

    def test_content_caps_each_type(self):
        self._assign(self.teacher_user, count=23)
        self._run_cron(9.25)
        body = self._digests(self.teacher_user).body_html
        self.assertIn('Digest task 20', body)
        self.assertNotIn('Digest task 21', body)
        self.assertIn('and 3 more', body)

    def test_content_in_recipient_language(self):
        self.env['res.lang']._activate_lang('ca_ES')
        self.teacher_user.lang = 'ca_ES'
        self._assign(self.teacher_user)
        self._run_cron(9.25)
        self.assertIn('tasques pendents (1)', self._digests(self.teacher_user).subject)
