from datetime import date, datetime, time, timedelta
from unittest.mock import patch

import pytz

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase

from .common import create_level_study, create_role_employee, create_role_user, mock_outgoing_email, next_student_id


# A fixed Wednesday: 'now' is frozen around it, so the fixtures never depend on when the suite runs.
SUMMARY_DAY = date(2030, 1, 9)
WEDNESDAY = str(SUMMARY_DAY.weekday())
THURSDAY = str((SUMMARY_DAY + timedelta(days=1)).weekday())
FRIDAY = str((SUMMARY_DAY + timedelta(days=2)).weekday())


class DailySummaryCase(TransactionCase):
    """Shared fixtures: a teacher working on Wednesdays 9:00-14:00 and Fridays 10:00-13:00, and a
    centre open on Wednesdays and Thursdays 8:00-21:30, so "the next working day" and "the next
    school day" are easy to tell apart."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.mail_transport = mock_outgoing_email(cls)
        cls.teacher_user = create_role_user(cls, 'tutor', 'summary_teacher', email='summary.teacher@example.com')
        cls.teacher = create_role_employee(cls, cls.teacher_user)
        # employee.create() already gave the teacher their own personal (empty) calendar.
        cls.calendar = cls.teacher.resource_calendar_id
        cls._add_slot(cls.calendar, WEDNESDAY, 9.0, 14.0)
        cls._add_slot(cls.calendar, FRIDAY, 10.0, 13.0)
        cls.env.company.default_schedule_framework_id = cls._calendar([(WEDNESDAY, 8.0, 21.5), (THURSDAY, 8.0, 21.5)])
        cls.partner = cls.env['res.partner'].create({'name': 'Summary Test Record'})

    @classmethod
    def _add_slot(cls, calendar, dayofweek, hour_from, hour_to):
        cls.env['resource.calendar.attendance'].create({
            'calendar_id': calendar.id, 'name': 'Summary Slot', 'dayofweek': dayofweek,
            'hour_from': hour_from, 'hour_to': hour_to, 'day_period': 'morning',
        })

    @classmethod
    def _calendar(cls, slots):
        """A calendar whose only periods are 'slots' - (dayofweek, hour_from, hour_to). Always
        passed explicitly: resource.calendar's own default would add a standard 40h week."""
        cls._calendar_count = getattr(cls, '_calendar_count', 0) + 1
        return cls.env['resource.calendar'].create({
            'name': f'Summary Test Calendar {cls._calendar_count}',
            'attendance_ids': [(0, 0, {
                'name': 'Summary Period', 'dayofweek': dayofweek, 'day_period': 'morning',
                'hour_from': hour_from, 'hour_to': hour_to,
            }) for dayofweek, hour_from, hour_to in slots],
        })

    def _utc(self, hour_float, day=SUMMARY_DAY):
        """Naive UTC datetime of a local (company timezone) hour on 'day'."""
        tz = pytz.timezone(self.env['ems.datetime_utils'].company_tz_name())
        hour, minute = int(hour_float), round((hour_float % 1) * 60)
        return tz.localize(datetime.combine(day, time(hour, minute))).astimezone(pytz.utc).replace(tzinfo=None)

    def _at(self, hour_float, day=SUMMARY_DAY):
        return patch.object(fields.Datetime, 'now', return_value=self._utc(hour_float, day))

    def _run_cron(self, hour_float, day=SUMMARY_DAY):
        with self._at(hour_float, day):
            self.env['res.users']._cron_ems_daily_summary()

    def _assign(self, user, count=1, activity_type='mail.mail_activity_data_todo', record=None, **vals):
        record = record or self.partner
        for index in range(count):
            record.activity_schedule(activity_type, user_id=user.id, summary=f'Summary task {index + 1}', **vals)

    def _summaries(self, user):
        """The daily summaries the user received (one message each, whatever the channel)."""
        return self.env['mail.message'].sudo().search([
            ('model', '=', 'res.partner'), ('res_id', '=', user.partner_id.id),
            ('message_type', '=', 'user_notification'), ('subject', '=like', 'EMS: %'),
        ], order='id')

    def _queue_notice(self, user, text='Summary notice', record=None):
        return self.env['ems.info_notice']._ems_queue(user, record or self.partner, lambda _user: f'<p>{text}</p>')


