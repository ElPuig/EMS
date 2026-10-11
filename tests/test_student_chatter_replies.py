from unittest.mock import patch

from odoo.tests.common import TransactionCase, tagged
from odoo.tools import config

from .common import create_role_user, mock_outgoing_email

REPLY = """From: {sender}
To: {to}
Subject: Re: TSCR
Message-Id: <tscr-reply-{number}@example.com>
In-Reply-To: {parent}
References: {parent}
MIME-Version: 1.0
Content-Type: text/plain; charset="utf-8"

TSCR answer from the family
"""


@tagged('post_install', '-at_install')
class TestStudentChatterReplies(TransactionCase):
    """A conversation on a contact's chatter stays between whoever writes and the contact
    (issue #586): nobody follows a contact for having created it, and an answer sent by email
    is filed on that chatter and reaches whoever wrote."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # As the real transport does, hand back the email's own Message-Id: Odoo stores what
        # send_email() returns as the message's id, which is what an answer refers to.
        mock_outgoing_email(cls).side_effect = lambda message, *args, **kwargs: message['Message-Id']
        cls.secretary = create_role_user(cls, 'secretary', 'test_secretary_tscr', email='secretary.tscr@example.com')
        cls.teacher = create_role_user(cls, 'teacher', 'test_teacher_tscr', name='TSCR Teacher',
                                       email='teacher.tscr@example.com')
        cls.family = cls.env['res.partner'].create({
            'name': 'TSCR Family', 'contact_type': 'family', 'email': 'family.tscr@example.com'})
        cls.contact = cls.env['res.partner'].create({'name': 'TSCR Contact', 'contact_type': 'family'})
        cls.admin_partner = cls.env.ref('base.user_admin').partner_id
        # Answers need an address of their own: Odoo discards as a bounce whatever arrives at
        # the bounce address, so a catchall equal to it (both 'ems') files no answer at all.
        cls.env.company.alias_domain_id.write({'bounce_alias': 'bounce.tscr', 'catchall_alias': 'answers.tscr'})

    def test_creating_a_contact_does_not_make_you_follow_it(self):
        contact = self.env['res.partner'].with_user(self.secretary).create({
            'name': 'TSCR Created', 'contact_type': 'family'})

        self.assertNotIn(self.secretary.partner_id, contact.sudo().message_partner_ids)
        self.assertNotIn('mail_create_nosubscribe', contact.env.context)

    def test_writing_on_a_contact_makes_you_follow_it(self):
        self.contact.with_user(self.teacher).sudo().message_post(
            body='TSCR', partner_ids=self.family.ids, message_type='comment', subtype_xmlid='mail.mt_comment')

        self.contact.invalidate_recordset(['message_partner_ids'])
        self.assertIn(self.teacher.partner_id, self.contact.message_partner_ids)

    def _created_by_secretary(self, name):
        """A contact the secretary created and follows, as before issue #586."""
        contact = self.env['res.partner'].with_user(self.secretary).create({'name': name, 'contact_type': 'family'}).sudo()
        contact.message_subscribe(partner_ids=self.secretary.partner_id.ids)
        return contact

    def test_whoever_only_created_a_contact_stops_following_it(self):
        contact = self._created_by_secretary('TSCR Only Created')
        contact.message_subscribe(partner_ids=self.teacher.partner_id.ids)

        self.env['res.partner']._ems_unfollow_contact_creators()

        contact.invalidate_recordset(['message_partner_ids'])
        self.assertNotIn(self.secretary.partner_id, contact.message_partner_ids)
        # Someone who follows a contact they did not create chose to.
        self.assertIn(self.teacher.partner_id, contact.message_partner_ids)

    def test_a_creator_who_wrote_on_the_contact_keeps_following_it(self):
        contact = self._created_by_secretary('TSCR Created And Wrote')
        contact.with_user(self.secretary).message_post(
            body='TSCR', message_type='comment', subtype_xmlid='mail.mt_comment')

        self.env['res.partner']._ems_unfollow_contact_creators()

        contact.invalidate_recordset(['message_partner_ids'])
        self.assertIn(self.secretary.partner_id, contact.message_partner_ids)

    def test_the_administrator_stops_following_every_contact(self):
        """Even one it wrote on: its mailbox is the EMS one."""
        admin = self.env.ref('base.user_admin')
        self.contact.with_user(admin).sudo().message_post(
            body='TSCR', message_type='comment', subtype_xmlid='mail.mt_comment')
        self.contact.message_subscribe(partner_ids=self.admin_partner.ids)

        self.env['res.partner']._ems_unfollow_contact_creators()

        self.contact.invalidate_recordset(['message_partner_ids'])
        self.assertNotIn(self.admin_partner, self.contact.message_partner_ids)

    def test_an_emailed_answer_is_filed_on_the_chatter_and_reaches_whoever_wrote(self):
        catchall = self.env.company.catchall_email
        self.assertTrue(catchall, "The test database has no catchall address for answers to arrive at.")
        sent = self.contact.with_user(self.teacher).sudo().message_post(
            body='TSCR', subject='TSCR', partner_ids=self.family.ids,
            message_type='comment', subtype_xmlid='mail.mt_comment')
        self.assertIn(catchall, sent.reply_to)

        self.env['mail.thread'].message_process(False, REPLY.format(
            sender='TSCR Family <family.tscr@example.com>', to=catchall, parent=sent.message_id, number=1))

        answer = self.env['mail.message'].search([
            ('model', '=', 'res.partner'), ('res_id', '=', self.contact.id), ('message_type', '=', 'email')])
        self.assertEqual(len(answer), 1)
        self.assertEqual(answer.author_id, self.family)
        self.assertIn('TSCR answer from the family', answer.body)
        self.assertIn(self.teacher.partner_id, answer.notified_partner_ids)

    def test_a_development_machine_reads_no_mailbox(self):
        server = self.env['fetchmail.server'].create({
            'name': 'TSCR Mailbox', 'server_type': 'imap', 'server': 'imap.example.com', 'port': 993,
            'user': 'tscr', 'password': 'tscr'})
        with patch.dict(config.options, {'ems_server_role': 'dev'}), \
                patch.object(type(server), 'connect') as connect:
            server.fetch_mail()

        connect.assert_not_called()
