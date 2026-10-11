# -*- coding: utf-8 -*-

from odoo import models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def _ems_reply_to(self):
        """The address an answer to an email this partner caused should go to: their own, as
        long as they are a person working at the centre (an internal user other than OdooBot,
        which is who scheduled actions run as). Empty otherwise, which leaves the email with
        the reply address it would have had anyway. Used by message_notify() below and by the
        email templates sent on someone's request (`{{ user.partner_id._ems_reply_to() }}`)."""
        self.ensure_one()
        if self == self.env.ref('base.partner_root') or not self.sudo().user_ids.filtered(lambda user: not user.share):
            return ''
        return self.email_formatted or ''


class MailThread(models.AbstractModel):
    _inherit = 'mail.thread'

    def message_notify(self, **kwargs):
        """A direct notice ("you have been sent to cover this class") is answered to the person
        who caused it (issue #607). Odoo's own reply address is the company's catchall mailbox,
        meant for answers that are filed on the record's thread: a notice is not part of any
        thread, so there the answer reached nobody. A notice nobody caused (a scheduled action,
        running as OdooBot) keeps that mailbox."""
        if 'reply_to' not in kwargs:
            author_id = self._message_compute_author(
                kwargs.get('author_id'), kwargs.get('email_from'), raise_on_email=False)[0]
            reply_to = self.env['res.partner'].browse(author_id)._ems_reply_to() if author_id else ''
            if reply_to:
                kwargs['reply_to'] = reply_to
        return super().message_notify(**kwargs)