class TestDailySummary(DailySummaryCase):
    """res.users' daily summary (models/shared/daily_summary.py): one message per person, at the
    moment chosen in their profile, with their pending tasks, their students' attendance issues
    and the informative notices queued for them. See docs/en/developers/shared/daily_summary.md."""

    # --- when -----------------------------------------------------------------------------

    def test_default_is_start_of_working_day_once(self):
        self.assertEqual(self.teacher_user.ems_digest_moment, 'teacher_start')
        self._assign(self.teacher_user)
        self._run_cron(8.5)
        self.assertEqual(self.teacher_user.ems_digest_next, self._utc(9.0))
        self.assertFalse(self._summaries(self.teacher_user), "Sent before the working day starts")
        self._run_cron(9.25)
        self.assertEqual(len(self._summaries(self.teacher_user)), 1)
        self._run_cron(12.0)
        self.assertEqual(len(self._summaries(self.teacher_user)), 1, "Sent twice the same day")
        self.assertEqual(self.teacher_user.ems_digest_next, self._utc(10.0, SUMMARY_DAY + timedelta(days=2)),
                         "Pending tasks: the next one is due on the next working day (Friday)")

    def test_something_arriving_after_the_moment_waits_for_the_next_one(self):
        """Grouped at the start of the day: a task assigned at noon doesn't trigger a summary."""
        self._run_cron(8.0)
        self._assign(self.teacher_user)
        self._run_cron(12.0)
        self.assertFalse(self._summaries(self.teacher_user))
        self._run_cron(10.25, SUMMARY_DAY + timedelta(days=2))
        self.assertEqual(len(self._summaries(self.teacher_user)), 1)

    def test_not_sent_on_a_day_off_of_own_schedule(self):
        """Own schedule expecting nothing that day: no summary, not even from a framework that
        has periods that day (Thursday)."""
        self._assign(self.teacher_user)
        thursday = SUMMARY_DAY + timedelta(days=1)
        self._run_cron(7.0, thursday)
        self._run_cron(20.0, thursday)
        self.assertFalse(self._summaries(self.teacher_user))

    def test_not_sent_during_whole_day_absence(self):
        self.env['resource.calendar.leaves'].create({
            'name': 'Summary Absence', 'calendar_id': self.calendar.id,
            'resource_id': self.teacher.resource_id.id,
            'date_from': self._utc(0.0), 'date_to': self._utc(23.99),
        })
        self._assign(self.teacher_user)
        self._run_cron(7.0)
        self._run_cron(20.0)
        self.assertFalse(self._summaries(self.teacher_user))

    def test_without_employee_uses_default_framework(self):
        user = create_role_user(self, 'secretary', 'summary_no_employee', email='summary.secretary@example.com')
        self.env.company.default_schedule_framework_id = self._calendar([(WEDNESDAY, 10.0, 12.0)])
        self._assign(user)
        self._run_cron(9.5)
        self.assertFalse(self._summaries(user))
        self._run_cron(10.25)
        self.assertEqual(len(self._summaries(user)), 1)

    def test_framework_fallback_skips_public_holiday(self):
        user = create_role_user(self, 'secretary', 'summary_holiday', email='summary.holiday@example.com')
        self.env.company.default_schedule_framework_id = self._calendar([(WEDNESDAY, 10.0, 12.0)])
        self.env['resource.calendar.leaves'].create({
            'name': 'Summary Holiday', 'date_from': self._utc(0.0), 'date_to': self._utc(23.99),
        })
        self._assign(user)
        self._run_cron(7.0)
        self._run_cron(20.0)
        self.assertFalse(self._summaries(user))

    def test_moment_chosen_applies_to_tasks_too(self):
        self.teacher_user.ems_digest_moment = 'teacher_end'
        self._assign(self.teacher_user)
        self._run_cron(9.25)
        self.assertEqual(self.teacher_user.ems_digest_next, self._utc(14.0))
        self._run_cron(14.25)
        self.assertEqual(len(self._summaries(self.teacher_user)), 1)

    def test_changing_preference_moves_pending_summary(self):
        self._assign(self.teacher_user)
        self._run_cron(8.0)
        self.assertEqual(self.teacher_user.ems_digest_next, self._utc(9.0))
        with self._at(8.0):
            self.teacher_user.with_user(self.teacher_user).write({'ems_digest_moment': 'fixed_time', 'ems_digest_time': 20.0})
        self.assertEqual(self.teacher_user.ems_digest_next, self._utc(20.0))

    # --- who ------------------------------------------------------------------------------

    def test_not_sent_without_anything_pending(self):
        self._run_cron(8.0)
        self._run_cron(12.0)
        self.assertFalse(self._summaries(self.teacher_user))
        self.assertFalse(self.teacher_user.ems_digest_next)

    def test_tasks_done_before_the_moment_send_nothing(self):
        self._assign(self.teacher_user)
        self._run_cron(8.0)
        self.partner.activity_ids.unlink()
        self._run_cron(9.25)
        self.assertFalse(self._summaries(self.teacher_user))
        self.assertFalse(self.teacher_user.ems_digest_next)

    def test_not_sent_to_archived_user(self):
        self._assign(self.teacher_user)
        self._run_cron(8.0)
        self.teacher_user.active = False
        self._run_cron(12.0)
        self.assertFalse(self._summaries(self.teacher_user))

    def test_user_sets_own_preference_from_profile(self):
        self.teacher_user.with_user(self.teacher_user).write({
            'ems_digest_moment': 'fixed_time', 'ems_digest_time': 21.5, 'notification_type': 'inbox'})
        self.assertEqual(self.teacher_user.ems_digest_moment, 'fixed_time')
        self.assertEqual(self.teacher_user.ems_digest_time, 21.5)
        self.assertEqual(self.teacher_user.notification_type, 'inbox')

    def test_fixed_time_must_be_a_time_of_day(self):
        with self.assertRaises(ValidationError):
            self.teacher_user.ems_digest_time = 24.0

    def test_failure_for_one_user_does_not_stop_the_others(self):
        other = create_role_user(self, 'teacher', 'summary_other', name='Summary Other Teacher',
                                 email='summary.other@example.com')
        self._add_slot(create_role_employee(self, other).resource_calendar_id, WEDNESDAY, 9.0, 14.0)
        self._assign(self.teacher_user)
        self._assign(other)
        self._run_cron(8.0)
        users_class = type(self.env['res.users'])
        original = users_class._ems_send_daily_summary
        failing = self.teacher_user

        def send(user):
            if user == failing:
                raise ValueError("Summary test failure")
            return original(user)

        with patch.object(users_class, '_ems_send_daily_summary', send):
            self._run_cron(9.25)
        self.assertFalse(self._summaries(self.teacher_user))
        self.assertEqual(len(self._summaries(other)), 1)

    # --- how --------------------------------------------------------------------------------

    def test_by_email_by_default(self):
        self.mail_transport.reset_mock()
        self._assign(self.teacher_user)
        self._run_cron(8.0)
        self._run_cron(9.25)
        notification = self._summaries(self.teacher_user).notification_ids
        self.assertEqual(notification.notification_type, 'email')
        self.assertTrue(any('summary.teacher@example.com' in call.args[0]['To']
                            for call in self.mail_transport.call_args_list))

    def test_in_odoo_inbox_when_preferred(self):
        """The user's own "Notification: in Odoo" preference: no email, the inbox instead."""
        self.teacher_user.notification_type = 'inbox'
        self.mail_transport.reset_mock()
        self._assign(self.teacher_user)
        self._run_cron(8.0)
        self._run_cron(9.25)
        notification = self._summaries(self.teacher_user).notification_ids
        self.assertEqual(notification.notification_type, 'inbox')
        self.assertEqual(notification.res_partner_id, self.teacher_user.partner_id)
        self.assertFalse(any('summary.teacher@example.com' in call.args[0]['To']
                             for call in self.mail_transport.call_args_list))

    # --- what -----------------------------------------------------------------------------

    def test_content_lists_own_tasks_grouped_by_type(self):
        other = create_role_user(self, 'teacher', 'summary_stranger', email='summary.stranger@example.com')
        mine = self.env['res.partner'].create({'name': 'Summary Mine Record'})
        theirs = self.env['res.partner'].create({'name': 'Summary Theirs Record'})
        self._assign(self.teacher_user, record=mine)
        self._assign(self.teacher_user, activity_type='mail.mail_activity_data_call', record=mine)
        self._assign(other, record=theirs)
        with self._at(9.25):
            message = self.teacher_user._ems_send_daily_summary()
        body = message.body
        self.assertIn('Summary Mine Record', body)
        self.assertNotIn('Summary Theirs Record', body)
        self.assertIn(f'/mail/view?model=res.partner&amp;res_id={mine.id}', body)
        self.assertIn(self.env.ref('mail.mail_activity_data_todo').name, body)
        self.assertIn(self.env.ref('mail.mail_activity_data_call').name, body)
        self.assertNotIn("For your information", body)
        self.assertEqual(message.subject, 'EMS: daily summary (pending tasks: 2)')

    def test_content_caps_each_type(self):
        self._assign(self.teacher_user, count=23)
        body = self.teacher_user._ems_send_daily_summary().body
        self.assertIn('Summary task 20', body)
        self.assertNotIn('Summary task 21', body)
        self.assertIn('and 3 more', body)

    def test_content_in_recipient_language(self):
        self.env['res.lang']._activate_lang('ca_ES')
        self.teacher_user.lang = 'ca_ES'
        self._assign(self.teacher_user)
        message = self.teacher_user._ems_send_daily_summary()
        self.assertEqual(message.subject, 'EMS: resum diari (tasques pendents: 1)')
        self.assertIn('Tasques pendents', message.body)

    def test_lists_detected_absences_to_review(self):
        """Issue #707: the Head of Studies' review task needs no report of its own."""
        reviewer = create_role_user(self, 'head_of_studies', 'summary_hos', email='summary.hos@example.com')
        self.teacher.parent_id = create_role_employee(self, reviewer)
        absence = self.env['ems.absence_pending'].create({
            'employee_id': self.teacher.id, 'date_from': self._utc(9.0), 'date_to': self._utc(11.0)})
        self.assertEqual(absence.activity_ids.user_id, reviewer)
        with self._at(12.0):
            body = reviewer._ems_send_daily_summary().body
        self.assertIn(self.env.ref('ems.mail_activity_absence_pending_review').name, body)
        self.assertIn(f'model=ems.absence_pending&amp;res_id={absence.id}', body)

    # --- informative notices --------------------------------------------------------------

    def test_notice_waits_for_the_summary(self):
        self.mail_transport.reset_mock()
        notice = self._queue_notice(self.teacher_user, 'Summary student leaves')
        self.mail_transport.assert_not_called()
        self.assertFalse(self._summaries(self.teacher_user))
        self._run_cron(8.0)
        self._run_cron(9.25)
        message = self._summaries(self.teacher_user)
        self.assertEqual(len(message), 1)
        self.assertIn("For your information", message.body)
        self.assertIn('Summary student leaves', message.body)
        self.assertIn('Summary Test Record', message.body)
        self.assertNotIn("Pending tasks", message.body)
        self.assertEqual(message.subject, 'EMS: daily summary (notices: 1)')
        self.assertTrue(notice.sent_date)
        self.assertFalse(self.teacher_user.ems_digest_next, "Nothing left: no summary scheduled")

    def test_notices_are_sent_once(self):
        self._queue_notice(self.teacher_user, 'Summary first notice')
        self.teacher_user._ems_send_daily_summary()
        self._queue_notice(self.teacher_user, 'Summary second notice')
        body = self.teacher_user._ems_send_daily_summary().body
        self.assertIn('Summary second notice', body)
        self.assertNotIn('Summary first notice', body)

    def test_notices_grouped_by_record(self):
        other = self.env['res.partner'].create({'name': 'Summary Other Record'})
        self._queue_notice(self.teacher_user, 'Summary notice A')
        self._queue_notice(self.teacher_user, 'Summary notice B', record=other)
        self._queue_notice(self.teacher_user, 'Summary notice C')
        body = self.teacher_user._ems_send_daily_summary().body
        self.assertLess(body.index('Summary notice A'), body.index('Summary notice C'))
        self.assertLess(body.index('Summary notice C'), body.index('Summary Other Record'))

    def test_notice_skips_users_without_summary(self):
        portal = self.env['res.users'].create({
            'name': 'Summary Portal', 'login': 'summary_portal', 'email': 'summary.portal@example.com',
            'groups_id': [(6, 0, [self.env.ref('base.group_portal').id])]})
        notices = self.env['ems.info_notice']._ems_queue(
            portal | self.env.ref('base.user_root') | self.teacher_user, self.partner, lambda _user: '<p>x</p>')
        self.assertEqual(notices.user_id, self.teacher_user)

    def test_old_sent_notices_are_deleted(self):
        notice = self._queue_notice(self.teacher_user)
        notice.sent_date = self._utc(9.0, SUMMARY_DAY - timedelta(days=40))
        recent = self._queue_notice(self.teacher_user)
        recent.sent_date = self._utc(9.0, SUMMARY_DAY - timedelta(days=5))
        self._run_cron(9.0)
        self.assertFalse(notice.exists())
        self.assertTrue(recent.exists())


