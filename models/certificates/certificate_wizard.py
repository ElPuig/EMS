# -*- coding: utf-8 -*-

from odoo import fields, models


class EmsCertificateWizard(models.TransientModel):
    """The text some steps of a certificate request need: what documentation is asked for, why it
    is returned, rejected or cancelled. One dialog for the four, since each only asks for a text."""
    _name = 'ems.certificate.wizard'
    _description = "Ask for the text of a certificate request's action."

    certificate_id = fields.Many2one(string="Request", comodel_name='ems.certificate', required=True,
                                     ondelete='cascade')
    mode = fields.Selection(string="Action", required=True, selection=[
        ('info', 'Request documentation'),
        ('return', 'Return to the previous step'),
        ('reject', 'Reject'),
        ('cancel', 'Cancel'),
    ])
    message = fields.Text(string="Text", required=True,
                          help="Requesting documentation or rejecting, it is emailed to the applicant. Returning or "
                               "cancelling, it stays on the request for the staff.")

    def action_confirm(self):
        self.ensure_one()
        certificate = self.certificate_id
        handlers = {
            'info': certificate._ems_request_documentation,
            'return': certificate._ems_return,
            'reject': certificate._ems_reject,
            'cancel': certificate._ems_cancel,
        }
        handlers[self.mode](self.message)
        return {'type': 'ir.actions.act_window_close'}
