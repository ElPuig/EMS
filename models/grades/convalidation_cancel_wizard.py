# -*- coding: utf-8 -*-

from odoo import _, fields, models
from odoo.exceptions import UserError


class EmsConvalidationCancelWizard(models.TransientModel):
    _name = 'ems.convalidation.cancel_wizard'
    _description = "The staff cancel a convalidation request, saying why."

    convalidation_id = fields.Many2one(string="Request", comodel_name='ems.convalidation', required=True,
                                       ondelete='cascade')
    student_id = fields.Many2one(string="Student", related='convalidation_id.student_id')
    reason = fields.Text(string="Reason", required=True,
                         help="Why the request is cancelled. The student sees it on the portal and "
                              "in their communications.")

    def action_cancel(self):
        self.ensure_one()
        reason = (self.reason or '').strip()
        if not reason:
            raise UserError(_("Write the reason for cancelling the request."))
        self.convalidation_id._ems_cancel(reason)
        return {'type': 'ir.actions.act_window_close'}
