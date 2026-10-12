# -*- coding: utf-8 -*-

from datetime import timedelta
from urllib.parse import urlencode

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import format_date

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
        # Read in the source language whoever is asking: a department's name is translated, and
        # its minutes must share one numbering whatever language each writer works in.
        record = (self.department_id or self.workgroup_id).with_context(lang='en_US')
        if record:
            return ''.join(word[0] for word in record.name.split() if word)[:4].upper()
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
        pending = previous.pending_topic_ids.filtered(lambda topic: not topic.is_done)
        # Whatever an earlier choice of scope had carried over goes first: changing the department
        # in the form must not leave the other department's topics behind.
        self.pending_topic_ids -= self.pending_topic_ids.filtered('carried_from_minute_id')
        self.pending_topic_ids = [(0, 0, {
            'name': topic.name,
            'carried_from_minute_id': previous.id,
        }) for topic in pending]

    # --- Call to the meeting ---------------------------------------------------------------------

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
        """Who calls the meeting: the person holding, in this minute's own scope, the post that
        approves it - the department's chief for a department minute, not whoever happens to be
        writing it. Falls back to the writer when the post has no single holder to name."""
        self.ensure_one()
        role = self.approver_role_id
        department = self.department_id.sudo()
        holder = self.env['hr.employee']
        if role == self.env.ref('ems.role_dchieff', raise_if_not_found=False):
            holder = department.manager_id
        elif role == self.env.ref('ems.role_seminar', raise_if_not_found=False):
            holder = department.seminar_chief_id
        elif role == self.env.ref('ems.role_tutor', raise_if_not_found=False):
            holder = self.group_id.sudo().tutor_id
        elif role == self.env.ref('ems.role_director', raise_if_not_found=False):
            holder = self.env.company.sudo().director_id
        elif role:
            holders = self.env['hr.employee.public'].search([('role_ids', 'in', role.ids)], limit=2)
            holder = holders if len(holders) == 1 else holder
        return self.env['hr.employee.public'].browse(holder.id) if holder else (
            self.redactor_employee_id or self.env['hr.employee.public'].search([('user_id', '=', self.env.uid)], limit=1))

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

    def action_submit(self):
        self._ems_sync_attendance()
        return super().action_submit()

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
