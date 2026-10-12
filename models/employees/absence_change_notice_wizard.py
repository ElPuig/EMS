# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import UserError

# The decisions that can be taken through this dialog: hr.leave._ems_ask_change_message() opens
# it with one of them, and nothing else can be called through it.
DECISION_METHODS = (
    'action_approve',
    'action_refuse',
    'action_ems_document_validate',
    'action_ems_direction_done',
    'action_ems_direction_refuse',
)
REFUSAL_METHODS = ('action_refuse', 'action_ems_direction_refuse')


class EmsAbsenceChangeNoticeWizard(models.TransientModel):
    _name = 'ems.absence.change_notice_wizard'
    _description = "The Head or Direction explains a decision on an absence request to the employee."

    leave_id = fields.Many2one(string="Absence", comodel_name='hr.leave', required=True,
                               ondelete='cascade')
    employee_id = fields.Many2one(string="Employee", related='leave_id.employee_id')
    method = fields.Char(string="Decision", required=True)
    when = fields.Char(string="Dates", compute='_compute_changes')
    is_refusal = fields.Boolean(string="Refusing the request", compute='_compute_is_refusal')
    has_changes = fields.Boolean(string="The request was corrected", compute='_compute_changes')
    changes = fields.Html(string="Changes", compute='_compute_changes')
    message = fields.Text(string="Message",
                          help="Sent to the employee alone: a message about the changes, or the "
                               "reason for the refusal. Optional.")

    @api.depends('method')
    def _compute_is_refusal(self):
        for wizard in self:
            wizard.is_refusal = wizard.method in REFUSAL_METHODS

    @api.depends('leave_id')
    def _compute_changes(self):
        for wizard in self:
            changes = wizard.leave_id._ems_request_changes() if wizard.leave_id else []
            wizard.has_changes = bool(changes)
            wizard.changes = self.env['ems.base'].build_html_list(changes)
            wizard.when = wizard.leave_id._ems_when() if wizard.leave_id else False

    def action_confirm(self):
        """Takes the decision the dialog interrupted, as the user who clicked it - the decision
        keeps its own access checks - and with what they wrote for the employee: a message
        about the changes or, when refusing, the reason."""
        self.ensure_one()
        if self.method not in DECISION_METHODS:
            raise UserError(_("This decision cannot be taken from here."))
        leave = self.leave_id.with_context(
            ems_ask_change_message=False, ems_change_message=(self.message or '').strip())
        getattr(leave, self.method)()
        return {'type': 'ir.actions.act_window_close'}
