from datetime import date

from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase

from .common import create_level_study_group, mock_outgoing_email


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
        mock_outgoing_email(cls)

        cls.level, cls.study, cls.group = create_level_study_group(cls, 'TNOT', level={'name': 'Test Notice Level'}, study={
            'code': 'TNOT001', 'name': 'Test Notice Study',
        }, group={'acronym': 'TNOT'})
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

    # --- recipient_email_type ---------------------------------------------------------------

    def test_recipient_email_type_defaults_to_both(self):
        notice = self._notice()
        self.assertEqual(notice.recipient_email_type, 'both')

    def test_recipient_email_type_corporate_only_uses_corporate_email(self):
        self.minor_student.student_email = 'minor.student.corp@example.com'
        notice = self._notice(
            recipient_type='students', recipient_email_type='corporate',
            group_ids=[(6, 0, [self.group.id])],
        )
        notice._onchange_groups()
        emails = notice.notice_line_ids.mapped('email')
        self.assertEqual(emails, ['minor.student.corp@example.com'])
        self.minor_student.student_email = False

    def test_recipient_email_type_corporate_only_skips_and_warns_without_it(self):
        # Neither fixture student has a student_email (corporate) set.
        notice = self._notice(
            recipient_type='students', recipient_email_type='corporate',
            group_ids=[(6, 0, [self.group.id])],
        )
        result = notice._onchange_groups()
        self.assertFalse(notice.notice_line_ids)
        self.assertIn('warning', result)
        self.assertIn(self.minor_student.name, result['warning']['message'])
        self.assertIn(self.adult_no_share_student.name, result['warning']['message'])

    def test_recipient_email_type_personal_only_uses_personal_email(self):
        self.minor_student.student_email = 'minor.student.corp@example.com'
        notice = self._notice(
            recipient_type='students', recipient_email_type='personal',
            group_ids=[(6, 0, [self.group.id])],
        )
        notice._onchange_groups()
        emails = set(notice.notice_line_ids.mapped('email'))
        self.assertEqual(emails, {self.minor_student.email, self.adult_no_share_student.email})
        self.minor_student.student_email = False

    def test_recipient_email_type_both_sends_to_both_addresses_when_available(self):
        self.minor_student.student_email = 'minor.student.corp@example.com'
        notice = self._notice(
            recipient_type='students', recipient_email_type='both',
            group_ids=[(6, 0, [self.group.id])],
        )
        notice._onchange_groups()
        minor_lines = notice.notice_line_ids.filtered(lambda l: l.student_id == self.minor_student)
        adult_lines = notice.notice_line_ids.filtered(lambda l: l.student_id == self.adult_no_share_student)
        self.assertEqual(
            set(minor_lines.mapped('email')),
            {'minor.student.corp@example.com', self.minor_student.email},
        )
        # adult_no_share_student has no corporate email - "both" still sends the one it has.
        self.assertEqual(adult_lines.mapped('email'), [self.adult_no_share_student.email])
        self.minor_student.student_email = False

    def test_recipient_email_type_both_still_skips_and_warns_with_no_email_at_all(self):
        no_email_student = self.env['res.partner'].create({
            'name': 'No Email Student', 'contact_type': 'student', 'main_group_id': self.group.id,
        })
        notice = self._notice(
            recipient_type='students', recipient_email_type='both',
            group_ids=[(6, 0, [self.group.id])],
        )
        result = notice._onchange_groups()
        self.assertNotIn(no_email_student.id, notice.notice_line_ids.mapped('student_id.id'))
        self.assertIn('warning', result)
        self.assertIn(no_email_student.name, result['warning']['message'])

    def test_both_selection_labels_are_translated(self):
        # Regression coverage for a real gap found 2026-09-05: the "Both" option on
        # recipient_type had an empty msgstr in both ca_ES.po/es_ES.po despite the msgid
        # existing - a .po entry existing is necessary but not sufficient (see CLAUDE.md's
        # i18n verification rule), so this checks the actual runtime-translated label.
        recipient_type_selection = dict(
            self.env['ems.notice'].with_context(lang='es_ES').fields_get(['recipient_type'])
            ['recipient_type']['selection']
        )
        recipient_email_type_selection = dict(
            self.env['ems.notice'].with_context(lang='es_ES').fields_get(['recipient_email_type'])
            ['recipient_email_type']['selection']
        )
        self.assertEqual(recipient_type_selection['both'], 'Ambos')
        self.assertEqual(recipient_email_type_selection['both'], 'Ambos')

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

    # --- unlink --------------------------------------------------------------------------

    def test_unlink_allowed_when_draft(self):
        notice = self._notice()
        notice.unlink()
        self.assertFalse(notice.exists())

    def test_unlink_blocked_once_scheduled(self):
        notice = self._notice(
            group_ids=[(6, 0, [self.group.id])],
            use_schedule=True, scheduled_date='2099-01-01 00:00:00',
        )
        notice._onchange_groups()
        notice.action_send()
        with self.assertRaises(UserError):
            notice.unlink()
        notice.action_archive()
        self.assertFalse(notice.active)

    def test_unlink_blocked_message_is_translated(self):
        # Verifies the .po translation actually loaded and applies at runtime -
        # a msgid existing in the .po file is necessary but not sufficient (see
        # CLAUDE.md's i18n verification rule).
        notice = self._notice(
            group_ids=[(6, 0, [self.group.id])],
            use_schedule=True, scheduled_date='2099-01-01 00:00:00',
        )
        notice._onchange_groups()
        notice.action_send()
        with self.assertRaises(UserError) as cm:
            notice.with_context(lang='es_ES').unlink()
        self.assertIn('Archívalo en su lugar', str(cm.exception))


