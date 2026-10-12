# -*- coding: utf-8 -*-

from odoo import fields, models


class EmsConvalidationRejectWizard(models.TransientModel):
    _name = 'ems.convalidation.reject_wizard'
    _description = "The Head of Studies refuses to convalidate a subject of a request, stating why."

    line_id = fields.Many2one(string="Subject", comodel_name='ems.convalidation.line', required=True,
                              ondelete='cascade')
    reason_id = fields.Many2one(string="Reason", comodel_name='ems.convalidation.rejection_reason', required=True,
                                default=lambda self: self._default_reason_id())
    details = fields.Text(string="Details",
                          help="Stated on the resolution after the reason.")

    def _default_reason_id(self):
        """First active reason by its own order: the most usual one, like the documentation
        request reasons."""
        return self.env['ems.convalidation.rejection_reason'].search([], limit=1)

    def action_reject(self):
        self.ensure_one()
        self.line_id.write({
            'state': 'rejected',
            'rejection_reason_id': self.reason_id.id,
            'rejection_reason': self.details,
        })
        return {'type': 'ir.actions.act_window_close'}
