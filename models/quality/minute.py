# -*- coding: utf-8 -*-

from datetime import timedelta
from urllib.parse import urlencode

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import format_date

from .common import SCOPE_CODE_LANG, scope_code

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
    _inherit = ['ems.signed.record', 'ems.quality.can.edit', 'mail.thread', 'mail.activity.mixin']
    _order = "date desc, id desc"
    _sql_constraints = [
        ('unique_code', 'unique (code)', "Another minute already uses this code."),
    ]

    # A meeting goes through one more stage than any other signed record: once it has been
    # prepared and called, it is held - and that is when its minute gets written.
    state = fields.Selection(selection_add=[('meeting', "Meeting"), ('to_approve',)], ondelete={'meeting': 'set default'})
    name = fields.Char(string="Title", compute="_compute_name", store=True, readonly=False, tracking=True)
    type_id = fields.Many2one(string="Type", comodel_name="ems.minute.type", required=True, ondelete='restrict', tracking=True)
    type_kind = fields.Selection(string="Kind", related="type_id.kind", store=True)
    scope_kind = fields.Selection(string="Scope kind", related="type_id.scope_kind")
    start_datetime = fields.Datetime(
        string="Date and time",
        default=lambda self: self._default_start_datetime(),
        tracking=True,
        help="When the meeting starts. The minute's date, its time and its course follow from it.",
    )
    time = fields.Char(string="Time", help="As the minute states it, for example 12:00.")
    duration = fields.Float(string="Duration", default=1.0, help="In hours. It gives the meeting its end in the calendar and, with the NFC tag, attendance is only taken between the start and the end.")
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
    # Only for a type whose scope is 'generic': which of the scopes above this particular minute has.
    scope_choice = fields.Selection(
        string="Scope of the meeting",
        selection=[
            ('none', "No particular scope"),
            ('department', "A department"),
            ('workgroup', "A workgroup"),
            ('group', "A group's teaching team"),
            ('centre', "The whole centre"),
        ],
        default='none',
    )
    code_preview = fields.Char(
        string="Code of the minute",
        compute="_compute_code_preview",
        help="The code the minute gets when it is saved, built up as its type, scope and date are filled in.",
    )
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
    attendance_mode = fields.Selection(
        string="Attendance",
        selection=[('manual', "Written by hand"), ('nfc', "With the NFC tag")],
        required=True,
        default='manual',
        tracking=True,
        help="By hand, whoever writes the minute ticks who attended. With the NFC tag, each person "
             "passes theirs at the meeting's kiosk and the lists fill in by themselves.",
    )
    call_sent_datetime = fields.Datetime(string="Call sent on", readonly=True, copy=False, tracking=True)
    call_recipient_count = fields.Integer(string="People the call was sent to", readonly=True, copy=False)
    presence_id = fields.Many2one(string="Attendance session", comodel_name="ems.meeting.presence", ondelete='set null', readonly=True, copy=False)
    # Read with sudo: whoever writes a minute runs its attendance, but the sessions themselves are
    # managed by the head of studies and the secretariat only.
    presence_state = fields.Selection(string="Attendance session state", related="presence_id.state", compute_sudo=True)

    previous_minute_id = fields.Many2one(string="Previous minute", comodel_name="ems.minute", ondelete='set null')
    previous_approved = fields.Selection(
        string="Previous minute approved",
        selection=[('yes', "Approved"), ('with_changes', "Approved with changes"), ('no', "Not approved"), ('na', "Not applicable")],
        default='na',
    )
    previous_approval_notes = fields.Text(string="Notes on the previous minute")

    agenda_ids = fields.One2many(string="Items to discuss", comodel_name="ems.minute.agenda", inverse_name="minute_id")
    agenda_html = fields.Html(
        string="Agenda",
        compute="_compute_agenda_html",
        sanitize=False,
        help="The meeting's agenda as it is sent with the call, put together from the sections of the "
             "minute type and the items to discuss.",
    )
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
    agreement_review_ids = fields.One2many(string="Agreements reviewed", comodel_name="ems.minute.agreement.review", inverse_name="minute_id")
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
    # The person, not the post: proposed from whoever answers for the scope that meets, and free to
    # be anybody else. Once approved it says who actually did.
    approver_employee_id = fields.Many2one(string="Approved by", comodel_name="hr.employee.public", copy=False, tracking=True)
    approver_candidate_ids = fields.Many2many(
        string="Who usually approves it",
        comodel_name="hr.employee.public",
        compute="_compute_approver_candidate_ids",
        help="The people who answer for the scope that meets: they come first when choosing who approves the minute.",
    )
    approval_date = fields.Date(string="Approved on", readonly=True, copy=False)
    # Who sent it for approval and when, for the stamp under the writer's name in the PDF: the
    # writer's side of the signature, as approval_date and approver_employee_id are the approver's.
    submission_date = fields.Date(string="Sent for approval on", readonly=True, copy=False)
    submitted_by_id = fields.Many2one(string="Sent for approval by", comodel_name="res.users", readonly=True, copy=False)
    can_approve = fields.Boolean(string="Can approve", compute="_compute_can_approve", help="Whether the current user is the one who approves this minute.")
    # Whoever may stand in for the person named to approve it: that person and their chain of
    # command (hr.employee.tutor_scope_user_ids: every chief above them, the Director). Searchable
    # for the record rules; not stored, so it always follows the current hierarchy.
    approver_scope_user_ids = fields.Many2many(
        string="Who can approve it", comodel_name="res.users",
        compute="_compute_approver_scope_user_ids", search="_search_approver_scope_user_ids")

    # Sections that carry a table of their own.
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

    @api.model
    def _default_start_datetime(self):
        """The next full hour, which is when meetings start more often than not."""
        return fields.Datetime.now().replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)

    @api.depends('type_id', 'scope_name', 'date')
    def _compute_name(self):
        for minute in self:
            if not minute.type_id:
                minute.name = minute.name or ""
                continue
            scope = minute.scope_name
            minute.name = f"{minute.type_id.name} - {scope}" if scope else minute.type_id.name

    def _ems_agenda_entries(self):
        """The points of the agenda, in order, as (title, [sub-items]).

        Nobody writes the agenda: it follows from the minute. The sections its type marks as part
        of the agenda give the points - approving the previous minute only when there is one,
        following up the agreements only when some are still open - and the section of kind
        'agenda' unfolds into the items to discuss, the only part that is typed in."""
        self.ensure_one()
        entries = []
        for section in self.type_id.section_ids.sorted('sequence').mapped('section_id').filtered('in_agenda'):
            if section.kind == 'previous_approval' and not self.previous_minute_id:
                continue
            if section.kind == 'agreement_followup' and not self.followed_agreement_ids:
                continue
            items = self.agenda_ids.sorted('sequence').mapped('name') if section.kind == 'agenda' else []
            entries.append((section.name, [item for item in items if item]))
        return entries

    @api.depends('type_id', 'previous_minute_id', 'followed_agreement_ids', 'agenda_ids.name', 'agenda_ids.sequence')
    def _compute_agenda_html(self):
        for minute in self:
            points = Markup()
            for title, items in minute._ems_agenda_entries():
                sub_list = Markup("<ol>%s</ol>") % Markup().join(Markup("<li>%s</li>") % item for item in items) if items else Markup()
                points += Markup("<li>%s%s</li>") % (title, sub_list)
            minute.agenda_html = Markup("<ol>%s</ol>") % points if points else False

    @api.depends('code', 'type_id', 'department_id', 'workgroup_id', 'group_id', 'is_centre', 'scope_choice', 'course_id')
    def _compute_code_preview(self):
        for minute in self:
            minute.code_preview = minute.code or minute._ems_code_preview()

    @api.depends('department_id', 'workgroup_id', 'group_id', 'is_centre')
    def _compute_scope_name(self):
        for minute in self:
            minute.scope_name = minute._scope_label()

    @api.depends('space_id', 'place_text')
    def _compute_place_name(self):
        for minute in self:
            # The room as the centre names it everywhere else, with its code: "Stallman (0.01)".
            # A hybrid meeting has both a room and somewhere to connect to.
            minute.place_name = " - ".join(filter(None, [minute.space_id.display_name, minute.place_text]))

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
        scope_kind = self.type_id.scope_kind
        # A scope left over from the type chosen before would number the minute under it.
        if scope_kind != 'generic':
            self.scope_choice = 'none'
            if scope_kind != 'department':
                self.department_id = False
            if scope_kind != 'workgroup':
                self.workgroup_id = False
            if scope_kind != 'teaching_team':
                self.group_id = False
        self.is_centre = scope_kind == 'centre'
        self._ems_build_sections()

    @api.onchange('scope_choice')
    def _onchange_scope_choice(self):
        if self.scope_kind != 'generic':
            return
        if self.scope_choice != 'department':
            self.department_id = False
        if self.scope_choice != 'workgroup':
            self.workgroup_id = False
        if self.scope_choice != 'group':
            self.group_id = False
        self.is_centre = self.scope_choice == 'centre'

    @api.onchange('start_datetime')
    def _onchange_start_datetime(self):
        if self.start_datetime:
            self.update(self._ems_vals_from_start(self.start_datetime))

    @api.onchange('department_id', 'workgroup_id', 'group_id', 'is_centre')
    def _onchange_scope(self):
        if self.type_id:
            self._ems_preload_attendees()
            self._ems_preload_previous()
            self.approver_employee_id = self._ems_approver_candidates()[:1]

    @api.model
    def _ems_vals_from_start(self, start):
        """What follows from when the meeting starts: its date and time as the centre reads them
        (the company's timezone, never UTC), and the course that day belongs to."""
        local = self.env['ems.datetime_utils'].utc_datetime_to_local(fields.Datetime.to_datetime(start))
        vals = {'date': local.date(), 'time': local.strftime('%H:%M')}
        # A course runs from 1 September to 31 August.
        course = self.env['ems.course'].search([('start', '=', local.year if local.month >= 9 else local.year - 1)], limit=1)
        if course:
            vals['course_id'] = course.id
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('date') and 'start_datetime' not in vals:
                # A minute dated by code (an import, a migration of older minutes) keeps that
                # date: the default start would move it to today.
                vals['start_datetime'] = False
            elif 'start_datetime' not in vals:
                vals['start_datetime'] = self._default_start_datetime()
            if vals.get('start_datetime'):
                derived = self._ems_vals_from_start(vals['start_datetime'])
                vals.update({key: value for key, value in derived.items() if key != 'course_id' or not vals.get('course_id')})
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
            if not minute.approver_employee_id:
                minute.approver_employee_id = minute._ems_approver_candidates()[:1]
            if not minute.section_value_ids:
                minute._ems_build_sections()
            if not minute.attendee_ids:
                minute._ems_preload_attendees()
            if not minute.previous_minute_id:
                minute._ems_preload_previous()
            if not minute.code:
                minute.code = minute._ems_next_code()
        minutes._ems_sync_presence()
        return minutes

    def write(self, vals):
        if vals.get('start_datetime'):
            derived = self._ems_vals_from_start(vals['start_datetime'])
            vals = {**derived, **vals, 'date': derived['date'], 'time': derived['time']}
        result = super().write(vals)
        if {'attendance_mode', 'start_datetime', 'duration', 'space_id'} & set(vals):
            self._ems_sync_presence()
        return result

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
        if record and scope_code(record):
            return scope_code(record)
        # Centre-wide minutes hang off no department, so the type itself is the numbering scope:
        # that keeps a staff meeting from sharing a counter with the management review.
        return (self.type_id.code or "CEN").upper()

    def _ems_scope_is_set(self):
        """Whether the minute already has the scope its type asks for, which is what its code is
        numbered under."""
        self.ensure_one()
        scope_kind = self.type_id.scope_kind
        if scope_kind == 'generic':
            scope_kind = {'group': 'teaching_team', 'none': 'centre'}.get(self.scope_choice, self.scope_choice)
        field_name = {'department': 'department_id', 'workgroup': 'workgroup_id', 'teaching_team': 'group_id'}.get(scope_kind)
        return bool(self.type_id) and (not field_name or bool(self[field_name]))

    def _ems_course_short_code(self):
        self.ensure_one()
        return self.course_id.short_code or (self.course_id.name or '').replace(' ', '')

    def _ems_sequence_code(self):
        self.ensure_one()
        return f"ems.minute.{self._ems_scope_code()}.{self._ems_course_short_code()}"

    def _ems_code_preview(self):
        """The code as far as it can be told before saving: each part appears once the field it
        comes from is filled in, and the number is the one the next minute of that scope and
        course would get. Nothing is reserved: the real code is issued on saving."""
        self.ensure_one()
        if not self.type_id or not self._ems_scope_is_set():
            return "ACTA"
        parts = ["ACTA", self._ems_scope_code()]
        if self.course_id:
            sequence = self.env['ir.sequence'].sudo().search([('code', '=', self._ems_sequence_code())], limit=1)
            parts += [self._ems_course_short_code(), f"{sequence.number_next_actual if sequence else 1:03d}"]
        return "-".join(parts)

    def _ems_next_code(self):
        self.ensure_one()
        scope_code = self._ems_scope_code()
        short_code = self._ems_course_short_code()
        sequence_code = self._ems_sequence_code()
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
        self.previous_minute_id = previous
        self.previous_approved = 'na'
        # Its own agreements and the older ones it was still following: an agreement stays on the
        # table, meeting after meeting, until somebody closes it.
        open_agreements = (previous.agreement_ids | previous.followed_agreement_ids).filtered(lambda action: action.state != 'closed')
        self.followed_agreement_ids = [(6, 0, open_agreements.ids)]
        # One line per agreement to review, keeping what was already written about the ones still there.
        self.agreement_review_ids -= self.agreement_review_ids.filtered(lambda review: review.action_id not in open_agreements)
        self.agreement_review_ids = [(0, 0, {'action_id': action.id}) for action in open_agreements - self.agreement_review_ids.action_id]
        pending = previous.pending_topic_ids.filtered(lambda topic: not topic.is_done)
        # Whatever an earlier choice of scope had carried over goes first: changing the department
        # in the form must not leave the other department's topics behind.
        self.pending_topic_ids -= self.pending_topic_ids.filtered('carried_from_minute_id')
        self.pending_topic_ids = [(0, 0, {
            'name': topic.name,
            'carried_from_minute_id': previous.id,
        }) for topic in pending]

    # --- Call to the meeting ---------------------------------------------------------------------

    @api.model
    def _ems_centre_lang(self):
        """The language the centre's own documents are written in - a minute, its call - whatever
        language whoever produces them works in (see common.SCOPE_CODE_LANG)."""
        return SCOPE_CODE_LANG if self.env['res.lang']._lang_get(SCOPE_CODE_LANG) else self.env.lang

    def _ems_call_values(self):
        """What the call says: when and where, the agenda, and where to read the previous minute."""
        self.ensure_one()
        previous = self.previous_minute_id
        return {
            'minute': self,
            'is_update': bool(self.call_sent_datetime),
            'date_label': format_date(self.env, self.date),
            'modality_label': dict(self._fields['modality']._description_selection(self.env)).get(self.modality),
            'nature_label': dict(self._fields['nature']._description_selection(self.env)).get(self.nature),
            'previous_url': previous and f"{self.get_base_url()}/odoo/action-ems.action_minute/{previous.id}",
            'calendar_url': self._ems_google_calendar_url(),
            'convener_name': self._ems_convener().name,
        }

    def _ems_convener(self):
        """Who calls the meeting: whoever is to approve its minute, which by default is the person
        answering for the scope that meets (the department's chief for a department minute), not
        whoever happens to be writing it. The writer when nobody is named."""
        self.ensure_one()
        return (self.approver_employee_id or self.redactor_employee_id
                or self.env['hr.employee.public'].search([('user_id', '=', self.env.uid)], limit=1))

    def _ems_approver_candidates(self):
        """The people who answer for the scope that meets, most likely first: a department's chief
        and its seminar chief, a group's tutor, the director for the whole centre; and, for a scope
        with nobody of its own (a workgroup), the few holders of the post the type names."""
        self.ensure_one()
        people = self.env['hr.employee']
        department = self.department_id.sudo()
        if department:
            people = department.manager_id | department.seminar_chief_id
        elif self.group_id:
            people = self.group_id.sudo().tutor_id
        elif self.is_centre:
            people = self.env.company.sudo().director_id
        candidates = self.env['hr.employee.public'].browse(people.ids)
        if not candidates and self.approver_role_id:
            holders = self.env['hr.employee.public'].search([('role_ids', 'in', self.approver_role_id.ids)], limit=6)
            candidates = holders if len(holders) <= 5 else candidates
        return candidates

    @api.depends('type_id', 'department_id', 'workgroup_id', 'group_id', 'is_centre', 'approver_role_id')
    def _compute_approver_candidate_ids(self):
        for minute in self:
            minute.approver_candidate_ids = minute._ems_approver_candidates()

    @api.depends('approver_employee_id')
    def _compute_approver_scope_user_ids(self):
        Employee = self.env['hr.employee'].sudo().with_context(active_test=False)
        for minute in self:
            minute.approver_scope_user_ids = Employee.browse(minute.approver_employee_id.id).tutor_scope_user_ids

    def _search_approver_scope_user_ids(self, operator, value):
        if operator not in ('=', 'in'):
            raise NotImplementedError(_("Unsupported search on approver_scope_user_ids"))
        approvers = self.env['hr.employee'].sudo().with_context(active_test=False).search([('tutor_scope_user_ids', operator, value)])
        return [('approver_employee_id', 'in', approvers.ids)]

    @api.depends('approver_employee_id', 'approver_role_id')
    @api.depends_context('uid')
    def _compute_can_approve(self):
        for minute in self:
            minute.can_approve = minute._ems_user_may_approve()

    def _ems_user_may_approve(self):
        """Who gives the approval: the person named to give it or anybody above them in the chain
        of command (when they are away, their Department Chief, Head or Deputy Head of Studies or
        the Director stands in), or, while nobody is named, whoever holds the post the minute
        names; above them all, the administrator. Never whoever wrote the minute just for having
        written it, nor anybody who can merely edit it."""
        self.ensure_one()
        user = self.env.user
        if self.env.su or user.has_group('ems.group_academic_admin'):
            return True
        if self.approver_employee_id:
            return user in self.approver_scope_user_ids
        return user in self.approver_role_id.sudo().employee_ids.user_id

    def _ems_google_calendar_url(self):
        """A link that opens Google Calendar with this meeting filled in, for each person to add
        it to their own calendar: its start and end (in UTC, which is what the link takes), the
        room and the agenda."""
        self.ensure_one()
        if not self.start_datetime:
            return False
        stamp = lambda moment: moment.strftime('%Y%m%dT%H%M%SZ')
        end = self.start_datetime + timedelta(hours=self.duration if self.duration > 0 else 1.0)
        lines = []
        for position, (title, items) in enumerate(self._ems_agenda_entries(), start=1):
            lines.append(f"{position}. {title}")
            lines += [f"   {position}.{sub_position}. {item}" for sub_position, item in enumerate(items, start=1)]
        return "https://calendar.google.com/calendar/render?" + urlencode({
            'action': 'TEMPLATE',
            'text': self.name or self.display_name,
            'dates': f"{stamp(self.start_datetime)}/{stamp(end)}",
            'location': self.place_name or '',
            'details': "\n".join(lines),
        })

    def action_send_call(self):
        """Email the call to everybody convened: the meeting's date, time and place, its agenda and
        a link to the previous minute, so it can be read before it is approved. It can be sent
        again whenever something changes; a second call says it replaces the first."""
        self.ensure_one()
        self.check_access('write')
        self = self.with_context(lang=self._ems_centre_lang())
        if self.state == 'approved' or self.type_kind == 'record':
            raise UserError(_("A call can only be sent for a meeting whose minute is not approved yet."))
        if not self.start_datetime:
            raise UserError(_("Set the date and time of the meeting before sending its call."))
        recipients = self.attendee_ids.filtered('work_email')
        if not recipients:
            raise UserError(_("There is nobody to send the call to: none of the people convened has an email address."))
        values = self._ems_call_values()
        subject = (_("Updated call: %s", self.name) if values['is_update'] else _("Call: %s", self.name))
        mail = self.env['mail.mail'].sudo().create({
            'subject': f"{subject} ({values['date_label']}, {self.time})",
            'body_html': self.env['ir.qweb']._render('ems.minute_call_email', values, minimal_qcontext=True),
            'email_from': self.env.user.email_formatted or self.env.company.email_formatted,
            'reply_to': self.env.user.email_formatted or self.env.company.email_formatted,
            'email_to': ", ".join(recipients.mapped('work_email')),
            'model': self._name,
            'res_id': self.id,
            'auto_delete': False,
        })
        mail.send()
        self.write({'call_sent_datetime': fields.Datetime.now(), 'call_recipient_count': len(recipients)})
        self.message_post(body=_("Call sent to %s people.", len(recipients)))
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'type': 'success', 'message': _("The call has been sent to %s people.", len(recipients)),
                       'next': {'type': 'ir.actions.act_window_close'}},
        }

    # --- Attendance with the NFC tag -----------------------------------------------------------

    def _ems_presence_scope(self):
        self.ensure_one()
        if self.department_id:
            return 'department'
        if self.workgroup_id:
            return 'workgroup'
        return 'all_teachers' if self.is_centre else 'manual'

    def _ems_presence_vals(self):
        self.ensure_one()
        return {
            'name': self.display_name,
            'date': self.start_datetime,
            'duration': self.duration,
            'space_id': self.space_id.id,
            'course_id': self.course_id.id,
        }

    def _ems_sync_presence(self):
        """Keep the attendance session in step with the minute that asked for it: created when
        the minute chooses the NFC tag, moved with the minute while nobody has opened it, and
        dropped if the minute goes back to a list written by hand before it was ever used.

        With sudo throughout: sessions are managed by the head of studies and the secretariat,
        but any teacher writes minutes, and the session of a minute is that teacher's to run (they
        are its convener, so the meetings page opens its kiosk with their own tag)."""
        for minute in self:
            presence = minute.presence_id.sudo()
            if minute.attendance_mode != 'nfc' or minute.type_kind == 'record':
                if presence and presence.state == 'draft':
                    presence.unlink()
                continue
            if not minute.start_datetime:
                raise UserError(_("Taking attendance with the NFC tag needs the date and time the meeting starts."))
            if minute.duration <= 0:
                raise UserError(_("Taking attendance with the NFC tag needs how long the meeting lasts."))
            if not presence:
                # The people convened are the ones the minute already preloaded from its scope:
                # one list, the minute's, not a second one worked out again by the session.
                minute.presence_id = self.env['ems.meeting.presence'].sudo().create({
                    **minute._ems_presence_vals(),
                    'scope': minute._ems_presence_scope(),
                    'department_id': minute.department_id.id,
                    'workgroup_id': minute.workgroup_id.id,
                    'convener_id': minute.redactor_employee_id.id,
                    'line_ids': [(0, 0, {'employee_id': employee.id}) for employee in minute.attendee_ids],
                })
            elif presence.state == 'draft':
                presence.write(minute._ems_presence_vals())

    def _ems_sync_attendance(self):
        """Fill the minute's lists from what the session recorded: who passed the tag attended,
        everybody else convened did not, and a justified absence says so with its reason."""
        for minute in self.filtered(lambda item: item.attendance_mode == 'nfc' and item.presence_id and item.state != 'approved'):
            lines = minute.presence_id.sudo().line_ids
            present = lines.filtered(lambda line: line.state == 'present')
            justified = lines.filtered(lambda line: line.state == 'justified')
            minute.sudo().write({
                'attendee_ids': [(6, 0, present.employee_id.ids)],
                'absentee_ids': [(6, 0, (lines - present).employee_id.ids)],
                'absence_notes': "; ".join(
                    f"{line.employee_id.name}: {line.notes}" if line.notes else _("%s (justified)", line.employee_id.name)
                    for line in justified) or False,
            })

    def action_open_attendance_kiosk(self):
        """Open the kiosk the attendees pass their tag at, starting the session if it has not."""
        self.ensure_one()
        self.check_access('write')
        presence = self.presence_id.sudo()
        if not presence:
            raise UserError(_("This minute does not take attendance with the NFC tag."))
        if presence.state == 'draft':
            presence.action_open()
        return {'type': 'ir.actions.act_url', 'url': presence.kiosk_url, 'target': 'new'}

    def action_close_attendance(self):
        """Stop taking attendance: whoever has not passed the tag by now was absent."""
        self.ensure_one()
        self.check_access('write')
        presence = self.presence_id.sudo()
        if presence.state == 'open':
            presence.action_close()
        self._ems_sync_attendance()
        return True

    def action_start_meeting(self):
        """From preparing the meeting to holding it: the minute opens for writing."""
        for minute in self:
            if minute.state != 'draft' or minute.type_kind == 'record':
                raise UserError(_("Only a meeting that is still being prepared can be started."))
            minute.state = 'meeting'

    def action_back_to_meeting(self):
        for minute in self:
            if minute.state != 'to_approve':
                raise UserError(_("Only a minute waiting for approval can go back to the meeting."))
            minute.write({'state': 'meeting', 'submission_date': False, 'submitted_by_id': False})

    def action_back_to_draft(self):
        """Back to draft takes back the sending for approval too: the minute is no longer what
        was sent."""
        result = super().action_back_to_draft()
        self.write({'submission_date': False, 'submitted_by_id': False})
        return result

    def action_submit(self):
        self._ems_sync_attendance()
        held = self.filtered(lambda minute: minute.state == 'meeting')
        for minute in held:
            minute._ems_compose_development()
            minute.state = 'to_approve'
        result = super(EmsMinute, self - held).action_submit()
        self.write({'submission_date': fields.Date.context_today(self), 'submitted_by_id': self.env.uid})
        return result

    def _ems_compose_development(self):
        """Put the development of the session together from what was written on each item to
        discuss. Nothing to do for a minute whose development is a text of its own."""
        self.ensure_one()
        development = self.section_value_ids.filtered(lambda value: value.kind == 'development' and not value.is_written)
        items = self.agenda_ids.sorted('sequence')
        if not development or not any(items.mapped('notes')):
            return
        development.content = Markup().join(
            Markup("<h4>%s. %s</h4>%s") % (position, item.name, item.notes or Markup())
            for position, item in enumerate(items, start=1))

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
            # Before anything is written: the check below names who was meant to approve it.
            if not minute._ems_user_may_approve():
                raise UserError(_("Only %s can approve this minute.",
                                  minute.approver_employee_id.name or minute.approver_role_id.name or _("the person who approves it")))
            # Who actually approves it, when that is somebody other than the person it was meant for.
            if employee:
                minute.approver_employee_id = employee
            minute.approval_date = fields.Date.context_today(minute)
        return super().action_approve()

    @api.model
    def _ems_people_label(self, people):
        """Who is responsible, as the minute prints it: their names while they are few, how many
        they are beyond that (a whole department answering for an agreement is said as a number)."""
        return ", ".join(people.mapped('name')) if len(people) <= 3 else _("%s people", len(people))

    def action_open_draft_pdf(self):
        """Show the minute as it stands, before it is approved: the same document the approval
        will file, rendered on the spot and marked as a draft. Nothing is stored."""
        self.ensure_one()
        if self.state == 'approved':
            return self.action_open_pdf()
        return {'type': 'ir.actions.act_url', 'url': f"/report/pdf/ems.report_minute/{self.id}", 'target': 'new'}

    def action_open_previous_pdf(self):
        self.ensure_one()
        return self.previous_minute_id.action_open_pdf()

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


class IrActionsReport(models.Model):
    _inherit = "ir.actions.report"

    def _ems_in_centre_lang(self, report_ref):
        """A minute is the centre's document: printed in the centre's language whoever prints it."""
        if self._get_report(report_ref).report_name == 'ems.report_minute':
            return self.with_context(lang=self.env['ems.minute']._ems_centre_lang())
        return self

    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        return super(IrActionsReport, self._ems_in_centre_lang(report_ref))._render_qweb_pdf(report_ref, res_ids=res_ids, data=data)

    def _render_qweb_html(self, report_ref, docids, data=None):
        return super(IrActionsReport, self._ems_in_centre_lang(report_ref))._render_qweb_html(report_ref, docids, data=data)
