from datetime import timedelta

from odoo.tests.common import TransactionCase

from .common import create_role_user


class TestActivitySnooze(TransactionCase):
    """Snoozing a task (issue #727, models/shared/mail_activity.py): Odoo's own "Snooze 7d" and
    EMS's "Snooze 1d"/"Snooze 3d" move its due date on from the company's today, or from its own
    due date when that is later. The daily summary only lists what is due, so a snoozed task
    leaves it until that day."""

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
        for method, days in (('action_ems_snooze_1d', 1), ('action_ems_snooze_3d', 3), ('action_snooze', 7)):
            with self.subTest(method=method):
                activity = self._activity(self.today - timedelta(days=4))
                getattr(activity, method)()
                self.assertEqual(activity.date_deadline, self.today + timedelta(days=days))

    def test_future_task_is_snoozed_from_its_own_date(self):
        for method, days in (('action_ems_snooze_1d', 1), ('action_ems_snooze_3d', 3), ('action_snooze', 7)):
            with self.subTest(method=method):
                activity = self._activity(self.today + timedelta(days=5))
                getattr(activity, method)()
                self.assertEqual(activity.date_deadline, self.today + timedelta(days=5 + days))

    def test_several_tasks_at_once(self):
        """The list's header button snoozes every selected task."""
        activities = self._activity(self.today) | self._activity(self.today - timedelta(days=1))
        activities.action_ems_snooze_3d()
        self.assertEqual(set(activities.mapped('date_deadline')), {self.today + timedelta(days=3)})
