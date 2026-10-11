from unittest.mock import MagicMock, patch

from odoo.addons.base.models.ir_mail_server import MailDeliveryException
from odoo.tests.common import TransactionCase, tagged
from odoo.tools import config

REDIRECT = 'dev.account@example.com'


@tagged('post_install', '-at_install')
class TestDevMailGuard(TransactionCase):
    """A development machine never sends real email (issue #590, models/settings/mail_guard.py):
    on 2026-10-06 a production copy restored on one sent 412 real notifications."""

    def setUp(self):
        super().setUp()
        self.params = self.env['ir.config_parameter'].sudo()
        self.params.set_param('ems.environment_type', 'dev')
        self.params.set_param('ems.dev_mail_redirect', REDIRECT)
        self.params.set_param('ems.dev_mail_allowlist', 'ems@example.com, Other.Allowed@example.com')
        self.mail_server = self.env['ir.mail_server']

    def _server_role(self, role):
        patcher = patch.dict(config.options, {'ems_server_role': role})
        patcher.start()
        self.addCleanup(patcher.stop)

    def _prepare(self, email_to, email_cc=None, email_bcc=None):
        message = self.mail_server.build_email(
            'sender@example.com', email_to, 'Subject', 'Body', email_cc=email_cc, email_bcc=email_bcc)
        return self.mail_server._prepare_email_message(message, None)[1]

    def test_production_machine_is_untouched(self):
        """No role in odoo.conf (production, CI): whatever the database says, nothing changes."""
        self._server_role(False)
        self.params.set_param('ems.environment_type', 'production')
        self.assertEqual(self._prepare(['family@gmail.example']), ['family@gmail.example'])

    def test_database_not_prepared_by_devel_sh_sends_nothing(self):
        """A restored production copy declares itself 'production' (deploy.sh): even the
        developer's own redirected address is refused, devel.sh never ran on it."""
        self._server_role('dev')
        for environment_type in ('production', False):
            self.params.set_param('ems.environment_type', environment_type)
            with self.assertRaises(MailDeliveryException):
                self._prepare(["dev.account+family_at_gmail.com@example.com"])

    def test_redirected_and_allowlisted_recipients_pass(self):
        self._server_role('dev')
        recipients = [
            'dev.account+family_at_gmail.com@example.com',
            'Dev.Account@Example.com',
            'ems@example.com',
            'other.allowed@example.com',
        ]
        self.assertEqual(sorted(self._prepare(recipients)), sorted(recipients))

    def test_real_recipient_is_blocked_in_to_cc_and_bcc(self):
        self._server_role('dev')
        redirected = 'dev.account+a_at_b.com@example.com'
        for kwargs in (
            {'email_to': ['family@gmail.example']},
            {'email_to': [redirected], 'email_cc': ['family@gmail.example']},
            {'email_to': [redirected], 'email_bcc': ['family@gmail.example']},
        ):
            with self.subTest(**kwargs), self.assertRaises(MailDeliveryException):
                self._prepare(**kwargs)

    def test_lookalike_addresses_are_blocked(self):
        """Same account on another domain, or an account that only starts like it."""
        self._server_role('dev')
        for recipient in ('dev.account+x@other.example', 'dev.accountx@example.com', 'dev.account.x+y@example.com'):
            with self.subTest(recipient=recipient), self.assertRaises(MailDeliveryException):
                self._prepare([recipient])

    def test_without_redirect_only_the_allowlist_passes(self):
        self._server_role('dev')
        self.params.set_param('ems.dev_mail_redirect', False)
        self.assertEqual(self._prepare(['ems@example.com']), ['ems@example.com'])
        with self.assertRaises(MailDeliveryException):
            self._prepare(['dev.account+a_at_b.com@example.com'])

    def test_queued_email_never_reaches_smtp(self):
        """End to end, as the attendance notification job sent them: the mail is marked as
        failed and the SMTP session never sends anything."""
        self._server_role('dev')
        self.params.set_param('ems.environment_type', 'production')
        smtp = MagicMock(from_filter=False, smtp_from=False)
        mail = self.env['mail.mail'].create({
            'subject': 'Attendance', 'body_html': '<p>Absence</p>',
            'email_from': 'sender@example.com', 'email_to': 'family@gmail.example',
        })
        with patch.object(type(self.mail_server), 'connect', return_value=smtp):
            mail.send()
        self.assertEqual(mail.state, 'exception')
        smtp.send_message.assert_not_called()
        smtp.sendmail.assert_not_called()
