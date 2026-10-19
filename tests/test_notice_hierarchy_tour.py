from odoo.tests import HttpCase, tagged

from .common import create_head_of_studies_branch, mock_outgoing_email


@tagged('post_install', '-at_install')
class TestNoticeHierarchyTour(HttpCase):
    """A Department Chief's draft notice: the Head of Studies above them sends it from the form's
    Actions dropdown, a Head of Studies of another branch only reads it (issue #636)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # action_send() only queues a queue.job here; mocked anyway, as in test_notice_tour.py.
        mock_outgoing_email(cls)
        teacher = cls.env['hr.employee'].create({'name': 'Notice Hierarchy Tour Teacher', 'employee_type': 'teacher'})
        create_head_of_studies_branch(cls, 'NoticeHierTour', teacher)
        # message_post() (action_send's chatter) needs the acting user's email.
        for user in (cls.head_of_studies, cls.department_chief, cls.other_department_chief, cls.other_head_of_studies):
            user.email = f'{user.login}@example.com'
        # Written as the chief (create_uid), past their department's groups check.
        cls.notice = cls.env['ems.notice'].with_user(cls.department_chief).sudo().create({
            'subject': 'Hierarchy tour draft', 'message': '<p>Draft</p>', 'recipient_type': 'both',
            'notice_line_ids': [(0, 0, {'email': 'hierarchy.tour.recipient@example.com'})],
        })

    def test_head_of_studies_above_sends_the_chief_draft(self):
        self.start_tour("/odoo", "ems_notice_hierarchy_send", login=self.head_of_studies.login)
        self.assertEqual(self.notice.state, 'scheduled')
        self.assertEqual(self.notice.sent_by, self.head_of_studies)

    def test_head_of_studies_of_another_branch_only_reads_it(self):
        self.start_tour("/odoo", "ems_notice_hierarchy_read_only", login=self.other_head_of_studies.login)
        self.assertEqual(self.notice.state, 'draft')
