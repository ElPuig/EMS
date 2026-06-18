# -*- coding: utf-8 -*-

from markupsafe import Markup
from odoo import models, _
from odoo.tools import plaintext2html


class ResUsers(models.Model):
    _inherit = 'res.users'

    def _get_activity_groups(self):
        """Relabel the sale.order group in the activities systray as
        "Enrollments" (in EMS, sale orders are enrollments) so the to-do is
        clearly tied to enrollments instead of the generic "Sales Order"."""
        groups = super()._get_activity_groups()
        for group in groups:
            if group.get('model') == 'sale.order':
                group['name'] = _('Enrollments')
        return groups


class MailActivity(models.Model):
    _inherit = 'mail.activity'

    def _action_done(self, feedback=False, attachment_ids=None):
        """When a secretary marks an enrollment-comment review task as done, let
        the student know: post a public message on the enrollment (visible in
        their portal and emailed to them, since they are a follower) with a
        standard notice plus the secretary's feedback if any."""
        comment_type = self.env.ref(
            'ems.mail_activity_enrollment_comment', raise_if_not_found=False
        )
        enrollment_ids = []
        if comment_type:
            enrollment_ids = self.filtered(
                lambda a: a.activity_type_id == comment_type
                and a.res_model == 'sale.order'
            ).mapped('res_id')

        res = super()._action_done(feedback=feedback, attachment_ids=attachment_ids)

        if enrollment_ids:
            body = Markup('<p>%s</p>') % _("Your request has been reviewed by the secretary's office.")
            if feedback:
                body += plaintext2html(feedback)
            orders = self.env['sale.order'].sudo().browse(set(enrollment_ids)).exists()
            for order in orders:
                order.message_post(
                    body=body,
                    message_type='comment',
                    subtype_xmlid='mail.mt_comment',
                )
        return res

    def unlink(self):
        """When an enrollment-comment review activity is resolved (marked done ->
        Odoo unlinks it) or discarded, close it for every other secretary too by
        removing the sibling activities on the same enrollment."""
        siblings = self.env['mail.activity']
        if not self.env.context.get('ems_activity_cascade'):
            comment_type = self.env.ref(
                'ems.mail_activity_enrollment_comment', raise_if_not_found=False
            )
            if comment_type:
                relevant = self.filtered(
                    lambda a: a.activity_type_id == comment_type
                    and a.res_model == 'sale.order'
                )
                for act in relevant:
                    siblings |= self.search([
                        ('activity_type_id', '=', comment_type.id),
                        ('res_model', '=', 'sale.order'),
                        ('res_id', '=', act.res_id),
                        ('id', 'not in', self.ids),
                    ])
        res = super().unlink()
        if siblings:
            siblings.with_context(ems_activity_cascade=True).unlink()
        return res
