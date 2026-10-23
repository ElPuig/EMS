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

    def _ems_notify(self, partners, message):
        """A note addressed to these partners only: unlike a comment, it is not sent to every
        follower of the record - whoever else follows it does not need each reminder. Used by
        the absence requests (hr.leave) and the detected absences (ems.absence_pending)."""
        self.ensure_one()
        if partners:
            self.message_post(body=message, partner_ids=partners.ids, subtype_xmlid='mail.mt_note')

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
