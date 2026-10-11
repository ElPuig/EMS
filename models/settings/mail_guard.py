# -*- coding: utf-8 -*-

from odoo import _, models
from odoo.addons.base.models.ir_mail_server import MailDeliveryException
from odoo.tools import config

# odoo.conf of a development machine (set by devel.sh): 'ems_server_role = dev'.
DEV_SERVER_ROLE = 'dev'


class IrMailServer(models.Model):
    """A development machine never sends real email (issue #590): only to the developer's own
    inbox (the addresses devel.sh redirected) and to an explicit allowlist, and nothing at all
    from a database that didn't go through devel.sh, such as a restored production copy.
    See docs/en/developers/shared/dev_mail_guard.md."""
    _inherit = 'ir.mail_server'

    def _prepare_email_message(self, message, smtp_session):
        # Every real SMTP send goes through here; tests that mock send_email() never do.
        smtp_from, smtp_to_list, message = super()._prepare_email_message(message, smtp_session)
        if config.get('ems_server_role') == DEV_SERVER_ROLE:
            self._ems_check_dev_recipients(smtp_to_list)
        return smtp_from, smtp_to_list, message

    def _ems_check_dev_recipients(self, recipients):
        params = self.env['ir.config_parameter'].sudo()
        if params.get_param('ems.environment_type') != 'dev':
            raise MailDeliveryException(_(
                "Email blocked: this is a development machine and this database has not been "
                "prepared with devel.sh, so its addresses may be real people's."))
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
