# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class EmsMeetingPresenceLine(models.Model):
    _name = "ems.meeting.presence.line"
    _description = "Meeting attendance line"
    _order = "presence_id, employee_id, id"
    _sql_constraints = [
        ('unique_employee', 'unique (presence_id, employee_id)', "This person is already in the list."),
    ]

    presence_id = fields.Many2one(string="Meeting", comodel_name="ems.meeting.presence", required=True, ondelete='cascade', index=True)
    employee_id = fields.Many2one(string="Employee", comodel_name="hr.employee.public", required=True)
    state = fields.Selection(
        string="State",
        selection=[('pending', "Pending"), ('present', "Present"), ('justified', "Justified"), ('absent', "Absent")],
        required=True,
        default='pending',
    )
    checkin_time = fields.Datetime(string="Time", readonly=True, copy=False)
    method = fields.Selection(string="How", selection=[('nfc', "NFC tag"), ('manual', "By hand")], readonly=True, copy=False)
    is_convened = fields.Boolean(string="Convened", default=True, help="Not ticked for someone who passed the tag without being convened.")
    notes = fields.Char(string="Notes", help="For example, why an absence is justified.")

    def _check_session_not_closed(self):
        if self.presence_id.filtered(lambda presence: presence.state == 'closed'):
            raise UserError(_("This meeting attendance is closed: reopen it to change it."))

    @api.model_create_multi
    def create(self, vals_list):
        self.env['ems.meeting.presence'].browse([vals['presence_id'] for vals in vals_list if vals.get('presence_id')])._check_not_closed()
        if not self.env.context.get('ems_presence_scan'):
            # Someone marked present by a manager in the form: same bookkeeping as a scan.
            vals_list = [self._manual_vals(vals) if vals.get('state') == 'present' else vals for vals in vals_list]
        return super().create(vals_list)

    def write(self, vals):
        self._check_session_not_closed()
        if 'state' not in vals or self.env.context.get('ems_presence_scan'):
            return super().write(vals)
        # A manager changes a state by hand: the time and the way are bookkeeping, not something
        # they type. A line whose state does not actually change keeps its own (a scan stays a scan).
        result = True
        for line in self:
            line_vals = dict(vals)
            if line.state != vals['state']:
                line_vals.update(self._manual_vals(vals))
            result = super(EmsMeetingPresenceLine, line).write(line_vals) and result
        return result

    @api.model
    def _manual_vals(self, vals):
        if vals['state'] == 'present':
            return {**vals, 'checkin_time': fields.Datetime.now(), 'method': 'manual'}
        return {**vals, 'checkin_time': False, 'method': False}

    @api.ondelete(at_uninstall=False)
    def _unlink_only_open_and_not_present(self):
        self._check_session_not_closed()
        if self.filtered(lambda line: line.state == 'present'):
            raise UserError(_("Someone marked as present cannot be removed: mark them as pending or absent first."))