class TestDailySummaryMoment(DailySummaryCase):
    """When the next summary is due (res.users._ems_digest_eta), for each moment a user may
    choose. Inherited from the tutor's attendance issues report, whose moments it keeps."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.level, cls.study = create_level_study(cls, 'TDSM', study={
            'name': 'Test Study (Daily Summary)', 'date': SUMMARY_DAY,
        }, level={'name': 'Test Level (Daily Summary)'})
        cls.group = cls.env['ems.group'].create({
            'course': 2, 'acronym': 'TDSM', 'level_id': cls.level.id, 'study_id': cls.study.id,
            'tutor_id': cls.teacher.id,
        })
        cls.first_year_group = cls.env['ems.group'].create({
            'course': 1, 'acronym': 'TDSM', 'level_id': cls.level.id, 'study_id': cls.study.id,
        })
        cls.subject = cls.env['ems.subject'].create({
            'code': 'TDSM001', 'acronym': 'TDSM1', 'name': 'Test Subject (Daily Summary)',
            'study_ids': [(6, 0, [cls.study.id])],
        })
        cls.first_year_subject = cls.env['ems.subject'].create({
            'code': 'TDSM002', 'acronym': 'TDSM2', 'name': 'Test 1st-year Subject (Daily Summary)',
            'study_ids': [(6, 0, [cls.study.id])],
        })
        cls.student = cls.env['res.partner'].create({
            'name': 'Summary Student', 'contact_type': 'student', 'student_id': next_student_id(),
            'main_group_id': cls.group.id,
        })

    def _eta(self, now_hour, now_day=SUMMARY_DAY, issue_date=SUMMARY_DAY, fallback=True):
        with self._at(now_hour, now_day):
            return self.teacher_user._ems_digest_eta(issue_date, fallback=fallback)

    def _choose(self, moment, summary_time=None):
        vals = {'ems_digest_moment': moment}
        if summary_time is not None:
            vals['ems_digest_time'] = summary_time
        self.teacher_user.write(vals)

    def _teach(self, group, subject, dayofweek, hour_from, hour_to):
        """A class of 'subject' in 'group', taught by a teacher of its own, with the student enrolled."""
        teacher = self.env['hr.employee'].create({'name': f'Summary Teacher {group.course} {dayofweek}', 'employee_type': 'teacher'})
        teacher.resource_calendar_id.apply_schedule_changes([{
            'dayofweek': dayofweek, 'hour_from': hour_from, 'hour_to': hour_to, 'day_period': 'morning',
            'subject_id': subject.id, 'group_ids': [group.id], 'name': 'Summary class',
        }])
        self.env['ems.enrollment'].create({'student_id': self.student.id, 'group_id': group.id, 'subject_id': subject.id})

    # --- when the user's own working day starts (the default) -------------------------------

    def test_teacher_start_is_next_own_working_day(self):
        """Wednesday at noon: the next start is Friday's (Thursday is not a working day for them)."""
        self.assertEqual(self._eta(12.0), self._utc(10.0, SUMMARY_DAY + timedelta(days=2)))

    def test_teacher_start_before_own_start_is_same_day(self):
        self.assertEqual(self._eta(8.0), self._utc(9.0))

    def test_on_long_leave_falls_back_to_end_of_centre_day_only_for_issues(self):
        """No working day for them in the next two weeks: their students' issues don't wait for
        their return; their tasks do (no summary on days they don't work)."""
        self.calendar.attendance_ids.unlink()
        self.assertEqual(self._eta(12.0), self._utc(21.5))
        self.assertIsNone(self._eta(12.0, fallback=False))

    # --- when the user's own working day ends ---------------------------------------------

    def test_teacher_end(self):
        self._choose('teacher_end')
        self.assertEqual(self._eta(10.0), self._utc(14.0))

    def test_end_of_day_already_past_waits_for_next_moment(self):
        """A roll-call taken after that day's moment (or for a past day) goes in the next summary,
        never straight away (issue #588: one email per click). Wednesday at 16:00, the tutor's
        day ended at 14:00 and they don't work on Thursday: Friday's end."""
        self._choose('teacher_end')
        friday = SUMMARY_DAY + timedelta(days=2)
        self.assertEqual(self._eta(16.0), self._utc(13.0, friday))
        self.assertEqual(self._eta(10.0, issue_date=SUMMARY_DAY - timedelta(days=7)), self._utc(14.0))

    def test_end_of_day_without_working_day_falls_back_to_end_of_centre_day(self):
        """Thursday: the tutor doesn't work, the centre does (until 21:30)."""
        self._choose('teacher_end')
        thursday = SUMMARY_DAY + timedelta(days=1)
        self.assertEqual(self._eta(10.0, thursday, thursday), self._utc(21.5, thursday))

    def test_fallback_already_past_waits_for_next_moment(self):
        """Thursday at 22:00: the tutor doesn't work that day and the centre's day ended at 21:30,
        so the issue waits for the tutor's next working day end (Friday)."""
        self._choose('teacher_end')
        thursday = SUMMARY_DAY + timedelta(days=1)
        self.assertEqual(self._eta(22.0, thursday, thursday), self._utc(13.0, thursday + timedelta(days=1)))

    # --- when the tutor's students' classes end ---------------------------------------------

    def test_students_end_counts_subjects_taken_in_another_group(self):
        """2nd-year student taking a 1st-year subject: their day ends with that group's class,
        later than their own group's."""
        self._choose('students_end')
        self._teach(self.group, self.subject, WEDNESDAY, 9.0, 13.0)
        self.assertEqual(self._eta(10.0), self._utc(13.0))
        self._teach(self.first_year_group, self.first_year_subject, WEDNESDAY, 15.0, 17.0)
        self.student.invalidate_recordset(['schedule_attendance_ids'])
        self.assertEqual(self._eta(10.0), self._utc(17.0))

    def test_students_end_ignores_other_weekdays(self):
        self._choose('students_end')
        self._teach(self.group, self.subject, WEDNESDAY, 9.0, 13.0)
        self._teach(self.first_year_group, self.first_year_subject, THURSDAY, 15.0, 20.0)
        self.assertEqual(self._eta(10.0), self._utc(13.0))

    def test_students_end_already_past_waits_for_next_moment(self):
        self._choose('students_end')
        self._teach(self.group, self.subject, WEDNESDAY, 9.0, 13.0)
        self._teach(self.first_year_group, self.first_year_subject, THURSDAY, 15.0, 20.0)
        self.assertEqual(self._eta(16.0), self._utc(20.0, SUMMARY_DAY + timedelta(days=1)))

    def test_students_end_for_a_non_tutor_is_end_of_own_day(self):
        self.group.tutor_id = False
        self.teacher_user.invalidate_recordset(['ems_is_tutor'])
        self._choose('students_end')
        self.assertEqual(self._eta(10.0), self._utc(14.0))

    def test_only_group_tutors_are_tutors(self):
        """The ems.group_tutor role isn't enough: a Department Chief gets it without tutoring."""
        self.assertTrue(self.teacher_user.ems_is_tutor)
        chief = create_role_user(self, 'department_chief', 'summary_chief')
        create_role_employee(self, chief)
        self.assertTrue(chief.has_group('ems.group_tutor'))
        self.assertFalse(chief.ems_is_tutor)

    # --- at a fixed time ---------------------------------------------------------------------

    def test_fixed_time_today_or_next_school_day(self):
        self._choose('fixed_time', 21 + 20 / 60)
        self.assertEqual(self._eta(10.0), self._utc(21 + 20 / 60))
        thursday = SUMMARY_DAY + timedelta(days=1)
        self.assertEqual(self._eta(22.0), self._utc(21 + 20 / 60, thursday))

    def test_fixed_time_skips_days_without_school(self):
        """Thursday night: Friday to Tuesday have no school in this centre, so next Wednesday."""
        self._choose('fixed_time', 8.0)
        thursday = SUMMARY_DAY + timedelta(days=1)
        self.assertEqual(self._eta(22.0, thursday, thursday), self._utc(8.0, SUMMARY_DAY + timedelta(days=7)))

    # --- a tutor's attendance issues --------------------------------------------------------

    def test_issues_after_the_moment_share_one_summary(self):
        """Issue #588: every roll-call click after the tutor's day had ended used to send its own
        email (42 for one tutor in an afternoon)."""
        self._choose('teacher_end')
        IssueTutor = self.env['ems.attendance_issue_tutor']
        with self._at(16.0):
            for day in (SUMMARY_DAY, SUMMARY_DAY - timedelta(days=1)):
                IssueTutor.create({'tutor_id': self.teacher.id, 'issue_date': day})._schedule_tutor_report()
        self.assertEqual(self.teacher_user.ems_digest_next, self._utc(13.0, SUMMARY_DAY + timedelta(days=2)))

    def test_issue_on_a_day_off_brings_the_summary_forward(self):
        """A summary already due on Friday (pending tasks) is brought forward to Thursday's
        fallback when an issue of Thursday arrives: issues don't wait for the next working day."""
        self._choose('teacher_end')
        thursday = SUMMARY_DAY + timedelta(days=1)
        self.teacher_user.ems_digest_next = self._utc(13.0, thursday + timedelta(days=1))
        with self._at(10.0, thursday):
            self.env['ems.attendance_issue_tutor'].create({'tutor_id': self.teacher.id, 'issue_date': thursday})._schedule_tutor_report()
        self.assertEqual(self.teacher_user.ems_digest_next, self._utc(21.5, thursday))
