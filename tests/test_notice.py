from datetime import date
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestNotice(TransactionCase):
    """models/communications/notice.py — EmsNotice/EmsNoticeLine, a bulk email
    feature sent through Odoo's own mail_server (no external service
    involved — unlike ems.limesurvey*). Zero test coverage existed before
    this pass.

    send_notification() calls send_mail(force_send=True) — mocked for every
    test in this file per CLAUDE.md's email-safety rule. No test here uses
    queue_job__no_delay except where the full send pipeline is the thing
    under test, so most tests never risk a real send at all (with_delay()
    alone just queues a queue.job row, it doesn't execute it)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mail_server_patcher = patch(
            'odoo.addons.base.models.ir_mail_server.IrMailServer.send_email',
            return_value='test-message-id',
        )
        mail_server_patcher.start()
        cls.addClassCleanup(mail_server_patcher.stop)

        cls.level = cls.env['ems.level'].create({'acronym': 'TNOT', 'name': 'Test Notice Level'})
        cls.study = cls.env['ems.study'].create({
            'code': 'TNOT001', 'acronym': 'TNOT', 'name': 'Test Notice Study',
            'date': date.today(), 'deprecated': False, 'level_id': cls.level.id,
        })
        cls.group = cls.env['ems.group'].create({
            'course': 1, 'acronym': 'TNOT', 'level_id': cls.level.id, 'study_id': cls.study.id,
        })
        cls.relation_father = cls.env.ref('ems.relation_type_father')

        cls.minor_student = cls.env['res.partner'].create({
            'name': 'Notice Minor Student', 'contact_type': 'student', 'main_group_id': cls.group.id,
            'email': 'minor.student@example.com',
        })
        cls.minor_family = cls.env['res.partner'].create({
            'name': 'Notice Minor Family', 'contact_type': 'family', 'email': 'minor.family@example.com',
        })
        cls.env['res.partner.relation'].create({
            'left_partner_id': cls.minor_family.id, 'type_id': cls.relation_father.id,
            'right_partner_id': cls.minor_student.id,
        })

        cls.adult_no_share_student = cls.env['res.partner'].create({
            'name': 'Notice Adult No-Share Student', 'contact_type': 'student', 'main_group_id': cls.group.id,
            'email': 'adult.noshare@example.com', 'birth_date': date(2000, 1, 1),
        })
        cls.adult_no_share_family = cls.env['res.partner'].create({
            'name': 'Notice Adult No-Share Family', 'contact_type': 'family', 'email': 'adult.noshare.family@example.com',
        })
        cls.env['res.partner.relation'].create({
            'left_partner_id': cls.adult_no_share_family.id, 'type_id': cls.relation_father.id,
            'right_partner_id': cls.adult_no_share_student.id,
        })

    def _notice(self, **vals):
        base = {'subject': 'Test Subject', 'message': '<p>Hello</p>', 'recipient_type': 'both'}
        base.update(vals)
        return self.env['ems.notice'].create(base)

    # --- computed fields ---------------------------------------------------------------

    def test_display_name_falls_back_when_no_subject(self):
        notice = self.env['ems.notice'].new({})
        notice._compute_display_name()
        self.assertEqual(notice.display_name, "(New notice)")

    def test_recipient_count(self):
        notice = self._notice(group_ids=[(6, 0, [self.group.id])])
        notice._onchange_groups()
        self.assertEqual(notice.recipient_count, len(notice.notice_line_ids))
        self.assertGreater(notice.recipient_count, 0)

    def test_has_families(self):
        notice = self._notice(recipient_type='students')
        self.assertFalse(notice.has_families)
        notice.recipient_type = 'families'
        notice._compute_has_families()
        self.assertTrue(notice.has_families)

    def test_can_cancel_false_when_draft(self):
        notice = self._notice()
        self.assertFalse(notice.can_cancel)

    # --- _build_auto_lines / _onchange_groups ---------------------------------------------

    def test_students_only_creates_one_line_per_student(self):
        notice = self._notice(recipient_type='students', group_ids=[(6, 0, [self.group.id])])
        notice._onchange_groups()
        self.assertEqual(set(notice.notice_line_ids.mapped('recipient_type')), {'student'})
        self.assertEqual(len(notice.notice_line_ids), 2)

    def test_families_only_skips_adult_without_auth_share(self):
        notice = self._notice(recipient_type='families', group_ids=[(6, 0, [self.group.id])])
        notice._onchange_groups()
        emails = notice.notice_line_ids.mapped('email')
        self.assertIn(self.minor_family.email, emails)
        self.assertNotIn(self.adult_no_share_family.email, emails)

    def test_both_includes_students_and_eligible_families(self):
        notice = self._notice(recipient_type='both', group_ids=[(6, 0, [self.group.id])])
        notice._onchange_groups()
        emails = notice.notice_line_ids.mapped('email')
        self.assertIn(self.minor_student.email, emails)
        self.assertIn(self.minor_family.email, emails)
        self.assertIn(self.adult_no_share_student.email, emails)
        self.assertNotIn(self.adult_no_share_family.email, emails)

    def test_onchange_preserves_manual_lines(self):
        notice = self._notice(recipient_type='students')
        manual_partner = self.env['res.partner'].create({'name': 'Manual Recipient', 'email': 'manual@example.com'})
        notice.notice_line_ids = [(0, 0, {
            'partner_id': manual_partner.id, 'email': manual_partner.email, 'recipient_type': 'student',
        })]
        notice.group_ids = [(6, 0, [self.group.id])]
        notice._onchange_groups()
        emails = notice.notice_line_ids.mapped('email')
        self.assertIn(manual_partner.email, emails)
        self.assertIn(self.minor_student.email, emails)

    def test_onchange_dedupes_across_groups(self):
        other_group = self.env['ems.group'].create({
            'course': 1, 'acronym': 'TNOT2', 'level_id': self.level.id, 'study_id': self.study.id,
        })
        self.minor_student.main_group_id = other_group
        notice = self._notice(recipient_type='students', group_ids=[(6, 0, [self.group.id, other_group.id])])
        notice._onchange_groups()
        matching = notice.notice_line_ids.filtered(lambda l: l.email == self.minor_student.email)
        self.assertEqual(len(matching), 1)
        self.minor_student.main_group_id = self.group

    # --- action_send -----------------------------------------------------------------------

    def test_action_send_blocks_non_draft(self):
        notice = self._notice(group_ids=[(6, 0, [self.group.id])])
        notice._onchange_groups()
        notice.action_send()
        with self.assertRaises(UserError):
            notice.action_send()

    def test_action_send_blocks_empty_recipients(self):
        notice = self._notice()
        with self.assertRaises(UserError):
            notice.action_send()

    def test_action_send_queues_jobs_and_sets_scheduled(self):
        notice = self._notice(group_ids=[(6, 0, [self.group.id])])
        notice._onchange_groups()
        notice.action_send()
        self.assertEqual(notice.state, 'scheduled')
        self.assertEqual(notice.sent_by.id, self.env.uid)
        self.assertTrue(all(notice.notice_line_ids.mapped('notification_id')))

    # --- _check_and_finalize -----------------------------------------------------------------

    def test_finalize_stays_scheduled_while_pending(self):
        notice = self._notice(group_ids=[(6, 0, [self.group.id])])
        notice._onchange_groups()
        notice.action_send()
        notice._check_and_finalize()
        self.assertEqual(notice.state, 'scheduled')

    def test_finalize_moves_to_sent_when_all_done(self):
        # queue_job__no_delay executes send_notification() synchronously but
        # never persists a real queue.job row (the "NO JOB scheduled" log),
        # so action_send()'s own notification_id-from-job-uuid lookup finds
        # nothing and every line's display_status reads as 'draft' (pending)
        # forever. To test the actual state-machine transition, queue for
        # real (no no_delay) and flip the resulting jobs' state by hand,
        # rather than trying to drive it through real async execution.
        notice = self._notice(recipient_type='students', group_ids=[(6, 0, [self.group.id])])
        notice._onchange_groups()
        notice.action_send()
        notice.notice_line_ids.mapped('notification_id').write({'state': 'done'})
        notice._check_and_finalize()
        self.assertEqual(notice.state, 'sent')
        self.assertTrue(notice.sent_date)

    def test_finalize_moves_to_failed_when_any_failed(self):
        notice = self._notice(recipient_type='students', group_ids=[(6, 0, [self.group.id])])
        notice._onchange_groups()
        notice.action_send()
        jobs = notice.notice_line_ids.mapped('notification_id')
        jobs[0].write({'state': 'done'})
        jobs[1].write({'state': 'failed'})
        notice._check_and_finalize()
        self.assertEqual(notice.state, 'failed')

    # --- action_cancel ---------------------------------------------------------------------

    def test_action_cancel_blocked_when_cannot_cancel(self):
        notice = self._notice()
        with self.assertRaises(UserError):
            notice.action_cancel()

    def test_action_cancel_resets_to_draft(self):
        # can_cancel requires use_schedule=True — an immediate send is
        # considered already committed even before the queue processes it.
        notice = self._notice(
            group_ids=[(6, 0, [self.group.id])],
            use_schedule=True, scheduled_date='2099-01-01 00:00:00',
        )
        notice._onchange_groups()
        notice.action_send()
        notice.action_cancel()
        self.assertEqual(notice.state, 'draft')
        self.assertFalse(any(notice.notice_line_ids.mapped('notification_id')))


class TestNoticeLine(TransactionCase):
    """ems.notice.line — the per-recipient row."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mail_server_patcher = patch(
            'odoo.addons.base.models.ir_mail_server.IrMailServer.send_email',
            return_value='test-message-id',
        )
        mail_server_patcher.start()
        cls.addClassCleanup(mail_server_patcher.stop)

        cls.notice = cls.env['ems.notice'].create({
            'subject': 'Line Test Subject', 'message': '<p>Body</p>', 'recipient_type': 'students',
        })
        cls.partner = cls.env['res.partner'].create({'name': 'Notice Line Partner', 'email': 'line@example.com'})

    def _line(self):
        return self.env['ems.notice.line'].create({
            'notice_id': self.notice.id, 'partner_id': self.partner.id,
            'email': self.partner.email, 'recipient_type': 'student',
        })

    def test_display_status_defaults_to_draft(self):
        line = self._line()
        self.assertEqual(line.display_status, 'draft')

    def test_send_notification_finalizes_notice(self):
        # send_notification() itself never sets notification_id (that's
        # action_send()'s job, from the with_delay() job's uuid) — calling it
        # directly here only proves the email-send + finalize side, not the
        # notification-id bookkeeping (covered at the ems.notice level via
        # action_send in test_notice.py). _check_and_finalize is also a
        # no-op unless the notice is already 'scheduled'.
        line = self._line()
        self.notice.state = 'scheduled'
        line.send_notification()
        self.assertEqual(self.notice.state, 'sent')

    def test_prepare_body_for_email_empty_body_returned_as_is(self):
        line = self._line()
        self.assertEqual(line._prepare_body_for_email(''), '')
        self.assertFalse(line._prepare_body_for_email(False))

    def test_prepare_body_for_email_converts_data_uri_image(self):
        import base64
        line = self._line()
        png_1x1 = base64.b64encode(b'\x89PNG\r\n\x1a\n').decode()
        body = f'<p><img src="data:image/png;base64,{png_1x1}"/></p>'
        result = line._prepare_body_for_email(body)
        self.assertIn('/web/image/', str(result))
        self.assertIn('access_token=', str(result))
        attachment = self.env['ir.attachment'].search([
            ('res_model', '=', 'ems.notice.line'), ('res_id', '=', line.id),
        ])
        self.assertTrue(attachment)

    def test_prepare_body_for_email_adds_token_to_existing_attachment_image(self):
        line = self._line()
        attachment = self.env['ir.attachment'].create({
            'name': 'existing.png', 'datas': base_encoded_png(), 'mimetype': 'image/png',
        })
        body = f'<p><img src="/web/image/{attachment.id}"/></p>'
        result = line._prepare_body_for_email(body)
        attachment.invalidate_recordset(['access_token'])
        self.assertTrue(attachment.access_token)
        self.assertIn('access_token=%s' % attachment.access_token, str(result))

    def test_open_notification_form(self):
        # Build a real notification_id the same way production code does
        # (action_send()'s with_delay()), rather than hand-constructing a
        # queue.job whose required/computed fields aren't this test's concern.
        line = self._line()
        self.notice.action_send()
        self.assertTrue(line.notification_id)
        action = line.open_notification_form()
        self.assertEqual(action['res_model'], 'queue.job')
        self.assertEqual(action['res_id'], line.notification_id.id)

    def test_open_exception_popup(self):
        line = self._line()
        action = line.open_exception_popup()
        self.assertEqual(action['res_model'], 'ems.notice.line')
        self.assertEqual(action['res_id'], line.id)


def base_encoded_png():
    import base64
    return base64.b64encode(b'\x89PNG\r\n\x1a\n').decode()
