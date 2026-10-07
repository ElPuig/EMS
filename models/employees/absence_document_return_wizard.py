# -*- coding: utf-8 -*-

from odoo import fields, models


class EmsAbsenceDocumentReturnWizard(models.TransientModel):
    _name = 'ems.absence.document_return_wizard'
    _description = "The Head or Direction sends an absence's supporting document back to the employee."

    leave_id = fields.Many2one(string="Absence", comodel_name='hr.leave', required=True,
                               ondelete='cascade')
    employee_id = fields.Many2one(string="Employee", related='leave_id.employee_id')
    reason = fields.Text(string="Reason", required=True,
                         help="What is wrong with the document and what the employee has to "
                              "attach instead. The employee is told, and it stays on the request "
                              "until they attach a new one.")

    def action_return(self):
        self.ensure_one()
        self.leave_id._ems_return_document(self.reason)
        return {'type': 'ir.actions.act_window_close'}
