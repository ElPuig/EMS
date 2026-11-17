# -*- coding: utf-8 -*-

from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError
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
    """A meeting held by email (issue #822): the minute's thread is the meeting, every answer is
    filed as its author's intervention, and the answers to the draft are its amendments."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # As the real transport does, hand back the email's own Message-Id: an answer refers to it.
        cls.mail_transport = mock_outgoing_email(cls)
        cls.mail_transport.side_effect = lambda message, *args, **kwargs: message['Message-Id']
        cls.env.company.ems_lang = 'en_US'
        cls.env.company.alias_domain_id.write({'bounce_alias': 'bounce.tmth', 'catchall_alias': 'answers.tmth'})
        cls.type = cls.env.ref('__import__.minute_type_email_thread')
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
            'redactor_employee_id': self.writer_public.id,
            'attendee_ids': [(6, 0, (self.writer_public | self.other_public | self.silent_public).ids)],
            'reply_deadline': fields.Date.today() + timedelta(days=7),
            'agenda_ids': [(0, 0, {'name': 'TMTH item'})],
        }
        vals.update(overrides)
        return self.env['ems.minute'].with_user(self.writer_user).create(vals)

    def _last_post(self, minute):
        """What EMS last wrote on the thread for the participants: the opening, or the draft."""
        return minute.message_ids.filtered(lambda message: message.message_type == 'comment'
                                           and message.subtype_id == self.env.ref('mail.mt_comment'))[:1]

    def _answer(self, minute, sender, text, number):
        catchall = ensure_catchall_address(self)
        self.env['mail.thread'].message_process(False, REPLY.format(
            sender=sender, to=catchall, parent=self._last_post(minute).message_id, number=number, text=text))
        minute.invalidate_recordset()

    def test_the_seeded_type_has_no_meeting_parts(self):
        minute = self._thread()
        self.assertEqual(minute.type_kind, 'email_thread')
        self.assertEqual(minute.attendance_mode, 'manual')
        self.assertFalse(minute.presence_id)
        self.assertEqual(minute.place_name, 'By email')

    def test_with_no_particular_scope_whoever_writes_it_approves_it(self):
        minute = self._thread()
        self.assertEqual(minute.approver_employee_id, self.writer_public)

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
        minute = self._thread()
        minute.with_user(self.writer_user).action_start_meeting()

        self.assertEqual(minute.state, 'meeting')
        self.assertFalse(minute.attendee_ids)
        self.assertEqual(minute.absentee_ids, self.writer_public | self.other_public | self.silent_public)
        opening = self._last_post(minute)
        self.assertIn('TMTH item', opening.body)
        self.assertIn(ensure_catchall_address(self), opening.reply_to)
        # A participant who reads notifications in Odoo is emailed too: the thread is a mailing list.
        notification = opening.notification_ids.filtered(lambda line: line.res_partner_id == self.other_user.partner_id)
        self.assertEqual(notification.notification_type, 'email')
        # Opening it is not anybody's intervention.
        self.assertFalse(minute.intervention_ids)
        # Sent inside the meetings card layout, which asks for an answer instead of saying none is needed.
        self.assertEqual(opening.email_layout_xmlid, 'ems.mail_layout_minutes')
        sent = self.mail_transport.call_args.args[0].get_body(('html',)).get_content()
        self.assertIn('Answer this message to take part', sent)
        self.assertNotIn('There is no need to reply', sent)

    def test_whoever_has_not_answered_yet_can_read_it(self):
        """They start among the absentees, and still open the minute and its draft from the emails."""
        minute = self._thread()
        minute.with_user(self.writer_user).action_start_meeting()
        self.assertIn(self.silent_public, minute.absentee_ids)
        minute.with_user(self.silent_user).check_access('read')

    def test_an_opened_thread_cannot_go_back_to_preparing(self):
        minute = self._thread()
        minute.with_user(self.writer_user).action_start_meeting()
        with self.assertRaises(UserError):
            minute.with_user(self.writer_user).action_back_to_draft()

    def test_an_answer_is_filed_without_the_quoted_text_and_makes_its_author_an_attendee(self):
        minute = self._thread()
        minute.with_user(self.writer_user).action_start_meeting()

        self._answer(minute, 'TMTH Other <tmth.other@example.com>', 'TMTH I agree with the item', 1)

        intervention = minute.intervention_ids
        self.assertEqual(len(intervention), 1)
        self.assertEqual(intervention.employee_id, self.other_public)
        self.assertEqual(intervention.author_name, self.other.name)
        self.assertIn('TMTH I agree with the item', intervention.body)
        self.assertNotIn('the whole opening email', intervention.body)
        self.assertEqual(minute.attendee_ids, self.other_public)
        self.assertNotIn(self.other_public, minute.absentee_ids)
        # Whoever opened it follows the thread and gets the answer, as in a mailing list.
        message = intervention.message_id
        self.assertIn(self.writer_user.partner_id, message.notified_partner_ids)
        self.assertEqual(message.email_layout_xmlid, 'ems.mail_layout_minutes', "relayed in the meetings layout too")

    def test_an_answer_from_an_unknown_address_is_filed_but_names_nobody_as_attendee(self):
        minute = self._thread()
        minute.with_user(self.writer_user).action_start_meeting()

        self._answer(minute, 'Somebody <tmth.personal@example.com>', 'TMTH from home', 2)

        self.assertEqual(len(minute.intervention_ids), 1)
        self.assertFalse(minute.intervention_ids.employee_id)
        self.assertFalse(minute.attendee_ids)

    def test_a_message_written_in_the_history_is_an_intervention_too(self):
        minute = self._thread()
        minute.with_user(self.writer_user).action_start_meeting()

        minute.with_user(self.writer_user).message_post(
            body='TMTH written in EMS', message_type='comment', subtype_xmlid='mail.mt_comment')
        minute.with_user(self.writer_user).message_post(body='TMTH a note', message_type='comment', subtype_xmlid='mail.mt_note')

        self.assertEqual(len(minute.intervention_ids), 1, "a note is not said to the participants")
        self.assertEqual(minute.attendee_ids, self.writer_public)

    def test_answers_to_the_draft_are_amendments_that_hold_the_approval(self):
        minute = self._thread()
        minute.with_user(self.writer_user).action_start_meeting()
        self._answer(minute, 'TMTH Other <tmth.other@example.com>', 'TMTH I agree', 3)
        minute.with_user(self.writer_user).action_submit()
        minute.with_user(self.writer_user).action_send_draft()
        self.assertIn('/report/pdf/ems.report_minute/', self._last_post(minute).body)

        self._answer(minute, 'TMTH Other <tmth.other@example.com>', 'TMTH please correct my name', 4)

        self.assertEqual(len(minute.intervention_ids), 1)
        self.assertEqual(len(minute.amendment_ids), 1)
        with self.assertRaises(UserError):
            minute.with_user(self.writer_user).action_approve()

        # Going back to the meeting is how the amendments get applied.
        minute.with_user(self.writer_user).action_back_to_meeting()
        self.assertTrue(minute.amendment_ids.addressed)
        minute.with_user(self.writer_user).action_submit()
        minute.with_user(self.writer_user).action_approve()
        self.assertEqual(minute.state, 'approved')

    def test_a_draft_with_no_amendments_is_approved_straight_away(self):
        minute = self._thread()
        minute.with_user(self.writer_user).action_start_meeting()
        minute.with_user(self.writer_user).action_submit()
        minute.with_user(self.writer_user).action_approve()
        self.assertEqual(minute.state, 'approved')

    def test_the_pdf_prints_the_interventions(self):
        minute = self._thread()
        minute.with_user(self.writer_user).action_start_meeting()
        self._answer(minute, 'TMTH Other <tmth.other@example.com>', 'TMTH printed intervention', 5)

        html = self.env['ir.actions.report']._render_qweb_html('ems.report_minute', minute.ids)[0].decode()

        self.assertIn('Interventions', html)
        self.assertIn('TMTH printed intervention', html)
        self.assertNotIn('the whole opening email', html)
