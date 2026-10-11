# -*- coding: utf-8 -*-

from odoo import models


class MailThread(models.AbstractModel):
    _inherit = 'mail.thread'

    def message_notify(self, **kwargs):
        """A direct notice ("you have been sent to cover this class") is answered to the person
        who caused it (issue #607). Odoo's own reply address is the company's catchall mailbox,
        meant for answers that are filed on the record's thread: a notice is not part of any
        thread, so there the answer reached nobody. A notice nobody caused (a scheduled action,
        running as OdooBot) keeps that mailbox."""
        if 'reply_to' not in kwargs:
            author_id, email_from = self._message_compute_author(
                kwargs.get('author_id'), kwargs.get('email_from'), raise_on_email=False)
            author = self.env['res.partner'].browse(author_id)
            if email_from and author != self.env.ref('base.partner_root') and author.sudo().user_ids.filtered(
                    lambda user: not user.share):
                kwargs['reply_to'] = email_from
        return super().message_notify(**kwargs)
