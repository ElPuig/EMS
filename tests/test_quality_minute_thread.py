# -*- coding: utf-8 -*-

from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged

from .common import create_role_employee, create_role_user, ensure_catchall_address, mock_outgoing_email

REPLY = """From: {sender}
To: {to}
Subject: Re: TMTH
Message-Id: <tmth-reply-{number}@example.com>
In-Reply-To: {parent}
References: {parent}
MIME-Version: 1.0
Content-Type: text/html; charset="utf-8"

<div>{text}</div><blockquote>On Monday somebody wrote: the whole opening email</blockquote>
"""


@tagged('post_install', '-at_install')
class TestQualityMinuteThread(TransactionCase):
    """A meeting held by email (issue #822): a modality of any meeting minute. Its thread is the
    meeting: every answer is written under any other business, a participant can also intervene on
    an item from EMS, and the answers to the draft stay in the minute's history."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # As the real transport does, hand back the email's own Message-Id: an answer refers to it.
        cls.mail_transport = mock_outgoing_email(cls)
        cls.mail_transport.side_effect = lambda message, *args, **kwargs: message['Message-Id']
        cls.env.company.ems_lang = 'en_US'
        ensure_catchall_address(cls)  # a fresh database (CI) has no alias domain: the opening needs the catchall as reply address
        cls.env.company.alias_domain_id.write({'bounce_alias': 'bounce.tmth', 'catchall_alias': 'answers.tmth'})
        cls.type = cls.env.ref('__import__.minute_type_generic')
        cls.writer_user = create_role_user(cls, 'teacher', 'tmth.writer@example.com', name='TMTH Writer',
                                           email='tmth.writer@example.com')
        cls.writer = create_role_employee(cls, cls.writer_user)
        cls.writer.work_email = 'tmth.writer@example.com'
        cls.other_user = create_role_user(cls, 'teacher', 'tmth.other@example.com', name='TMTH Other',
                                          email='tmth.other@example.com')
        cls.other = create_role_employee(cls, cls.other_user)
        cls.other.work_email = 'tmth.other@example.com'
        # Whoever reads their notifications inside Odoo still gets the thread by email.
        cls.other_user.notification_type = 'inbox'
        cls.silent_user = create_role_user(cls, 'teacher', 'tmth.silent@example.com', name='TMTH Silent',
                                           email='tmth.silent@example.com')
        cls.silent = create_role_employee(cls, cls.silent_user)
        cls.silent.work_email = 'tmth.silent@example.com'
        public = cls.env['hr.employee.public']
        cls.writer_public, cls.other_public, cls.silent_public = (
            public.browse(cls.writer.id), public.browse(cls.other.id), public.browse(cls.silent.id))

    def _thread(self, **overrides):
        vals = {
            'type_id': self.type.id,
            'scope_choice': 'none',
            'modality': 'email',
            'redactor_employee_id': self.writer_public.id,
            'approver_employee_id': self.writer_public.id,
            'attendee_ids': [(6, 0, (self.writer_public | self.other_public | self.silent_public).ids)],
            'reply_deadline': fields.Date.today() + timedelta(days=7),
            'agenda_ids': [(0, 0, {'sequence': 1, 'name': 'TMTH first item'}), (0, 0, {'sequence': 2, 'name': 'TMTH second item'})],
        }
        vals.update(overrides)
        return self.env['ems.minute'].with_user(self.writer_user).create(vals)

    def _open(self, **overrides):
        minute = self._thread(**overrides)
        minute.with_user(self.writer_user).action_start_meeting()
        return minute

    def _requests(self, minute):
        return minute.section_value_ids.filtered(lambda value: value.kind == 'requests').content or ''

    def _last_post(self, minute):
        """What was last written on the thread for the participants."""
        return minute.message_ids.filtered(lambda message: message.message_type in ('comment', 'email')
                                           and message.subtype_id == self.env.ref('mail.mt_comment'))[:1]

    def _answer(self, minute, sender, text, number):
        catchall = ensure_catchall_address(self)
        self.env['mail.thread'].message_process(False, REPLY.format(
            sender=sender, to=catchall, parent=self._last_post(minute).message_id, number=number, text=text))
        minute.invalidate_recordset()

    def _intervene(self, minute, user, texts):
        """Fill the wizard's blocks as the participant would: `texts` maps an item (or None, for any
        other business) to what they say; the other blocks stay empty."""
        Wizard = self.env['ems.minute.intervention.wizard'].with_user(user).with_context(default_minute_id=minute.id)
        wizard = Wizard.create(Wizard.default_get(['minute_id', 'line_ids']))
        for line in wizard.line_ids:
            text = texts.get(line.agenda_id or None)
            if text:
                line.body = f'<p>{text}</p>'
        wizard.action_confirm()
        minute.invalidate_recordset()

    def test_by_email_is_a_modality_of_any_meeting(self):
        """The minute keeps its own type, so it stays in line with the other minutes of its scope."""
        minute = self._thread()
        self.assertEqual(minute.type_kind, 'meeting')
        self.assertEqual(minute.attendance_mode, 'manual')
        self.assertFalse(minute.presence_id)
        self.assertEqual(minute.place_name, 'By email')

    def test_only_a_type_with_any_other_business_can_be_held_by_email(self):
        minute = self._thread(modality='in-person', start_datetime=fields.Datetime.now())
        minute.section_value_ids.filtered(lambda value: value.kind == 'requests').unlink()
        self.type.section_ids.filtered(lambda line: line.kind == 'requests').unlink()
        with self.assertRaisesRegex(ValidationError, 'any other business'):
            minute.modality = 'email'

    def test_no_call_is_sent_for_a_thread(self):
        minute = self._thread()
        with self.assertRaises(UserError):
            minute.with_user(self.writer_user).action_send_call()

    def test_opening_needs_a_deadline(self):
        minute = self._thread(reply_deadline=False)
        with self.assertRaises(UserError):
            minute.with_user(self.writer_user).action_start_meeting()
        self.assertEqual(minute.state, 'draft')

    def test_opening_emails_everybody_and_starts_them_all_as_absentees(self):
        minute = self._open()

        self.assertEqual(minute.state, 'meeting')
        self.assertFalse(minute.attendee_ids)
        self.assertEqual(minute.absentee_ids, self.writer_public | self.other_public | self.silent_public)
        opening = self._last_post(minute)
        self.assertIn('TMTH first item', opening.body)
        self.assertIn(ensure_catchall_address(self), opening.reply_to)
        # A participant who reads notifications in Odoo is emailed too: the thread is a mailing list.
        notification = opening.notification_ids.filtered(lambda line: line.res_partner_id == self.other_user.partner_id)
        self.assertEqual(notification.notification_type, 'email')
        # Opening it is not anybody's intervention.
        self.assertNotIn('TMTH', self._requests(minute))
        # Sent inside the meetings card layout, which asks for an answer instead of saying none is needed.
        self.assertEqual(opening.email_layout_xmlid, 'ems.mail_layout_minutes')
        sent = self.mail_transport.call_args.args[0].get_body(('html',)).get_content()
        self.assertIn('Answer this message to take part', sent)
        self.assertNotIn('There is no need to reply', sent)

    def test_whoever_has_not_answered_yet_can_read_it(self):
        """They start among the absentees, and still open the minute and its draft from the emails."""
        minute = self._open()
        self.assertIn(self.silent_public, minute.absentee_ids)
        minute.with_user(self.silent_user).check_access('read')

    def test_an_opened_thread_cannot_go_back_to_preparing(self):
        minute = self._open()
        with self.assertRaises(UserError):
            minute.with_user(self.writer_user).action_back_to_draft()

    def test_an_answer_goes_under_any_other_business_and_makes_its_author_an_attendee(self):
        minute = self._open()

        self._answer(minute, 'TMTH Other <tmth.other@example.com>', 'TMTH I agree with the item', 1)

        requests = self._requests(minute)
        self.assertIn(self.other.name, requests)
        self.assertIn('TMTH I agree with the item', requests)
        self.assertNotIn('the whole opening email', requests)
        self.assertEqual(minute.attendee_ids, self.other_public)
        self.assertNotIn(self.other_public, minute.absentee_ids)
        # Whoever opened it follows the thread and gets the answer, as in a mailing list, in the meetings layout.
        message = self._last_post(minute)
        self.assertIn(self.writer_user.partner_id, message.notified_partner_ids)
        self.assertEqual(message.email_layout_xmlid, 'ems.mail_layout_minutes')

    def test_an_answer_from_an_unknown_address_is_written_but_names_nobody_as_attendee(self):
        minute = self._open()

        self._answer(minute, 'Somebody <tmth.personal@example.com>', 'TMTH from home', 2)

        self.assertIn('TMTH from home', self._requests(minute))
        self.assertFalse(minute.attendee_ids)

    def test_a_message_written_in_the_history_is_an_intervention_too(self):
        minute = self._open()

        minute.with_user(self.writer_user).message_post(
            body='TMTH written in EMS', message_type='comment', subtype_xmlid='mail.mt_comment')
        minute.with_user(self.writer_user).message_post(body='TMTH a note', message_type='comment', subtype_xmlid='mail.mt_note')

        self.assertIn('TMTH written in EMS', self._requests(minute))
        self.assertNotIn('TMTH a note', self._requests(minute), "a note is not said to the participants")
        self.assertEqual(minute.attendee_ids, self.writer_public)

    def test_a_participant_intervenes_on_an_item_from_ems(self):
        """A teacher who only reads the minute writes on an item: it lands in that item's notes and
        goes to everybody by the thread, saying which item it is about."""
        minute = self._open()
        second = minute.agenda_ids.filtered(lambda item: item.name == 'TMTH second item')
        self.assertTrue(minute.with_user(self.other_user).can_intervene)
        self.mail_transport.reset_mock()

        self._intervene(minute, self.other_user, {second: 'TMTH about the second item'})

        self.assertIn('TMTH about the second item', second.notes)
        self.assertIn(self.other.name, second.notes)
        self.assertNotIn('TMTH about the second item', self._requests(minute), "not written twice")
        self.assertEqual(minute.attendee_ids, self.other_public)
        post = self._last_post(minute)
        self.assertEqual(post.author_id, self.other_user.partner_id)
        self.assertIn('On item 2: TMTH second item', post.body)
        self.assertTrue(self.mail_transport.called, "everybody gets it by email")

    def test_a_participant_intervention_with_no_item_goes_under_any_other_business(self):
        minute = self._open()
        self._intervene(minute, self.silent_user, {None: 'TMTH in general'})
        self.assertIn('TMTH in general', self._requests(minute))

    def test_interventions_on_several_items_go_in_a_single_email(self):
        minute = self._open()
        first, second = minute.agenda_ids.sorted('sequence')
        posts_before = len(minute.message_ids)

        self._intervene(minute, self.other_user, {first: 'TMTH on the first', second: 'TMTH on the second', None: 'TMTH in general'})

        self.assertIn('TMTH on the first', first.notes)
        self.assertIn('TMTH on the second', second.notes)
        self.assertIn('TMTH in general', self._requests(minute))
        self.assertEqual(len(minute.message_ids) - posts_before, 1, "one message, so one email to everybody")
        post = self._last_post(minute)
        self.assertIn('On item 1: TMTH first item', post.body)
        self.assertIn('On item 2: TMTH second item', post.body)
        self.assertIn('TMTH in general', post.body)

    def test_an_empty_wizard_adds_nothing(self):
        minute = self._open()
        with self.assertRaises(UserError):
            self._intervene(minute, self.other_user, {})

    def test_only_the_people_convened_intervene_while_it_is_open(self):
        outsider = create_role_user(self, 'teacher', 'tmth.outsider@example.com', name='TMTH Outsider')
        create_role_employee(self, outsider)
        minute = self._thread()
        self.assertFalse(minute.with_user(self.other_user).can_intervene, "not before it is opened")
        minute.with_user(self.writer_user).action_start_meeting()
        with self.assertRaises(Exception):
            self._intervene(minute, outsider, {None: 'TMTH not convened'})

    def test_whoever_is_taken_off_the_lists_stops_getting_the_thread(self):
        minute = self._open()
        self.assertIn(self.silent_user.partner_id, minute.message_partner_ids)

        minute.with_user(self.writer_user).absentee_ids = [(3, self.silent_public.id)]

        self.assertNotIn(self.silent_user.partner_id, minute.message_partner_ids)
        self.assertIn(self.other_user.partner_id, minute.message_partner_ids)

    def test_answers_to_the_draft_stay_in_the_history_and_do_not_hold_the_approval(self):
        minute = self._open()
        self._intervene(minute, self.other_user, {minute.agenda_ids.sorted('sequence')[:1]: 'TMTH I agree'})
        minute.with_user(self.writer_user).action_submit()
        minute.with_user(self.writer_user).action_send_draft()
        self.assertIn('/report/pdf/ems.report_minute/', self._last_post(minute).body)

        self._answer(minute, 'TMTH Other <tmth.other@example.com>', 'TMTH please correct my name', 4)

        self.assertNotIn('TMTH please correct my name', self._requests(minute))
        self.assertTrue(minute.message_ids.filtered(lambda message: 'TMTH please correct my name' in (message.body or '')))
        minute.with_user(self.writer_user).action_approve()
        self.assertEqual(minute.state, 'approved')
        # The approved minute closes the thread: everybody gets the link to its approved PDF.
        approved = self._last_post(minute)
        self.assertIn(f'/web/content/{minute.pdf_attachment_id.id}', approved.body)
        self.assertIn(self.other_user.partner_id, approved.notified_partner_ids)

    def test_the_pdf_prints_the_interventions(self):
        minute = self._open()
        self._answer(minute, 'TMTH Other <tmth.other@example.com>', 'TMTH printed intervention', 5)

        html = self.env['ir.actions.report']._render_qweb_html('ems.report_minute', minute.ids)[0].decode()

        self.assertIn('TMTH printed intervention', html)
        self.assertNotIn('the whole opening email', html)
