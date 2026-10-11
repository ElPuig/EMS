from odoo.tests.common import TransactionCase, tagged

from .common import create_role_user, mock_outgoing_email


@tagged('post_install', '-at_install')
class TestMailReplyTo(TransactionCase):
    """Who gets the answer to a message EMS sends on someone's behalf (issue #607): a direct
    notice (message_notify) is answered to the person who caused it, never to the EMS mailbox."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        cls.sender = create_role_user(cls, 'teacher', 'test_sender_tmrt', name='TMRT Sender',
                                      email='sender.tmrt@example.com')
        cls.recipient = cls.env['res.partner'].create({'name': 'TMRT Recipient', 'email': 'recipient.tmrt@example.com'})
        cls.record = cls.env['res.partner'].create({'name': 'TMRT Record'})
        cls.catchall = cls.env.company.catchall_email

    def _notify(self, record, **kwargs):
        return record.message_notify(partner_ids=self.recipient.ids, subject='TMRT', body='TMRT', **kwargs)

    def test_a_notice_is_answered_to_whoever_caused_it(self):
        message = self._notify(self.record.with_user(self.sender))

        self.assertIn('sender.tmrt@example.com', message.reply_to)
        self.assertIn('TMRT Sender', message.reply_to)

    def test_a_notice_sent_in_sudo_is_still_answered_to_the_acting_user(self):
        message = self._notify(self.record.with_user(self.sender).sudo())

        self.assertIn('sender.tmrt@example.com', message.reply_to)

    def test_an_automatic_notice_keeps_the_ems_mailbox(self):
        """A scheduled action runs as OdooBot: nobody to answer to but the EMS mailbox."""
        self.assertTrue(self.catchall, "The test database has no catchall address to fall back to.")

        message = self._notify(self.record.with_user(self.env.ref('base.user_root')))

        self.assertIn(self.catchall, message.reply_to)

    def test_an_explicit_reply_to_is_respected(self):
        message = self._notify(self.record.with_user(self.sender), reply_to='other.tmrt@example.com')

        self.assertEqual(message.reply_to, 'other.tmrt@example.com')

    def test_a_chatter_message_is_not_affected(self):
        """A message written on a record's thread keeps Odoo's own reply address: only direct
        notices are changed."""
        self.assertTrue(self.catchall, "The test database has no catchall address to fall back to.")

        message = self.record.with_user(self.sender).message_post(body='TMRT', partner_ids=self.recipient.ids)

        self.assertIn(self.catchall, message.reply_to)
