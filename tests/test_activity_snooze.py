from datetime import timedelta

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase

from .common import create_role_user


class TestActivitySnooze(TransactionCase):
    """Snoozing a task (issue #727, models/shared/mail_activity.py): the row's popover and the
    header's dialog in My Activities both call action_ems_snooze(days), which moves the due date
    1, 3 or 7 days on from the company's today, or from its own due date when that is later. The
    daily summary only lists what is due, so a snoozed task leaves it until that day."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.teacher_user = create_role_user(cls, 'teacher', 'snooze_teacher', email='snooze.teacher@example.com')
        cls.partner = cls.env['res.partner'].create({'name': 'Snooze Test Record'})
        cls.today = cls.env['ems.datetime_utils'].get_local_today()

    def _activity(self, date_deadline):
        # quick_update: no "X assigned you a task" email.
        return self.env['mail.activity'].with_context(mail_activity_quick_update=True).create({
            'res_model_id': self.env['ir.model']._get_id('res.partner'),
            'res_id': self.partner.id,
            'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
            'user_id': self.teacher_user.id,
            'summary': 'Snooze test task',
            'date_deadline': date_deadline,
        }).with_user(self.teacher_user)

    def test_overdue_task_is_snoozed_from_today(self):
        for days in (1, 3, 7):
            with self.subTest(days=days):
                activity = self._activity(self.today - timedelta(days=4))
                activity.action_ems_snooze(days)
                self.assertEqual(activity.date_deadline, self.today + timedelta(days=days))

    def test_future_task_is_snoozed_from_its_own_date(self):
        for days in (1, 3, 7):
            with self.subTest(days=days):
                activity = self._activity(self.today + timedelta(days=5))
                activity.action_ems_snooze(days)
                self.assertEqual(activity.date_deadline, self.today + timedelta(days=5 + days))

    def test_only_the_offered_days(self):
        activity = self._activity(self.today)
        with self.assertRaises(UserError):
            activity.action_ems_snooze(2)
        self.assertEqual(activity.date_deadline, self.today)

    def test_odoo_snooze_counts_from_the_company_day(self):
        activity = self._activity(self.today - timedelta(days=1))
        activity.action_snooze()
        self.assertEqual(activity.date_deadline, self.today + timedelta(days=7))

    def test_header_dialog_snoozes_the_selected_tasks(self):
        activities = self._activity(self.today) | self._activity(self.today - timedelta(days=1))
        action = activities.action_ems_snooze_dialog()
        self.assertEqual((action['tag'], action['target']), ('ems.activity_snooze_dialog', 'new'))
        self.assertEqual(action['params']['activity_ids'], activities.ids)
        activities.action_ems_snooze(3)
        self.assertEqual(set(activities.mapped('date_deadline')), {self.today + timedelta(days=3)})

    def test_choices_come_from_the_server_rule(self):
        """The web client shows what the server offers: the days and, for one task, the date it
        would move to by the same rule action_ems_snooze applies."""
        overdue = self._activity(self.today - timedelta(days=2))
        later = self._activity(self.today + timedelta(days=5))
        self.assertEqual(overdue.ems_snooze_choices(), [
            {'days': days, 'date': str(self.today + timedelta(days=days))} for days in (1, 3, 7)])
        self.assertEqual([choice['date'] for choice in later.ems_snooze_choices()],
                         [str(self.today + timedelta(days=5 + days)) for days in (1, 3, 7)])
        self.assertEqual((overdue | later).ems_snooze_choices(),
                         [{'days': days, 'date': False} for days in (1, 3, 7)])