class TestNoticeLine(TransactionCase):
    """ems.notice.line — the per-recipient row."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)

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


class TestNoticeAccessControl(TransactionCase):
    """security/rules/communications.xml — who can see/edit which ems.notice records.

    Admin and Director see and can edit every notice. Head of Studies/Deputy Head of Studies
    and the Quality coordinator can also *see* every notice centre-wide (so they can supervise
    each other - `views/communications/notice/search.xml`'s "Show only mine" filter, defaulted
    on, keeps their default view comfortably scoped to their own), but can only create/edit/
    delete the ones they personally created.

    Regression coverage for a real bug found while first implementing this: rule_notice_own
    used to have no `groups` (global), which Odoo ANDs against every other rule - so the
    "admin sees all" rule was silently neutered and admins only ever saw their own notices
    too."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.admin_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Admin (Notice)', 'login': 'test_admin_notice', 'email': 'test_admin_notice@example.com',
            'groups_id': [(4, cls.env.ref('ems.group_academic_admin').id), (4, cls.env.ref('base.group_user').id)],
        })
        cls.director_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Director (Notice)', 'login': 'test_director_notice', 'email': 'test_director_notice@example.com',
            'groups_id': [(4, cls.env.ref('ems.group_director').id), (4, cls.env.ref('base.group_user').id)],
        })
        cls.hos_a_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test HOS A (Notice)', 'login': 'test_hos_a_notice', 'email': 'test_hos_a_notice@example.com',
            'groups_id': [(4, cls.env.ref('ems.group_head_of_studies').id), (4, cls.env.ref('base.group_user').id)],
        })
        cls.hos_b_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test HOS B (Notice)', 'login': 'test_hos_b_notice', 'email': 'test_hos_b_notice@example.com',
            'groups_id': [(4, cls.env.ref('ems.group_head_of_studies').id), (4, cls.env.ref('base.group_user').id)],
        })
        cls.quality_admin_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Quality Coordinator (Notice)', 'login': 'test_quality_admin_notice', 'email': 'test_quality_admin_notice@example.com',
            'groups_id': [(4, cls.env.ref('ems.group_quality_admin').id), (4, cls.env.ref('base.group_user').id)],
        })

        cls.notice_hos_a = cls.env['ems.notice'].with_user(cls.hos_a_user).create({
            'subject': 'HOS A notice', 'message': '<p>A</p>', 'recipient_type': 'both',
        })
        cls.notice_hos_b = cls.env['ems.notice'].with_user(cls.hos_b_user).create({
            'subject': 'HOS B notice', 'message': '<p>B</p>', 'recipient_type': 'both',
        })
        cls.notice_quality = cls.env['ems.notice'].with_user(cls.quality_admin_user).create({
            'subject': 'Quality notice', 'message': '<p>Q</p>', 'recipient_type': 'both',
        })

    def test_admin_sees_all_notices(self):
        found = self.env['ems.notice'].with_user(self.admin_user).search([
            ('id', 'in', (self.notice_hos_a | self.notice_hos_b | self.notice_quality).ids)
        ])
        self.assertEqual(len(found), 3)

    def test_director_sees_all_notices(self):
        found = self.env['ems.notice'].with_user(self.director_user).search([
            ('id', 'in', (self.notice_hos_a | self.notice_hos_b | self.notice_quality).ids)
        ])
        self.assertEqual(len(found), 3)

    def test_hos_sees_every_notice_for_supervision(self):
        found = self.env['ems.notice'].with_user(self.hos_a_user).search([
            ('id', 'in', (self.notice_hos_a | self.notice_hos_b | self.notice_quality).ids)
        ])
        self.assertEqual(len(found), 3)

    def test_hos_only_mine_filter_narrows_to_own(self):
        # The default UI filter's own domain, exercised directly (a tour test covers the
        # actual checkbox interaction/default-on state).
        found = self.env['ems.notice'].with_user(self.hos_a_user).search([
            ('id', 'in', (self.notice_hos_a | self.notice_hos_b | self.notice_quality).ids),
            ('create_uid', '=', self.hos_a_user.id),
        ])
        self.assertEqual(found, self.notice_hos_a)

    def test_other_hos_cannot_write_or_unlink(self):
        with self.assertRaises(AccessError):
            self.notice_hos_a.with_user(self.hos_b_user).write({'subject': 'Hijacked'})
        with self.assertRaises(AccessError):
            self.notice_hos_a.with_user(self.hos_b_user).unlink()

    def test_quality_coordinator_sees_every_notice_for_supervision(self):
        found = self.env['ems.notice'].with_user(self.quality_admin_user).search([
            ('id', 'in', (self.notice_hos_a | self.notice_hos_b | self.notice_quality).ids)
        ])
        self.assertEqual(len(found), 3)

    def test_quality_coordinator_cannot_write_others_notice(self):
        with self.assertRaises(AccessError):
            self.notice_hos_a.with_user(self.quality_admin_user).write({'subject': 'Hijacked'})

    def test_hos_can_read_but_not_write_others_notice_line(self):
        line = self.env['ems.notice.line'].with_user(self.hos_a_user).create({
            'notice_id': self.notice_hos_a.id, 'email': 'recipient@example.com',
        })
        found = self.env['ems.notice.line'].with_user(self.hos_b_user).search([('id', '=', line.id)])
        self.assertEqual(found, line, "HOS B should be able to read HOS A's notice line for supervision")
        with self.assertRaises(AccessError):
            line.with_user(self.hos_b_user).write({'email': 'hijacked@example.com'})


def base_encoded_png():
    import base64
    return base64.b64encode(b'\x89PNG\r\n\x1a\n').decode()
