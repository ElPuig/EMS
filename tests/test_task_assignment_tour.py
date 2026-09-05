from odoo.tests.common import HttpCase, tagged

from .common import force_user_language_to_english


@tagged('post_install', '-at_install')
class TestTaskAssignmentTour(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.activity_type = cls.env.ref('ems.mail_activity_enrollment_comment')
        cls.activity_type.ems_assignee_ids = [(5, 0, 0)]

    def test_task_assignment_edit_tour(self):
        force_user_language_to_english(self, self.env.ref('base.user_admin'))
        self.assertFalse(self.activity_type.ems_assignee_ids)

        self.start_tour("/odoo", "ems_task_assignment_edit", login="admin")

        self.assertEqual(self.activity_type.ems_assignee_ids, self.env.ref('base.user_admin'))
