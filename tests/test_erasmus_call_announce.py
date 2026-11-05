from datetime import datetime, timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged

from .common import create_level_study_group, create_role_employee, create_role_user, mock_outgoing_email
from .test_erasmus import create_erasmus_fixtures, upload


@tagged('post_install', '-at_install')
class TestErasmusCallAnnounce(TransactionCase):
    """The notice of an open call to whoever can apply, and the reminder before it closes, for the
    students' call (the levels of its modalities; conduct warnings rule nobody out, see test_erasmus.py) and
    the staff call (the teachers of its levels and the Direction)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        create_erasmus_fixtures(cls)
        # The staff call: an FP teacher can apply, an ESO teacher and the administration staff
        # cannot; the Direction that validates the activities can.
        cls.eso_level, eso_study, cls.eso_group = create_level_study_group(cls, 'TERC')
        cls.staff = {}
        for name, group, kind in (('fp', cls.group, 'teacher'), ('eso', cls.eso_group, 'teacher'),
                                  ('admin', cls.eso_group, 'asp')):
            user = create_role_user(cls, 'teacher', f'test_announce_{name}', name=f'Announce {name}',
                                    email=f'announce.{name}@example.com')
            employee = create_role_employee(cls, user, employee_type=kind)
            subject = cls.env['ems.subject'].create({
                'code': f'TANN{name}', 'acronym': f'TA{name}', 'name': f'Announce {name}',
                'study_ids': [(4, group.study_id.id)]})
            cls.env['ems.teaching'].create({'teacher_id': employee.id, 'group_id': group.id, 'subject_id': subject.id})
            cls.staff[name] = user
        cls.director = create_role_user(cls, 'director', 'test_announce_director', email='announce.director@example.com')
        now = fields.Datetime.now()
        cls.staff_call = cls.env['ems.erasmus.call'].create({
            'name': 'Test staff call', 'audience': 'staff', 'date_open': now - timedelta(days=1),
            'date_close': now + timedelta(days=10), 'staff_level_ids': [(6, 0, cls.level.ids)],
            'validator_ids': [(6, 0, cls.director.ids)]})
        cls.staff_call.action_publish()

    def _mails(self, call):
        return self.env['mail.mail'].search([('model', '=', 'ems.erasmus.call'), ('res_id', '=', call.id)])

    def test_who_can_apply_to_a_students_call(self):
        partners = self.call._ems_eligible_partners()
        self.assertIn(self.student, partners)
        self.assertIn(self.minor, partners)
        self.assertNotIn(self.outsider, partners, "Another level: not in any modality.")

    def test_who_can_apply_to_a_staff_call(self):
        partners = self.staff_call._ems_eligible_partners()
        self.assertIn(self.staff['fp'].partner_id, partners)
        self.assertIn(self.director.partner_id, partners, "The Direction that validates the activities.")
        self.assertNotIn(self.staff['eso'].partner_id, partners)
        self.assertNotIn(self.staff['admin'].partner_id, partners)
        for user in (self.staff['fp'], self.staff['eso']):
            self.assertEqual(self.staff_call in user.partner_id._ems_erasmus_calls(),
                             user.partner_id in partners, "The same rule as the portal.")

    def test_the_notice_emails_each_person_alone(self):
        wizard = self.env['ems.erasmus.call.announce'].with_user(self.erasmus_user).create({'call_id': self.call.id})
        self.assertEqual((wizard.recipient_count, wizard.without_email_count), (2, 0))
        wizard.action_send()
        mails = self._mails(self.call)
        self.assertEqual(sorted(mails.mapped('email_to')), ['erasmus.minor@example.com', 'erasmus.student@example.com'])
        self.assertTrue(all(self.call.name in mail.subject for mail in mails))
        self.assertTrue(all(f'/my/erasmus/call/{self.call.id}' in mail.body_html for mail in mails))
        self.assertEqual(self.call.announce_count, 2)
        self.assertTrue(self.call.announce_date)
        self.assertIn('2', self.call.message_ids[:1].body)

    def test_the_notice_skips_who_has_no_address(self):
        self.minor.email = False
        wizard = self.env['ems.erasmus.call.announce'].with_user(self.erasmus_user).create({'call_id': self.call.id})
        self.assertEqual((wizard.recipient_count, wizard.without_email_count), (2, 1))
        wizard.action_send()
        self.assertEqual(self._mails(self.call).mapped('email_to'), ['erasmus.student@example.com'])
        self.assertEqual(self.call.announce_count, 1)

    def test_staff_call_notice(self):
        self.staff_call.with_user(self.erasmus_user)._ems_send_announce()
        self.assertEqual(sorted(self._mails(self.staff_call).mapped('email_to')),
                         ['announce.director@example.com', 'announce.fp@example.com'])

    def test_only_the_team_and_only_an_open_published_call(self):
        with self.assertRaises(AccessError):
            self.call.with_user(self.hos_user).action_announce()
        draft = self.call.copy()
        with self.assertRaises(UserError):
            draft.with_user(self.erasmus_user)._ems_send_announce()
        self.call.date_close = fields.Datetime.now() - timedelta(minutes=1)
        with self.assertRaises(UserError):
            self.call.with_user(self.erasmus_user)._ems_send_announce()
        self.assertFalse(self._mails(self.call) | self._mails(draft))

    def test_reminder_days_cannot_be_negative(self):
        with self.assertRaises(ValidationError):
            self.call.reminder_days = -1

    # --- the reminder before the closing date -------------------------------------------------

    def _remind_at(self, local_now):
        """Run the reminder with the centre's clock at `local_now` (naive, the centre's time)."""
        utils = self.env['ems.datetime_utils']
        with patch.object(type(utils), 'get_local_datetime', return_value=local_now.replace(tzinfo=utils.current_tz())):
            self.env['ems.erasmus.call']._cron_remind_closing()

    def test_reminder_to_who_has_not_submitted(self):
        Application = self.env['ems.erasmus.application']
        submitted = Application._ems_portal_get_or_create(self.call, self.student)
        upload(submitted, self.cv)
        submitted.action_submit()
        Application._ems_portal_get_or_create(self.call, self.minor)  # a draft does not count
        self.call.with_user(self.erasmus_user)._ems_send_announce()
        notice = self._mails(self.call)
        close_day = self.call._ems_local_date(self.call.date_close)
        morning = datetime.combine(close_day - timedelta(days=self.call.reminder_days), datetime.min.time())
        self._remind_at(morning - timedelta(days=1, hours=-10))
        self.assertFalse(self.call.reminder_date, "Not yet: more than the reminder days before closing.")
        self._remind_at(morning + timedelta(hours=7))
        self.assertFalse(self.call.reminder_date, "Not before 9:00.")
        self._remind_at(morning + timedelta(hours=10))
        reminder = self._mails(self.call) - notice
        self.assertEqual(reminder.mapped('email_to'), ['erasmus.minor@example.com'])
        self.assertEqual(self.call.reminder_count, 1)
        self._remind_at(morning + timedelta(hours=12))
        self.assertEqual(self._mails(self.call) - notice, reminder, "Only once.")

    def test_no_reminder_without_the_notice_or_with_zero_days(self):
        close_day = self.call._ems_local_date(self.call.date_close)
        noon = datetime.combine(close_day, datetime.min.time()) + timedelta(hours=12)
        self._remind_at(noon - timedelta(days=1))
        self.assertFalse(self._mails(self.call), "A call never announced from EMS never emails on its own.")
        self.call.with_user(self.erasmus_user)._ems_send_announce()
        self.call.reminder_days = 0
        notice = self._mails(self.call)
        self._remind_at(noon - timedelta(days=1))
        self.assertEqual(self._mails(self.call), notice)
