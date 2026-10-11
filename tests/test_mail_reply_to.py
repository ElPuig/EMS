from odoo.tests.common import TransactionCase, tagged

from .common import create_role_user, ensure_catchall_address, mock_outgoing_email


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
        cls.catchall = ensure_catchall_address(cls)

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
        message = self._notify(self.record.with_user(self.env.ref('base.user_root')))

        self.assertIn(self.catchall, message.reply_to)

    def test_an_explicit_reply_to_is_respected(self):
        message = self._notify(self.record.with_user(self.sender), reply_to='other.tmrt@example.com')

        self.assertEqual(message.reply_to, 'other.tmrt@example.com')

    def test_a_chatter_message_is_not_affected(self):
        """A message written on a record's thread keeps Odoo's own reply address: only direct
        notices are changed."""
        message = self.record.with_user(self.sender).sudo().message_post(body='TMRT', partner_ids=self.recipient.ids)

        self.assertIn(self.catchall, message.reply_to)

    # Emails sent with a template on someone's request

    REQUESTED_TEMPLATES = (
        'ems.email_template_convalidation_resolved',
        'ems.email_template_convalidation_info_request',
        'ems.email_template_authorization_send',
        'ems.email_template_contact_data_request',
    )

    def _template_reply_to(self, user):
        template = self.env.ref('ems.email_template_authorization_send').with_user(user).sudo()
        return template._render_field('reply_to', self.record.ids)[self.record.id]

    def test_requested_templates_share_the_reply_rule(self):
        for xmlid in self.REQUESTED_TEMPLATES:
            self.assertEqual(self.env.ref(xmlid).reply_to, '{{ user.partner_id._ems_reply_to() }}', xmlid)

    def test_a_requested_email_is_answered_to_whoever_sent_it(self):
        self.assertIn('sender.tmrt@example.com', self._template_reply_to(self.sender))

    def test_a_reminder_nobody_sent_keeps_the_company_address(self):
        """Empty: the email is then answered to its sender address, the company's own."""
        self.assertFalse(self._template_reply_to(self.env.ref('base.user_root')))

    def test_a_family_is_never_the_reply_address(self):
        portal = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'TMRT Portal', 'login': 'test_portal_tmrt', 'email': 'portal.tmrt@example.com',
            'groups_id': [(6, 0, self.env.ref('base.group_portal').ids)]})

        self.assertEqual(portal.partner_id._ems_reply_to(), '')
