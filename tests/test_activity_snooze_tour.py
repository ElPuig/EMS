from datetime import timedelta

from odoo.tests.common import HttpCase, tagged

from .common import create_role_user


@tagged('post_install', '-at_install')
class TestActivitySnoozeTour(HttpCase):
    """Issue #727: a teacher snoozes their own tasks from My Activities (list and kanban)."""

    def test_activity_snooze_tour(self):
        teacher = create_role_user(self, 'teacher', 'snooze_tour_teacher', email='snooze.tour@example.com')
        partner = self.env['res.partner'].create({'name': 'Snooze Tour Record'})
        today = self.env['ems.datetime_utils'].get_local_today()
        activities = {
            letter: self.env['mail.activity'].with_context(mail_activity_quick_update=True).create({
                'res_model_id': self.env['ir.model']._get_id('res.partner'),
                'res_id': partner.id,
                'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
                'user_id': teacher.id,
                'summary': f'Snooze tour task {letter}',
                'date_deadline': today - timedelta(days=1),
            }) for letter in 'ABC'
        }
        self.start_tour("/odoo", "ems_activity_snooze", login=teacher.login)
        self.assertEqual(activities['A'].date_deadline, today + timedelta(days=1))
        self.assertEqual(activities['B'].date_deadline, today + timedelta(days=3))
        self.assertEqual(activities['C'].date_deadline, today - timedelta(days=1))
