# -*- coding: utf-8 -*-

from odoo import fields, models


class EmsConvalidationReturnWizard(models.TransientModel):
    _name = 'ems.convalidation.return_wizard'
    _description = "The Director sends a convalidation proposal back to the Head of Studies."

    convalidation_id = fields.Many2one(string="Request", comodel_name='ems.convalidation', required=True,
                                       ondelete='cascade')
    student_id = fields.Many2one(string="Student", related='convalidation_id.student_id')
    reason = fields.Text(string="Reason", required=True,
                         help="What the Head of Studies has to review. Shown on the request until the "
                              "next proposal; the student is not told.")

    def action_return(self):
        self.ensure_one()
        self.convalidation_id._ems_return(self.reason)
        return {'type': 'ir.actions.act_window_close'}
