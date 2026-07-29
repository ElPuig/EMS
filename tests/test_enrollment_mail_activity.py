from odoo.tests.common import TransactionCase

from .common import create_level_study


class TestEnrollmentMailActivity(TransactionCase):
    """models/enrollment/mail_activity.py — ResUsers._get_activity_groups()
    relabeling and MailActivity._action_done()/unlink() cascade for the
    enrollment-comment review activity. Who gets assigned the activity
    (ems.mail_activity_type.ems_assignee_ids) is already covered by
    tests/test_task_assignment.py — not duplicated here."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.comment_type = cls.env.ref('ems.mail_activity_enrollment_comment')
        cls.reviewer1 = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Comment Reviewer 1', 'login': 'test_comment_reviewer1',
            'groups_id': [(4, cls.env.ref('base.group_user').id), (4, cls.env.ref('ems.group_secretary').id)],
        })
        cls.reviewer2 = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Comment Reviewer 2', 'login': 'test_comment_reviewer2',
            'groups_id': [(4, cls.env.ref('base.group_user').id), (4, cls.env.ref('ems.group_secretary').id)],
        })
        cls.comment_type.ems_assignee_ids = [(6, 0, (cls.reviewer1 | cls.reviewer2).ids)]

        cls.course = cls.env['ems.course'].search([('is_enrollment_default', '=', True)], limit=1) \
            or cls.env['ems.course'].create({'start': 2098, 'end': 2099, 'is_enrollment_default': True})
        cls.level, cls.study = create_level_study(cls, 'TMA', level={'name': 'Test Mail Activity Level'}, study={
            'code': 'TMA001', 'acronym': 'TMAS', 'name': 'Test Mail Activity Study',
        })
        cls.student = cls.env['res.partner'].create({'name': 'Mail Activity Student', 'contact_type': 'student'})
        cls.order = cls.env['sale.order'].create({
            'partner_id': cls.student.id, 'ems_study_id': cls.study.id, 'ems_course_id': cls.course.id,
        })

    # --- ResUsers._get_activity_groups ---------------------------------------------

    def test_sale_order_activity_group_relabeled_enrollments(self):
        self.order.sudo()._ems_schedule_comment_review_activities()
        # _get_activity_groups is @api.model — it reads self.env.uid, not
        # the recordset it's called on.
        groups = self.env['res.users'].with_user(self.reviewer1).with_context(
            lang='en_US')._get_activity_groups()
        sale_group = next((g for g in groups if g.get('model') == 'sale.order'), None)
        self.assertIsNotNone(sale_group)
        self.assertEqual(sale_group['name'], 'Enrollments')

    # --- MailActivity._action_done ---------------------------------------------------

    def test_marking_comment_review_done_posts_message_on_enrollment(self):
        self.order.sudo()._ems_schedule_comment_review_activities()
        activity = self.order.activity_ids.filtered(
            lambda a: a.activity_type_id == self.comment_type and a.user_id == self.reviewer1)
        message_count_before = len(self.order.message_ids)
        activity.action_done()
        self.assertGreater(len(self.order.message_ids), message_count_before)
        last_message = self.order.message_ids.sorted('id')[-1]
        self.assertIn('reviewed by the secretary', last_message.body)

    def test_marking_comment_review_done_includes_feedback(self):
        self.order.sudo()._ems_schedule_comment_review_activities()
        activity = self.order.activity_ids.filtered(
            lambda a: a.activity_type_id == self.comment_type and a.user_id == self.reviewer1)
        activity.action_feedback(feedback='All good, proceeding.')
        last_message = self.order.message_ids.sorted('id')[-1]
        self.assertIn('All good, proceeding.', last_message.body)

    def test_action_done_on_unrelated_activity_does_not_post_review_notice(self):
        # Odoo always logs a generic "activity done" chatter entry regardless
        # of type — only the enrollment-comment-specific review notice
        # ("reviewed by the secretary's office") must NOT appear here.
        other_type = self.env.ref('mail.mail_activity_data_todo')
        activity = self.order.activity_schedule(
            activity_type_id=other_type.id, user_id=self.reviewer1.id)
        activity.action_done()
        bodies = self.order.message_ids.mapped('body')
        self.assertFalse(any('reviewed by the secretary' in b for b in bodies))

    # --- MailActivity.unlink cascade ------------------------------------------------

    def test_resolving_one_reviewers_activity_removes_the_others(self):
        self.order.sudo()._ems_schedule_comment_review_activities()
        activities = self.order.activity_ids.filtered(lambda a: a.activity_type_id == self.comment_type)
        self.assertEqual(len(activities), 2)
        activities.filtered(lambda a: a.user_id == self.reviewer1).unlink()
        remaining = self.order.activity_ids.filtered(lambda a: a.activity_type_id == self.comment_type)
        self.assertFalse(remaining)

    def test_cascade_context_prevents_infinite_recursion(self):
        self.order.sudo()._ems_schedule_comment_review_activities()
        activities = self.order.activity_ids.filtered(lambda a: a.activity_type_id == self.comment_type)
        # Simulates the sibling-cascade's own unlink call: must not re-trigger
        # another search-and-cascade pass.
        activities.with_context(ems_activity_cascade=True).unlink()
        self.assertFalse(self.order.activity_ids.filtered(lambda a: a.activity_type_id == self.comment_type))

    def test_unlink_does_not_cascade_across_different_enrollments(self):
        other_student = self.env['res.partner'].create({'name': 'Other Mail Activity Student', 'contact_type': 'student'})
        other_order = self.env['sale.order'].create({
            'partner_id': other_student.id, 'ems_study_id': self.study.id, 'ems_course_id': self.course.id,
        })
        self.order.sudo()._ems_schedule_comment_review_activities()
        other_order.sudo()._ems_schedule_comment_review_activities()

        self.order.activity_ids.filtered(
            lambda a: a.activity_type_id == self.comment_type and a.user_id == self.reviewer1).unlink()

        self.assertTrue(other_order.activity_ids.filtered(lambda a: a.activity_type_id == self.comment_type))
