# -*- coding: utf-8 -*-

from odoo import SUPERUSER_ID, api, fields, models


class EmsInfoNotice(models.Model):
    """A notice for a member of staff that asks for no action and isn't urgent: it waits here
    for their daily summary (res.users._ems_send_daily_summary) instead of being sent on the
    spot. Only the system reads or writes it (sudo). See docs/en/developers/shared/daily_summary.md."""
    _name = 'ems.info_notice'
    _description = "Informative notice waiting for its recipient's daily summary"
    _order = 'id'

    user_id = fields.Many2one(string="Recipient", comodel_name='res.users', required=True, index=True, ondelete='cascade')
    res_model = fields.Char(string="Related model", required=True)
    res_id = fields.Many2oneReference(string="Related record", model_field='res_model', required=True)
    body = fields.Html(string="Notice text", sanitize=True)
    sent_date = fields.Datetime(string="Sent on", readonly=True, index=True)

    @api.model
    def _ems_queue(self, users, record, compose):
        """Queues a notice about `record` for each of `users`, written by `compose(user)` in that
        user's own language (call it with `record.with_context(lang=user.lang)` or `env._`). Users
        who can't receive a summary (archived, portal, OdooBot) are skipped."""
        record.ensure_one()
        recipients = users.sudo().filtered(lambda user: user.active and not user.share and user.id != SUPERUSER_ID)
        return self.sudo().create([{
            'user_id': user.id,
            'res_model': record._name,
            'res_id': record.id,
            'body': compose(user),
        } for user in recipients])
