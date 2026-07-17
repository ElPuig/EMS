# -*- coding: utf-8 -*-

from odoo import SUPERUSER_ID
from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase


class TestTaskAssignment(TransactionCase):
    """Who gets the tasks EMS schedules is configured per activity type, not derived
    from a security group (see Academic Management > Configuration > Task Assignment)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.doc_type = cls.env.ref('ems.mail_activity_student_document_review')
        cls.comment_type = cls.env.ref('ems.mail_activity_enrollment_comment')

        cls.reviewer = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Task Reviewer',
            'login': 'test_task_reviewer',
        })
        cls.other_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Unrelated User',
            'login': 'test_task_outsider',
        })
        cls.student = cls.env['res.partner'].create({'name': 'Task Assignment Student'})

        cls.doc_type.ems_assignee_ids = [(6, 0, cls.reviewer.ids)]

    def _create_document(self):
        return self.env['ems.student.document'].create({
            'partner_id': self.student.id,
            'doc_type': 'other',
            'status': 'pending',
        })

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------
    def test_ems_task_types_are_flagged(self):
        """Both EMS-scheduled types show up in the Task Assignment screen."""
        self.assertTrue(self.doc_type.ems_task_assignment)
        self.assertTrue(self.comment_type.ems_task_assignment)

    def test_task_users_are_the_configured_ones(self):
        self.assertEqual(self.doc_type._ems_task_users(), self.reviewer)

    def test_task_users_skip_archived_and_system_user(self):
        """Archived users and OdooBot never get a task: nobody reads their inbox."""
        archived = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Archived Reviewer',
            'login': 'test_task_archived',
        })
        odoobot = self.env['res.users'].browse(SUPERUSER_ID)
        self.doc_type.ems_assignee_ids = [(6, 0, (self.reviewer + archived + odoobot).ids)]
        archived.active = False

        self.assertEqual(self.doc_type._ems_task_users(), self.reviewer)

    def test_task_users_of_missing_type(self):
        """An unknown xmlid yields no recipient instead of blowing up."""
        users = self.env['mail.activity.type']._ems_get_task_users('ems.does_not_exist')
        self.assertFalse(users)

    # ------------------------------------------------------------------
    # Document review tasks
    # ------------------------------------------------------------------
    def test_document_schedules_task_for_assignees_only(self):
        document = self._create_document()

        activities = document.activity_ids
        self.assertEqual(activities.activity_type_id, self.doc_type)
        self.assertEqual(activities.user_id, self.reviewer)
        self.assertNotIn(self.other_user, activities.user_id)

    def test_document_reviewers_are_not_followers(self):
        """The to-do is the reviewer's only notice: no email on every status change.

        The student, on the other hand, must stay a follower — they are the one who
        needs to hear back about their own document.
        """
        document = self._create_document()

        follower_partners = document.message_partner_ids
        self.assertIn(self.student, follower_partners)
        self.assertNotIn(self.reviewer.partner_id, follower_partners)

    def _assignation_notified_partners(self, document):
        """Partners emailed the "assigned to you" notice for this document.

        These messages are ``user_notification``, a type the chatter deliberately hides,
        so they are not in ``document.message_ids`` — they have to be searched for.
        """
        messages = self.env['mail.message'].search([
            ('model', '=', 'ems.student.document'),
            ('res_id', '=', document.id),
            ('message_type', '=', 'user_notification'),
        ])
        return messages.notification_ids.res_partner_id

    def test_document_reviewers_get_no_assignation_email(self):
        """mail.activity.create() emails every assignee ("X has assigned you...") unless
        the mail_activity_quick_update context is set. The reviewer's notice is the
        systray task — and the author of that email would be the family who uploaded the
        document from the portal, which reads as if a family assigned work to the office.
        """
        document = self._create_document()

        self.assertNotIn(self.reviewer.partner_id, self._assignation_notified_partners(document))

    def test_document_without_assignees_schedules_nothing(self):
        """An empty recipient list creates no task (and no crash)."""
        self.doc_type.ems_assignee_ids = [(5, 0, 0)]

        document = self._create_document()

        self.assertFalse(document.activity_ids)
        self.assertIn(self.student, document.message_partner_ids)

    def test_document_reset_to_pending_reschedules_task(self):
        document = self._create_document()
        document.action_approve()
        self.assertFalse(document.activity_ids)

        document.action_reset_to_pending()

        self.assertEqual(document.activity_ids.user_id, self.reviewer)

    # ------------------------------------------------------------------
    # Who may configure the assignment
    # ------------------------------------------------------------------
    def test_secretary_admin_can_configure_the_assignment(self):
        """The Secretary Administrator runs the office, so they decide who handles
        its tasks — Odoo natively reserves mail.activity.type to base.group_system."""
        secretary_admin = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Secretary Administrator',
            'login': 'test_task_secretary_admin',
            'groups_id': [(4, self.env.ref('ems.group_secretary_admin').id)],
        })

        self.doc_type.with_user(secretary_admin).ems_assignee_ids = [(6, 0, self.other_user.ids)]

        self.assertEqual(self.doc_type._ems_task_users(), self.other_user)

    def test_secretary_admin_cannot_touch_other_activity_types(self):
        """Their write access is confined to the task types EMS manages: the ACL alone
        would also let them rename every other activity type in the database."""
        secretary_admin = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Secretary Administrator',
            'login': 'test_task_secretary_admin_2',
            'groups_id': [(4, self.env.ref('ems.group_secretary_admin').id)],
        })
        native_type = self.env.ref('mail.mail_activity_data_todo')

        with self.assertRaises(AccessError):
            native_type.with_user(secretary_admin).name = 'Hijacked'

    def test_academic_admin_no_longer_inherits_system_access(self):
        """group_academic_admin no longer implies group_secretary_admin/group_settings_admin
        (permission blocks are independent - see security/groups.xml), so an Academic
        Administrator without group_settings_admin has no base.group_system access and
        can't touch activity types outside what group_academic_admin's own ACLs allow."""
        academic_admin = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Academic Administrator',
            'login': 'test_task_academic_admin',
            'groups_id': [(4, self.env.ref('ems.group_academic_admin').id)],
        })
        native_type = self.env.ref('mail.mail_activity_data_todo')

        with self.assertRaises(AccessError):
            native_type.with_user(academic_admin).name = 'Renamed by the administrator'

    def test_assignment_is_independent_from_security_groups(self):
        """The reviewer holds no EMS group, and a secretary who is not on the list
        gets no task: the two concepts are decoupled."""
        secretary = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Secretary Without Tasks',
            'login': 'test_task_secretary',
            'groups_id': [(4, self.env.ref('ems.group_secretary').id)],
        })

        document = self._create_document()

        self.assertFalse(self.reviewer.has_group('ems.group_secretary'))
        self.assertNotIn(secretary, document.activity_ids.user_id)
