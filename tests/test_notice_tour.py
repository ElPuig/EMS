from odoo.tests.common import HttpCase, tagged

from .common import create_level_study_group, force_user_language_to_english, mock_outgoing_email


@tagged('post_install', '-at_install')
class TestNoticeTour(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # action_send() -> with_delay().send_notification() only queues a queue.job row in
        # this test (no queue_job__no_delay), so no real send is at risk - mocked anyway for
        # consistency with the rest of this model's coverage (see CLAUDE.md).
        mock_outgoing_email(cls)

        # ems.group.name is computed from study_id.acronym/course/acronym for 'main' groups
        # (any override here is silently discarded) - give the group a distinctive acronym
        # instead, so the resulting computed name ('TNOTT1NOTC') is unique and searchable.
        cls.level, cls.study, cls.group = create_level_study_group(
            cls, 'TNOTT',
            level={'name': 'Test Level (Notice Tour)'},
            study={'code': 'TNOTT001', 'name': 'Test Study (Notice Tour)'},
            group={'acronym': 'NOTC'},
        )
        cls.student = cls.env['res.partner'].create({
            'name': 'Notice Tour Student', 'contact_type': 'student',
            'main_group_id': cls.group.id, 'email': 'notice.tour.student@example.com',
        })

    def test_notice_create_and_send_tour(self):
        # Both tours below assert on literal English button text ("Send now", "Close") - this
        # only works if admin's own language is en_US, which isn't guaranteed on every dev box
        # (this one's real admin is es_ES). Root cause of a failure that looked like a
        # timing/flake issue at first (a 10s TIMEOUT on the "Send now" step with no console
        # error or traceback): the button was actually there the whole time, just rendered as
        # "Enviar ahora" (confirmed via the tour's own failure screenshot) - see
        # [[project_notice_tour_preexisting_flake]] and CLAUDE.md's "Tour tests and language"
        # testing convention.
        force_user_language_to_english(self, self.env.ref('base.user_admin'))
        self.start_tour("/odoo", "ems_notice_create_and_send", login="admin")

        notice = self.env['ems.notice'].search([('subject', '=', 'Tour Notice Subject')])
        self.assertEqual(len(notice), 1)
        self.assertEqual(notice.state, 'scheduled')
        self.assertIn('Tour message body', notice.message)
        self.assertEqual(len(notice.notice_line_ids), 1)
        self.assertTrue(notice.notice_line_ids.notification_id)

    def test_notice_exception_popup_tour(self):
        force_user_language_to_english(self, self.env.ref('base.user_admin'))
        self.start_tour("/odoo", "ems_notice_create_and_send", login="admin")
        notice = self.env['ems.notice'].search([('subject', '=', 'Tour Notice Subject')])
        notice.notice_line_ids.notification_id.write({
            'state': 'failed', 'exc_info': 'Notice delivery failed (tour fixture).',
        })
        self.start_tour("/odoo", "ems_notice_exception_popup", login="admin")
