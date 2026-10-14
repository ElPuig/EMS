# -*- coding: utf-8 -*-

from odoo import fields, models


class EmsAbsenceDocumentReturnWizard(models.TransientModel):
    _name = 'ems.absence.document_return_wizard'
    _description = "The Head or Direction sends an absence back to the employee: its supporting document, its ATRI request, or its documentation in ATRI."

    leave_id = fields.Many2one(string="Absence", comodel_name='hr.leave', required=True,
                               ondelete='cascade')
    employee_id = fields.Many2one(string="Employee", related='leave_id.employee_id')
    kind = fields.Selection(
        string="What is sent back", selection=[
            ('document', "Supporting document"), ('atri', "ATRI request"),
            ('atri_document', "Documentation in ATRI")],
        default='document', required=True,
        help="The supporting document that is not sufficient, an absence that does not appear "
             "in ATRI, or one whose documentation in ATRI is not sufficient (both Direction only).")
    reason = fields.Text(string="Reason", required=True,
                         help="What is wrong and what the employee has to do instead. The "
                              "employee is told, and it stays on the request until they do it.")

    def action_return(self):
        self.ensure_one()
        if self.kind in ('atri', 'atri_document'):
            self.leave_id._ems_return_atri(self.reason, documentation=self.kind == 'atri_document')
        else:
            self.leave_id._ems_return_document(self.reason)
        return {'type': 'ir.actions.act_window_close'}
