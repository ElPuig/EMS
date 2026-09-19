# -*- coding: utf-8 -*-

from odoo import api, fields, models

from .common import QUALITY_STATE_CLOSED, QUALITY_STATES


class EmsQualityAction(models.Model):
    _name = "ems.quality.action"
    _description = "Quality action: a meeting agreement or an improvement action, which are the same thing."
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = "deadline_date, id desc"
    _sql_constraints = [
        ('unique_code', 'unique (code)', "Another action already uses this code."),
    ]

    code = fields.Char(string="Code", readonly=True, copy=False, index=True)
    name = fields.Char(string="Subject", required=True, tracking=True)
    description = fields.Html(string="Description")
    # One model for both because they are the same concept - owner, deadline, follow-up, closure -
    # and unifying them is what makes a single "what do I owe and by when" screen possible.
    type = fields.Selection(
        string="Type",
        selection=[
            ('agreement', "Agreement"),
            ('immediate', "Immediate action"),
            ('repair', "Repair action"),
            ('corrective', "Corrective action"),
            ('preventive', "Preventive action"),
            ('improvement', "Improvement action"),
            ('change', "Change plan"),
        ],
        required=True,
        default='agreement',
        tracking=True,
    )
    responsible_role_id = fields.Many2one(string="Responsible post", comodel_name="ems.role", tracking=True)
    # The centre's own records hold values like "<name> + volunteers" or "management team and
    # department heads", so several people must be expressible alongside the post.
    responsible_employee_ids = fields.Many2many(
        string="Responsible people",
        comodel_name="hr.employee.public",
        relation="ems_quality_action_employee_rel",
        column1="action_id",
        column2="employee_id",
    )
    deadline_date = fields.Date(string="Deadline", tracking=True)
    # Real deadlines are often prose ("by the final meeting of the year"), so both are kept: the
    # date is what the overdue filter uses, the text is what the minute actually said.
    deadline_text = fields.Char(string="Deadline (as agreed)", help="When the deadline was agreed as a description rather than a date.")
    resources = fields.Char(string="Resources")
    completion_criteria = fields.Text(string="When will it be finished")
    efficacy_criteria = fields.Text(string="How will efficacy be measured")
    course_id = fields.Many2one(
        string="Course",
        comodel_name="ems.course",
        required=True,
        default=lambda self: self.env['ems.course'].search([('is_current', '=', True)], limit=1),
        tracking=True,
    )
    # Scope: drives the code sequence, the search facets and the record rules.
    department_id = fields.Many2one(string="Department", comodel_name="hr.department", tracking=True)
    workgroup_id = fields.Many2one(string="Workgroup", comodel_name="ems.workgroup", tracking=True)
    group_id = fields.Many2one(string="Group", comodel_name="ems.group", tracking=True)
    is_centre = fields.Boolean(string="Centre-wide", help="For agreements of a staff meeting or of the management review, which hang off no department.")
    scope_name = fields.Char(string="Scope", compute="_compute_scope_name", store=True)
    followup_ids = fields.One2many(string="Follow-up", comodel_name="ems.quality.followup", inverse_name="action_id")
    state = fields.Selection(
        string="State",
        selection=QUALITY_STATES,
        compute="_compute_state",
        store=True,
        tracking=True,
        help="Derived from the latest follow-up entry: to move it forward, add one.",
    )
    is_late = fields.Boolean(string="Overdue", compute="_compute_is_late", store=True)
    active = fields.Boolean(string="Active", default=True)

    @api.depends('department_id', 'workgroup_id', 'group_id', 'is_centre')
    def _compute_scope_name(self):
        for action in self:
            action.scope_name = action._scope_label()

    @api.depends('followup_ids', 'followup_ids.state', 'followup_ids.date', 'responsible_role_id', 'responsible_employee_ids', 'deadline_date', 'deadline_text')
    def _compute_state(self):
        """The rule the centre's own spreadsheets implement, kept deliberately.

        There is no editable state field: moving an action forward means adding a follow-up
        entry, which is what keeps the reason on the record."""
        for action in self:
            latest = action._latest_followup()
            if latest:
                action.state = latest.state
            elif action.responsible_role_id or action.responsible_employee_ids or action.deadline_date or action.deadline_text:
                action.state = 'analysed'
            else:
                action.state = 'new'

    @api.depends('deadline_date', 'state')
    def _compute_is_late(self):
        today = fields.Date.context_today(self)
        for action in self:
            action.is_late = bool(action.deadline_date) and action.state != QUALITY_STATE_CLOSED and action.deadline_date < today

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('code'):
                vals['code'] = self.new(vals)._next_code()
        return super().create(vals_list)

    def _latest_followup(self):
        """The most recent follow-up entry, by date and then by creation order.

        Two entries can share a date (a meeting that reviews several agreements at once), so id
        breaks the tie rather than leaving the state dependent on insertion order."""
        self.ensure_one()
        return self.followup_ids.sorted(key=lambda line: (line.date or fields.Date.today(), line.id))[-1:]

    def _scope_label(self):
        """Short label of the scope this action belongs to, used in codes and lists."""
        self.ensure_one()
        if self.department_id:
            return self.department_id.name
        if self.workgroup_id:
            return self.workgroup_id.name
        if self.group_id:
            return self.group_id.name
        return "Centre" if self.is_centre else ""

    def _scope_code(self):
        """The scope's short code, for the sequence prefix.

        hr.department and ems.workgroup have no code field of their own yet (issue #496 adds one),
        so this falls back to an uppercase initialism of the name: readable, stable enough for a
        prefix, and replaced by the real code as soon as the field exists."""
        self.ensure_one()
        if self.group_id:
            return self.group_id.name.upper().replace(' ', '')
        record = self.department_id or self.workgroup_id
        if record:
            code = getattr(record, 'code', False)
            if code:
                return code.upper()
            return ''.join(word[0] for word in record.name.split() if word)[:4].upper()
        return "CEN"

    def _next_code(self):
        """One sequence per (scope, action type family, course), created on demand.

        An ir.sequence rather than a computed max+1: two people approving records at the same
        time must not get the same number, and only the sequence guarantees that."""
        self.ensure_one()
        course = self.course_id or self.env['ems.course'].search([('is_current', '=', True)], limit=1)
        scope_code = self._scope_code() or "CEN"
        short_code = course.short_code or (course.name or '').replace(' ', '')
        prefix = f"ACORD-{scope_code}-{short_code}-"
        sequence_code = f"ems.quality.action.{scope_code}.{short_code}"
        sequence = self.env['ir.sequence'].sudo().search([('code', '=', sequence_code)], limit=1)
        if not sequence:
            sequence = self.env['ir.sequence'].sudo().create({
                'name': f"Quality actions {scope_code} {short_code}",
                'code': sequence_code,
                'prefix': prefix,
                'padding': 3,
                'implementation': 'no_gap',
            })
        return sequence.next_by_id()

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for action in self:
            action.display_name = f"{action.code} {action.name}" if action.code else action.name
