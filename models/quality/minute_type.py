# -*- coding: utf-8 -*-

from odoo import api, fields, models

# What a section actually renders. Everything that is just prose shares 'text'; the rest either
# drive a behaviour of their own (agreements, carried-over agreements, pending topics) or carry a
# table whose columns EMS can preload from data it already holds.
SECTION_KINDS = [
    ('text', "Free text"),
    ('development', "Development of the session"),
    ('agenda', "Agenda"),
    ('previous_approval', "Approval of the previous minute"),
    ('agreement_followup', "Follow-up of earlier agreements"),
    ('agreements', "Agreements"),
    ('pending_topics', "Pending topics"),
    ('annexes', "Annexes"),
    ('signature', "Signatures"),
    ('team_constitution', "Team constitution"),
    ('objectives', "Objectives and indicators"),
    ('meeting_calendar', "Meeting calendar"),
]


# The minute field that holds each scope's department, group or workgroup.
SCOPE_FIELDS = {'department': 'department_id', 'teaching_team': 'group_id', 'workgroup': 'workgroup_id'}


class EmsMinuteSection(models.Model):
    _name = "ems.minute.section"
    _description = "Minute section: one of the blocks a minute can be made of."
    _order = "name"
    _sql_constraints = [
        ('unique_code', 'unique (code)', "Another section already uses this code."),
    ]

    code = fields.Char(string="Code", required=True)
    name = fields.Char(string="Name", required=True, translate=True)
    kind = fields.Selection(string="Kind", selection=SECTION_KINDS, required=True, default='text')
    help_text = fields.Text(string="Guidance", translate=True, help="Shown to whoever writes the minute, above the section.")
    in_agenda = fields.Boolean(
        string="In the agenda",
        help="The section is one of the points of the meeting's agenda, the one sent with the call: "
             "approving the previous minute, following up the agreements, the items to discuss, any other business.",
    )
    active = fields.Boolean(string="Active", default=True)

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for section in self:
            section.display_name = section.name or section.code


