# -*- coding: utf-8 -*-

import logging

from odoo import _, models
from odoo.addons.base.models.ir_mail_server import MailDeliveryException
from odoo.tools import config

# odoo.conf of a development machine (set by devel.sh): 'ems_server_role = dev'.
DEV_SERVER_ROLE = 'dev'
# What every email leaving a development machine carries at the start of its subject.
DEV_SUBJECT_MARK = '[DEV]'

_logger = logging.getLogger(__name__)


class IrMailServer(models.Model):
    """A development machine never sends real email (issue #590): only to the developer's own
    inbox (the addresses devel.sh redirected) and to an explicit allowlist, and nothing at all
    from a database that didn't go through devel.sh, such as a restored production copy.
    See docs/en/developers/shared/dev_mail_guard.md."""
    _inherit = 'ir.mail_server'

    def _prepare_email_message(self, message, smtp_session):
        # Every real SMTP send goes through here; tests that mock send_email() never do.
        smtp_from, smtp_to_list, message = super()._prepare_email_message(message, smtp_session)
        dev_machine = config.get('ems_server_role') == DEV_SERVER_ROLE
        if dev_machine:
            self._ems_check_dev_recipients(smtp_to_list)
        # The database alone is enough to mark the subject (issue #691): a box prepared by a
        # devel.sh older than #590 has no machine role, but its emails come from development too.
        if dev_machine or self._ems_is_dev_database():
            self._ems_mark_dev_subject(message)
        return smtp_from, smtp_to_list, message

    def _ems_is_dev_database(self):
        """devel.sh ran on this database ('ems.environment_type', see CLAUDE.md)."""
        return self.env['ir.config_parameter'].sudo().get_param('ems.environment_type') == 'dev'

    def _ems_mark_dev_subject(self, message):
        """Whoever receives it - the developer's redirect inbox, or a shared allowlisted one
        such as the staff account, which gets production's emails too - has to tell at a glance
        that it comes from a development machine and not from production."""
        subject = message['Subject'] or ''
        if subject.startswith(DEV_SUBJECT_MARK):
            return
        del message['Subject']
        message['Subject'] = f"{DEV_SUBJECT_MARK} {subject}".strip()

    def _ems_check_dev_recipients(self, recipients):
        if not self._ems_is_dev_database():
            raise MailDeliveryException(_(
                "Email blocked: this is a development machine and this database has not been "
                "prepared with devel.sh, so its addresses may be real people's."))
        params = self.env['ir.config_parameter'].sudo()
        redirect = (params.get_param('ems.dev_mail_redirect') or '').strip().lower()
        allowlist = {address.strip().lower() for address in (params.get_param('ems.dev_mail_allowlist') or '').split(',')}
        blocked = [recipient for recipient in recipients if not self._ems_dev_recipient_allowed(recipient, redirect, allowlist)]
        if blocked:
            raise MailDeliveryException(_(
                "Email blocked: this is a development machine and these recipients are neither "
                "redirected by devel.sh nor in the allowlist: %(recipients)s",
                recipients=", ".join(blocked)))

    def _ems_dev_recipient_allowed(self, recipient, redirect, allowlist):
        """The redirect account itself, any of its '+' aliases devel.sh created, or the allowlist."""
        recipient = recipient.strip().lower()
        if recipient in allowlist:
            return True
        if '@' not in redirect or '@' not in recipient:
            return False
        account, domain = redirect.split('@', 1)
        local, recipient_domain = recipient.rsplit('@', 1)
        return recipient_domain == domain and (local == account or local.startswith(f"{account}+"))


class MailMail(models.Model):
    """On a development machine OdooBot's emails (daily summaries, automatic notices) are not
    sent unless 'ems.dev_mail_odoobot' is 'True' (issue #752): a restored production database
    generates them for every staff member, and devel.sh redirects all of them to the developer."""
    _inherit = 'mail.mail'

    def send(self, auto_commit=False, raise_exception=False, post_send_callback=None):
        odoobot_mails = self._ems_dev_odoobot_mails()
        if odoobot_mails:
            odoobot_mails.write({
                'state': 'cancel',
                'failure_reason': _(
                    "Not sent: OdooBot's emails are off on this development machine. Set the "
                    "system parameter ems.dev_mail_odoobot to True to receive them."),
            })
            self.env['mail.notification'].sudo().search([
                ('mail_mail_id', 'in', odoobot_mails.ids),
                ('notification_status', 'not in', ('sent', 'canceled')),
            ]).write({'notification_status': 'canceled'})
            _logger.info("Development machine: %s OdooBot email(s) not sent.", len(odoobot_mails))
        return super(MailMail, self - odoobot_mails).send(
            auto_commit=auto_commit, raise_exception=raise_exception, post_send_callback=post_send_callback)

    def _ems_dev_odoobot_mails(self):
        # A database devel.sh never ran on is refused by IrMailServer, with its own reason.
        if config.get('ems_server_role') != DEV_SERVER_ROLE or not self.env['ir.mail_server']._ems_is_dev_database():
            return self.browse()
        if self.env['ir.config_parameter'].sudo().get_param('ems.dev_mail_odoobot') == 'True':
            return self.browse()
        odoobot = self.env.ref('base.partner_root')
        return self.filtered(lambda mail: mail.state == 'outgoing' and mail.author_id == odoobot)


class FetchmailServer(models.Model):
    """A development machine never reads a mailbox either (issue #586): a database restored from
    production carries production's incoming mail server, and reading it here would take the
    families' answers away from production (an email is only fetched once) and file them on a
    copy nobody looks at."""
    _inherit = 'fetchmail.server'

    def fetch_mail(self, raise_exception=True):
        if config.get('ems_server_role') == DEV_SERVER_ROLE:
            _logger.info("Development machine: incoming mail server(s) %s not read.", self.mapped('name'))
            return True
        return super().fetch_mail(raise_exception=raise_exception)
