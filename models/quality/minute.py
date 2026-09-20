# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import UserError

# What the old free-text 'type' column held, kept in step with the new type's scope so the column
# stays meaningful for anything reading the database directly. It is no longer used by the
# application and can be dropped by a version that ships a migration for it.
_LEGACY_TYPE_BY_SCOPE = {
    'department': 'department',
    'workgroup': 'workgroup',
    'teaching_team': 'evaluation',
    'centre': 'department',
    'generic': 'department',
}


class EmsMinute(models.Model):
    _name = "ems.minute"
    _description = "Minute: a meeting minute or an evidence record, written, approved and filed."
    _inherit = ['ems.signed.record', 'mail.thread', 'mail.activity.mixin']
    _order = "date desc, id desc"
    _sql_constraints = [
        ('unique_code', 'unique (code)', "Another minute already uses this code."),
    ]

    name = fields.Char(string="Title", compute="_compute_name", store=True, readonly=False, tracking=True)
    type_id = fields.Many2one(string="Type", comodel_name="ems.minute.type", required=True, ondelete='restrict', tracking=True)
    type_kind = fields.Selection(string="Kind", related="type_id.kind", store=True)
    scope_kind = fields.Selection(string="Scope kind", related="type_id.scope_kind")
    time = fields.Char(string="Time", help="As the minute states it, for example 12:00.")
    nature = fields.Selection(
        string="Nature",
        selection=[("ordinary", "Ordinary"), ("extraordinary", "Extraordinary")],
        required=True,
        default="ordinary",
    )
    modality = fields.Selection(
        string="Modality",
        selection=[("in-person", "In-person"), ("online", "Online"), ("hybrid", "Hybrid")],
        required=True,
        default="in-person",
    )
    space_id = fields.Many2one(string="Room", comodel_name="ems.space")
    place_text = fields.Char(string="Place", help="For a meeting held somewhere that is not a room of the centre: a video call, a mailing list.")
    place_name = fields.Char(string="Where", compute="_compute_place_name")

    # Scope. Exactly one of these is meaningful, decided by the type's own scope_kind.
    department_id = fields.Many2one(string="Department", comodel_name="hr.department", tracking=True)
    workgroup_id = fields.Many2one(string="Workgroup", comodel_name="ems.workgroup", tracking=True)
    group_id = fields.Many2one(string="Group", comodel_name="ems.group", tracking=True)
    is_centre = fields.Boolean(string="Centre-wide")
    scope_name = fields.Char(string="Scope", compute="_compute_scope_name", store=True)
    course_id = fields.Many2one(
        string="Course",
        comodel_name="ems.course",
        required=True,
        default=lambda self: self.env['ems.course'].search([('is_current', '=', True)], limit=1),
    )

    attendee_ids = fields.Many2many(
        string="Attendees",
        comodel_name="hr.employee.public",
        relation="ems_minute_attendee_rel",
        column1="minute_id",
        column2="employee_id",
    )
    absentee_ids = fields.Many2many(
        string="Absentees",
        comodel_name="hr.employee.public",
        relation="ems_minute_absentee_rel",
        column1="minute_id",
        column2="employee_id",
    )
    absence_notes = fields.Char(string="About the absences", help="For example, which of them were justified.")
    attendee_count = fields.Integer(string="Number of attendees", compute="_compute_attendee_count")

    previous_minute_id = fields.Many2one(string="Previous minute", comodel_name="ems.minute", ondelete='set null')
    previous_approved = fields.Selection(
        string="Previous minute approved",
        selection=[('yes', "Approved"), ('with_changes', "Approved with changes"), ('no', "Not approved"), ('na', "Not applicable")],
        default='na',
    )
    previous_approval_notes = fields.Text(string="Notes on the previous minute")

    agenda_ids = fields.One2many(string="Agenda", comodel_name="ems.minute.agenda", inverse_name="minute_id")
    section_value_ids = fields.One2many(string="Sections", comodel_name="ems.minute.section.value", inverse_name="minute_id")
    agreement_ids = fields.One2many(string="Agreements", comodel_name="ems.quality.action", inverse_name="minute_id")
    followed_agreement_ids = fields.Many2many(
        string="Agreements followed up",
        comodel_name="ems.quality.action",
        relation="ems_minute_followed_agreement_rel",
        column1="minute_id",
        column2="action_id",
        help="Agreements of earlier minutes of the same scope that were still open and got reviewed here.",
    )
    pending_topic_ids = fields.One2many(string="Pending topics", comodel_name="ems.minute.pending.topic", inverse_name="minute_id")
    annex_document_ids = fields.Many2many(
        string="Annexes",
        comodel_name="ems.quality.document",
        relation="ems_minute_annex_rel",
        column1="minute_id",
        column2="document_id",
    )

    redactor_employee_id = fields.Many2one(
        string="Written by",
        comodel_name="hr.employee.public",
        default=lambda self: self.env['hr.employee.public'].search([('user_id', '=', self.env.uid)], limit=1),
        tracking=True,
    )
    approver_role_id = fields.Many2one(string="Approved by (post)", comodel_name="ems.role", tracking=True)
    approver_employee_id = fields.Many2one(string="Approved by", comodel_name="hr.employee.public", readonly=True, copy=False, tracking=True)
    approval_date = fields.Date(string="Approved on", readonly=True, copy=False)

    # Sections that carry a table of their own.
    harmonisation_line_ids = fields.One2many(string="Harmonisation", comodel_name="ems.minute.harmonisation.line", inverse_name="minute_id")
    clil_line_ids = fields.One2many(string="CLIL", comodel_name="ems.minute.clil.line", inverse_name="minute_id")
    member_line_ids = fields.One2many(string="Team members", comodel_name="ems.minute.member.line", inverse_name="minute_id")
    objective_line_ids = fields.One2many(string="Objectives", comodel_name="ems.minute.objective.line", inverse_name="minute_id")
    team_date_from = fields.Date(string="Team starts")
    team_date_to = fields.Date(string="Team ends")

    abstract = fields.Char(string="Abstract or main topic", size=255)
    # Superseded by type_id; kept only so the existing NOT NULL column stays populated, and
    # computed so it still says something sensible to anyone reading the table directly.
    type = fields.Selection(
        string="Type (legacy)",
        selection=[("department", "Department meeting"), ("workgroup", "Workgroup meeting"), ("evaluation", "Evaluation meeting")],
        compute="_compute_legacy_type",
        store=True,
        readonly=True,
    )

    @api.depends('type_id', 'scope_name', 'date')
    def _compute_name(self):
        for minute in self:
            if not minute.type_id:
                minute.name = minute.name or ""
                continue
            scope = minute.scope_name
            minute.name = f"{minute.type_id.name} - {scope}" if scope else minute.type_id.name

    @api.depends('department_id', 'workgroup_id', 'group_id', 'is_centre')
    def _compute_scope_name(self):
        for minute in self:
            minute.scope_name = minute._scope_label()

    @api.depends('space_id', 'place_text')
    def _compute_place_name(self):
        for minute in self:
            minute.place_name = minute.space_id.name or minute.place_text or ""

    @api.depends('attendee_ids')
    def _compute_attendee_count(self):
        for minute in self:
            minute.attendee_count = len(minute.attendee_ids)

    @api.depends('type_id')
    def _compute_legacy_type(self):
        for minute in self:
            minute.type = _LEGACY_TYPE_BY_SCOPE.get(minute.type_id.scope_kind, 'department')

    @api.onchange('type_id')
    def _onchange_type_id(self):
        """Lay out the minute as its type declares it, and preload what EMS already knows."""
        if not self.type_id:
            return
        self.template_document_id = self.type_id.template_document_id
        self.approver_role_id = self.type_id.approver_role_id
        self.is_centre = self.type_id.scope_kind == 'centre'
        self._ems_build_sections()

    @api.onchange('department_id', 'workgroup_id', 'group_id', 'is_centre')
    def _onchange_scope(self):
        if self.type_id:
            self._ems_preload_attendees()
            self._ems_preload_previous()

    @api.model_create_multi
    def create(self, vals_list):
        minutes = super().create(vals_list)
        for minute in minutes:
            # The onchange only fires in the form: a minute created by code, by an import or by a
            # future wizard must end up laid out the same way, or its PDF would quote no template.
            if not minute.template_document_id:
                minute.template_document_id = minute.type_id.template_document_id
            if not minute.approver_role_id:
                minute.approver_role_id = minute.type_id.approver_role_id
            if minute.type_id.scope_kind == 'centre' and not minute.is_centre:
                minute.is_centre = True
            if not minute.section_value_ids:
                minute._ems_build_sections()
            if not minute.attendee_ids:
                minute._ems_preload_attendees()
            if not minute.previous_minute_id:
                minute._ems_preload_previous()
            if not minute.code:
                minute.code = minute._ems_next_code()
        return minutes

    def _scope_label(self):
        self.ensure_one()
        if self.department_id:
            return self.department_id.name
        if self.workgroup_id:
            return self.workgroup_id.name
        if self.group_id:
            return self.group_id.name
        return _("Centre") if self.is_centre else ""

    def _ems_scope_code(self):
        self.ensure_one()
        if self.group_id:
            return self.group_id.name.upper().replace(' ', '')
        record = self.department_id or self.workgroup_id
        if record:
            return ''.join(word[0] for word in record.name.split() if word)[:4].upper()
        # Centre-wide minutes hang off no department, so the type itself is the numbering scope:
        # that keeps a staff meeting from sharing a counter with the management review.
        return (self.type_id.code or "CEN").upper()

    def _ems_next_code(self):
        self.ensure_one()
        scope_code = self._ems_scope_code()
        short_code = self.course_id.short_code or (self.course_id.name or '').replace(' ', '')
        sequence_code = f"ems.minute.{scope_code}.{short_code}"
        sequence = self.env['ir.sequence'].sudo().search([('code', '=', sequence_code)], limit=1)
        if not sequence:
            sequence = self.env['ir.sequence'].sudo().create({
                'name': f"Minutes {scope_code} {short_code}",
                'code': sequence_code,
                'prefix': f"ACTA-{scope_code}-{short_code}-",
                'padding': 3,
                'implementation': 'no_gap',
            })
        return sequence.next_by_id()

    def _ems_build_sections(self):
        """Give the minute the sections its type declares, in order, keeping whatever was already
        written in sections the type still has."""
        self.ensure_one()
        written = {value.section_id.id: value for value in self.section_value_ids if value.content}
        commands = [(5, 0, 0)]
        for line in self.type_id.section_ids.sorted('sequence'):
            existing = written.get(line.section_id.id)
            commands.append((0, 0, {
                'section_id': line.section_id.id,
                'sequence': line.sequence,
                'content': existing.content if existing else False,
            }))
        self.section_value_ids = commands

    def _ems_preload_attendees(self):
        """Fill the attendee list from the scope, which is the single biggest saving of this whole
        feature: a staff meeting has around a hundred attendees and they are typed by hand today."""
        self.ensure_one()
        employees = self.env['hr.employee.public']
        if self.department_id:
            employees = employees.search([('department_id', '=', self.department_id.id)])
        elif self.workgroup_id:
            employees = self.workgroup_id.employee_ids
        elif self.group_id:
            employees = self.env['hr.employee.public'].browse(self._ems_teaching_team_ids())
        elif self.is_centre:
            employees = employees.search([('employee_type', '=', 'teacher')])
        if employees:
            self.attendee_ids = [(6, 0, employees.ids)]

    def _ems_teaching_team_ids(self):
        """The teachers who teach the group, through the teaching assignment EMS already holds."""
        self.ensure_one()
        teachings = self.env['ems.teaching'].search([('group_id', '=', self.group_id.id)])
        return teachings.mapped('teacher_id').ids

    def _ems_preload_previous(self):
        """Point at the previous minute of the same type and scope, and pull its still-open
        agreements and pending topics in - the carry-over nobody does by hand."""
        self.ensure_one()
        if not self.type_id:
            return
        domain = [('type_id', '=', self.type_id.id), ('id', '!=', self.id or 0)]
        for field_name in ('department_id', 'workgroup_id', 'group_id'):
            if self[field_name]:
                domain.append((field_name, '=', self[field_name].id))
        if self.is_centre:
            domain.append(('is_centre', '=', True))
        previous = self.search(domain, order="date desc, id desc", limit=1)
        if not previous:
            return
        self.previous_minute_id = previous
        self.previous_approved = 'na'
        open_agreements = previous.agreement_ids.filtered(lambda action: action.state != 'closed')
        if open_agreements:
            self.followed_agreement_ids = [(6, 0, open_agreements.ids)]
        pending = previous.pending_topic_ids.filtered(lambda topic: not topic.is_done)
        if pending:
            self.pending_topic_ids = [(0, 0, {
                'name': topic.name,
                'carried_from_minute_id': previous.id,
            }) for topic in pending]

    def _ems_check_can_approve(self):
        self.ensure_one()
        if not self.redactor_employee_id:
            raise UserError(_("A minute needs to say who wrote it before it can be approved."))
        missing = self.section_value_ids.filtered(lambda value: value.required and not value.content)
        if missing:
            raise UserError(_("These sections are required by this type of minute and are still empty: %s",
                              ", ".join(missing.mapped('section_id.name'))))
        return True

    def action_approve(self):
        """Record who approved it, on top of what the shared machinery does."""
        employee = self.env['hr.employee.public'].search([('user_id', '=', self.env.uid)], limit=1)
        for minute in self:
            minute.approver_employee_id = employee
            minute.approval_date = fields.Date.context_today(minute)
        return super().action_approve()

    def _ems_report_xmlid(self):
        return 'ems.action_report_minute'

    def _ems_file_name(self):
        self.ensure_one()
        scope = (self.scope_name or '').replace('/', '-')
        return f"{self.code} {scope} {self.date}.pdf".replace('  ', ' ')

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for minute in self:
            minute.display_name = f"{minute.code} {minute.name}" if minute.code else (minute.name or "")
