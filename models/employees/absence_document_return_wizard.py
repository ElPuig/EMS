# -*- coding: utf-8 -*-

from odoo import fields, models


class EmsAbsenceDocumentReturnWizard(models.TransientModel):
    _name = 'ems.absence.document_return_wizard'
    _description = "The Head or Direction sends an absence back to the employee: its supporting document, or its ATRI request."

    leave_id = fields.Many2one(string="Absence", comodel_name='hr.leave', required=True,
                               ondelete='cascade')
    employee_id = fields.Many2one(string="Employee", related='leave_id.employee_id')
    kind = fields.Selection(
        string="What is sent back", selection=[('document', "Supporting document"), ('atri', "ATRI request")],
        default='document', required=True,
        help="The supporting document that is not sufficient, or an absence that does not "
             "appear in ATRI (Direction only).")
    reason = fields.Text(string="Reason", required=True,
                         help="What is wrong and what the employee has to do instead. The "
                              "employee is told, and it stays on the request until they do it.")

    def action_return(self):
        self.ensure_one()
        if self.kind == 'atri':
            self.leave_id._ems_return_atri(self.reason)
        else:
            self.leave_id._ems_return_document(self.reason)
        return {'type': 'ir.actions.act_window_close'}
