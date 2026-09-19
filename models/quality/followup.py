# -*- coding: utf-8 -*-

from odoo import api, fields, models

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

    @api.depends('date', 'state')
    def _compute_display_name(self):
        state_labels = dict(self._fields['state']._description_selection(self.env))
        for followup in self:
            followup.display_name = f"{followup.date} {state_labels.get(followup.state, '')}".strip()
