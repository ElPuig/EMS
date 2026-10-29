# -*- coding: utf-8 -*-

from markupsafe import Markup

from odoo import _, api, fields, models

from .common import QUALITY_STATES


class EmsQualityFollowup(models.Model):
    _name = "ems.quality.followup"
    _description = "Follow-up entry: what happened, when, and which state it left the record in."
    _order = "date desc, id desc"

    action_id = fields.Many2one(string="Action", comodel_name="ems.quality.action", required=True, ondelete='cascade', index=True)
    date = fields.Date(string="Date", required=True, default=fields.Date.context_today)
    state = fields.Selection(string="State", selection=QUALITY_STATES, required=True, default='in_progress')
    description = fields.Text(string="What happened", required=True)
    author_employee_id = fields.Many2one(
        string="Written by",
        comodel_name="hr.employee.public",
        default=lambda self: self.env['hr.employee.public'].search([('user_id', '=', self.env.uid)], limit=1),
    )

    @api.model_create_multi
    def create(self, vals_list):
        followups = super().create(vals_list)
        followups._ems_notify_followers()
        return followups

    def _ems_notify_followers(self):
        """Every entry is told to the agreement's followers (its responsible people and the people
        involved), so they hear of its progress without having to look. With sudo and the writer as
        author: posting on a record is a write the people reporting progress do not have."""
        state_labels = dict(self._fields['state']._description_selection(self.env))
        for followup in self:
            followup.action_id.sudo().message_post(
                body=Markup("<p>%s</p>") % _("Follow-up (%(state)s): %(description)s",
                                             state=state_labels.get(followup.state, ''), description=followup.description),
                author_id=self.env.user.partner_id.id,
                subtype_xmlid='mail.mt_comment',
            )

    @api.depends('date', 'state')
    def _compute_display_name(self):
        state_labels = dict(self._fields['state']._description_selection(self.env))
        for followup in self:
            followup.display_name = f"{followup.date} {state_labels.get(followup.state, '')}".strip()
