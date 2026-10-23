# -*- coding: utf-8 -*-

from odoo import _, fields, models
from odoo.exceptions import UserError


class EmsErasmusClaim(models.Model):
    """Issue #685 - a claim against the provisional resolution or an appeal before the Director
    (art. 14 of the call). They arrive by email; the Erasmus team records them and the answer."""
    _name = 'ems.erasmus.claim'
    _description = 'Erasmus+ claim'
    _inherit = ['ems.base']
    _order = 'received_date desc, id desc'

    application_id = fields.Many2one(string="Application", comodel_name='ems.erasmus.application', required=True,
                                     ondelete='restrict', index=True)
    call_id = fields.Many2one(string="Call", related='application_id.call_id', store=True)
    partner_id = fields.Many2one(string="Applicant", related='application_id.partner_id', store=True)
    resolution_id = fields.Many2one(string="Against", comodel_name='ems.erasmus.resolution', ondelete='restrict',
                                    domain="[('call_id', '=', call_id), ('state', '=', 'published')]")
    kind = fields.Selection(string="Kind", required=True, default='claim', tracking=True, selection=[
        ('claim', "Claim"), ('appeal', "Appeal before the Director")])
    received_date = fields.Date(string="Received on", required=True, tracking=True,
                                default=lambda self: self.env['ems.datetime_utils'].get_local_today())
    description = fields.Text(string="What is claimed", required=True)
    attachment_ids = fields.Many2many(string="Files", comodel_name='ir.attachment',
                                      relation='ems_erasmus_claim_attachment_rel')
    response = fields.Text(string="Response", tracking=True)
    resolved_date = fields.Date(string="Resolved on", readonly=True, copy=False)
    state = fields.Selection(string="State", required=True, default='open', readonly=True, tracking=True,
                             selection=[('open', "Open"), ('resolved', "Resolved")])

    def _compute_display_name(self):
        kinds = dict(self._fields['kind']._description_selection(self.env))
        for claim in self:
            claim.display_name = f"{kinds.get(claim.kind, '')} - {claim.partner_id.name}"

    def action_resolve(self):
        if self.filtered(lambda claim: not (claim.response or '').strip()):
            raise UserError(_("Write the response first."))
        self.write({'state': 'resolved', 'resolved_date': self.env['ems.datetime_utils'].get_local_today()})

    def action_reopen(self):
        self.write({'state': 'open', 'resolved_date': False})
