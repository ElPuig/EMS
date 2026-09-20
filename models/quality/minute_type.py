# -*- coding: utf-8 -*-

from odoo import api, fields, models

# What a section actually renders. Everything that is just prose shares 'text'; the rest either
# drive a behaviour of their own (agreements, carried-over agreements, pending topics) or carry a
# table whose columns EMS can preload from data it already holds.
SECTION_KINDS = [
    ('text', "Free text"),
    ('agenda', "Agenda"),
    ('previous_approval', "Approval of the previous minute"),
    ('agreement_followup', "Follow-up of earlier agreements"),
    ('agreements', "Agreements"),
    ('pending_topics', "Pending topics"),
    ('annexes', "Annexes"),
    ('signature', "Signatures"),
    ('harmonisation', "Harmonisation"),
    ('clil', "CLIL (GEP)"),
    ('team_constitution', "Team constitution"),
    ('objectives', "Objectives and indicators"),
    ('meeting_calendar', "Meeting calendar"),
]


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
        domain="[('kind', '=', 'template')]",
        help="The controlled document this type is written against. Its code and version are quoted in the PDF.",
    )
    approver_role_id = fields.Many2one(string="Approved by", comodel_name="ems.role", help="The post that normally gives the approval.")
    print_identification = fields.Boolean(
        string="Print the identification number",
        help="Only for the minutes that need it: improvement team minutes carry the members' identification number because it is needed to claim the innovation credit.",
    )
    section_ids = fields.One2many(string="Sections", comodel_name="ems.minute.type.section", inverse_name="type_id")
    sequence = fields.Integer(string="Sequence", default=10)
    active = fields.Boolean(string="Active", default=True)

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for minute_type in self:
            minute_type.display_name = minute_type.name or minute_type.code

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