class EmsMinuteType(models.Model):
    _name = "ems.minute.type"
    _description = "Minute type: which sections a kind of minute carries, and who approves it."
    _order = "sequence, name"
    _sql_constraints = [
        ('unique_code', 'unique (code)', "Another minute type already uses this code."),
    ]

    code = fields.Char(string="Code", required=True)
    name = fields.Char(string="Name", required=True, translate=True)
    # A meeting deliberates and produces agreements; a record just states that something happened.
    # Same model, same machinery, different sections - which is why adding either is configuration.
    kind = fields.Selection(
        string="Kind",
        selection=[('meeting', "Meeting minute"), ('record', "Evidence record")],
        required=True,
        default='meeting',
    )
    scope_kind = fields.Selection(
        string="Scope",
        selection=[
            ('department', "Department"),
            ('workgroup', "Workgroup"),
            ('teaching_team', "Teaching team (group)"),
            ('centre', "Centre-wide"),
            ('generic', "Generic"),
        ],
        required=True,
        default='generic',
        help="What the minute hangs off. It decides whose attendees are preloaded and how the code is numbered.",
    )
    template_document_id = fields.Many2one(
        string="Controlled template",
        comodel_name="ems.quality.document",
        help="The controlled document this type is written against. Its code is quoted in the PDF.",
    )
    approver_role_id = fields.Many2one(string="Approved by", comodel_name="ems.role", help="The post that normally gives the approval.")
    print_identification = fields.Boolean(
        string="Print the identification number",
        help="Only for the minutes that need it: improvement team minutes carry the members' identification number because it is needed to claim the innovation credit.",
    )
    section_ids = fields.One2many(string="Sections", comodel_name="ems.minute.type.section", inverse_name="type_id")
    sequence = fields.Integer(string="Sequence", default=10)
    active = fields.Boolean(string="Active", default=True)
    # Who can start one. With neither set, anybody can: a teacher is only offered the kinds they
    # can actually start, instead of every kind of meeting the centre holds.
    starter_role_ids = fields.Many2many(
        string="Started by",
        comodel_name="ems.role",
        relation="ems_minute_type_starter_role_rel",
        column1="type_id",
        column2="role_id",
        help="The posts whose holders can start this kind of minute, for any scope. With none, and the option below off, anybody can.",
    )
    starter_scope = fields.Boolean(
        string="Also started by the people of its scope",
        help="A department's: its Department and Seminar Chiefs and those above them. A group's: its tutor, those above them and its teachers. A workgroup's: its members. Only for their own department, group or workgroup.",
    )
    can_start = fields.Boolean(string="Can start it", compute="_compute_can_start", search="_search_can_start")

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for minute_type in self:
            minute_type.display_name = minute_type.name or minute_type.code

    @api.depends_context('uid')
    @api.depends('starter_role_ids', 'starter_scope', 'scope_kind')
    def _compute_can_start(self):
        startable = self._ems_startable()
        for minute_type in self:
            minute_type.can_start = minute_type in startable

    def _search_can_start(self, operator, value):
        if operator not in ('=', '!=') or not isinstance(value, bool):
            raise NotImplementedError()
        startable = self.search([])._ems_startable()
        return [('id', 'in' if (operator == '=') == value else 'not in', startable.ids)]

    def _ems_startable(self):
        """The kinds among these the current user can start, for some scope or other."""
        return self.filtered(lambda minute_type: minute_type._ems_starts_anywhere()
                             or (minute_type.starter_scope and minute_type._ems_scope_records()))

    def _ems_starts_anywhere(self):
        """Whether the current user can start this kind of minute whatever its scope: anybody can,
        they hold one of its posts, or they administer EMS or the quality system."""
        self.ensure_one()
        user = self.env.user
        if self.env.su or user.has_group('ems.group_academic_admin') or user.has_group('ems.group_quality_admin'):
            return True
        if not self.starter_role_ids and not self.starter_scope:
            return True
        return bool(self.starter_role_ids.sudo().employee_ids.filtered(lambda employee: employee.user_id == user))

    def _ems_scope_records(self):
        """The departments, groups or workgroups through which the current user can start this kind
        of minute, as one of their people (see starter_scope); False for a kind with no such scope."""
        self.ensure_one()
        uid = self.env.uid
        if self.scope_kind == 'department':
            return self.env['hr.department'].sudo().search([
                '|', ('manager_id.tutor_scope_user_ids', '=', uid), ('seminar_chief_id.tutor_scope_user_ids', '=', uid)])
        if self.scope_kind == 'teaching_team':
            taught = self.env['ems.teaching'].sudo().search([('teacher_id.user_id', '=', uid)]).group_id
            return self.env['ems.group'].sudo().search([
                '|', ('tutor_id.tutor_scope_user_ids', '=', uid), ('id', 'in', taught.ids)])
        if self.scope_kind == 'workgroup':
            return self.env['ems.workgroup'].sudo().search([('employee_ids.user_id', '=', uid)])
        return False

    def _ems_can_start(self, scope_record):
        """Whether the current user can start this kind of minute for this department, group or
        workgroup."""
        self.ensure_one()
        if self._ems_starts_anywhere():
            return True
        scope_records = self.starter_scope and self._ems_scope_records()
        return bool(scope_records) and bool(scope_record) and scope_record in scope_records

    def _has_section(self, kind):
        self.ensure_one()
        return kind in self.section_ids.mapped('section_id.kind')


class EmsMinuteTypeSection(models.Model):
    _name = "ems.minute.type.section"
    _description = "Minute type section: a section of a minute type, in its place."
    _order = "type_id, sequence, id"

    type_id = fields.Many2one(string="Minute type", comodel_name="ems.minute.type", required=True, ondelete='cascade')
    section_id = fields.Many2one(string="Section", comodel_name="ems.minute.section", required=True, ondelete='restrict')
    sequence = fields.Integer(string="Sequence", default=10)
    intro_text = fields.Text(string="Introduction", translate=True, help="Optional text shown at the top of the section in this type of minute.")
    required = fields.Boolean(string="Required", help="The minute cannot be approved while this section is empty.")
    kind = fields.Selection(string="Kind", related="section_id.kind", store=True)
