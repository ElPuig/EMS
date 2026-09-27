# -*- coding: utf-8 -*-

import secrets
from collections import Counter
from datetime import timedelta

import psycopg2
from pytz import UTC

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.http import request
from odoo.tools import remove_accents
from odoo.tools.image import image_data_uri

# How long a meeting attendance stays open for tags when nobody says otherwise: a staff meeting.
DEFAULT_DURATION = 2.0

# What the kiosk's lists do to a name to make it shorter: drop the last surname. A name is one
# string here, with nothing saying which words are given names and which surnames, so it is only
# done when it is safe, and in any doubt the whole name stays: a longer name is never a wrong one.
# Words that belong to the surname that follows them ("de la Torre", "Vila i Serra").
_SURNAME_PARTICLES = frozenset((
    'de', 'del', 'della', 'la', 'las', 'los', 'el', 'i', 'y', 'da', 'das', 'do', 'dos', 'di', 'dels',
    'van', 'von', 'der', 'des', 'du', 'le',
))
# The second word of a three-word name that makes it a two-given-names name with a single surname
# ("Josep Manel Cos", "Gerardo Jesús Nicolau"), where dropping the last word would drop the only
# surname. Only names that are not also surnames: "Martín" or "Alonso" are not here, and a name
# that is missing here just stays whole.
_SECOND_GIVEN_NAMES = frozenset((
    'maria', 'mari', 'mar', 'carmen', 'pilar', 'isabel', 'teresa', 'rosa', 'ana', 'anna', 'belen',
    'angeles', 'angels', 'merce', 'montserrat', 'dolors', 'dolores', 'paloma', 'cristina', 'eva',
    'jose', 'josep', 'juan', 'joan', 'jesus', 'manuel', 'manel', 'luis', 'lluis', 'carlos', 'carles',
    'antonio', 'antoni', 'angel', 'francisco', 'francesc', 'javier', 'xavier', 'miguel', 'miquel',
    'pedro', 'pere', 'pablo', 'pau', 'jordi', 'ramon', 'jaume', 'joaquim', 'ricard', 'enric',
    'ignasi', 'vicent', 'vicente', 'rafael', 'lluc', 'marc',
))


def kiosk_short_name(name):
    """`name` without its last surname, for the kiosk's lists, when that can be told apart from a
    name that has just one: 'Ada Alsina Pla' -> 'Ada Alsina', 'Fernando del Olmo Fernández' ->
    'Fernando del Olmo', but 'Olga de la Morena' and 'Gerardo Jesús Nicolau' stay as they are."""
    words = (name or '').split()
    if len(words) < 3:
        return ' '.join(words)
    # The last surname, with the particles that go with it.
    start = len(words) - 1
    while start > 1 and words[start - 1].casefold() in _SURNAME_PARTICLES:
        start -= 1
    kept = words[:start]
    two_given_names = len(words) == 3 and remove_accents(words[1]).casefold() in _SECOND_GIVEN_NAMES
    if len(kept) < 2 or two_given_names:
        return ' '.join(words)
    return ' '.join(kept)


class EmsMeetingPresence(models.Model):
    _name = "ems.meeting.presence"
    _description = "Meeting attendance"
    _inherit = ['ems.base']
    _order = "date desc, id desc"
    _sql_constraints = [
        ('unique_access_token', 'unique (access_token)', "Another meeting attendance already uses this token."),
    ]

    name = fields.Char(string="Meeting", required=True, tracking=True)
    date = fields.Datetime(string="Starts", required=True, default=fields.Datetime.now, tracking=True)
    duration = fields.Float(
        string="Duration",
        required=True,
        default=DEFAULT_DURATION,
        tracking=True,
        help="In hours. The kiosk only takes tags between the start and the end.",
    )
    date_end = fields.Datetime(
        string="Ends",
        required=True,
        compute="_compute_date_end",
        inverse="_inverse_date_end",
        store=True,
        precompute=True,  # required and stored: it has to exist when the row is inserted
        tracking=True,
        help="Set the end or the duration, whichever is easier: each one follows the other.",
    )
    space_id = fields.Many2one(string="Room", comodel_name="ems.space")
    course_id = fields.Many2one(
        string="Course",
        comodel_name="ems.course",
        default=lambda self: self.env['ems.course'].search([('is_current', '=', True)], limit=1),
    )
    company_id = fields.Many2one(string="Company", comodel_name="res.company", required=True, default=lambda self: self.env.company)
    scope = fields.Selection(
        string="Who is convened",
        selection=[
            ('all_teachers', "All teachers"),
            ('all_staff', "All staff"),
            ('department', "A department"),
            ('workgroup', "A workgroup"),
            ('manual', "Chosen by hand"),
        ],
        required=True,
        default='all_teachers',
        help="Who is convened. It only decides who is loaded into the list: people can always be added or removed by hand.",
    )
    department_id = fields.Many2one(string="Department", comodel_name="hr.department")
    workgroup_id = fields.Many2one(string="Workgroup", comodel_name="ems.workgroup")
    state = fields.Selection(
        string="State",
        selection=[('draft', "Draft"), ('open', "Open"), ('closed', "Closed")],
        required=True,
        default='draft',
        copy=False,
        tracking=True,
    )
    access_token = fields.Char(
        string="Kiosk token",
        default=lambda self: secrets.token_urlsafe(24),
        copy=False,
        readonly=True,
        index=True,
        help="The only credential of the kiosk page: whoever has the link can register a scan while the meeting is open.",
    )
    kiosk_url = fields.Char(string="Kiosk link", compute="_compute_kiosk_url")
    kiosk_lang = fields.Selection(
        string="Kiosk language",
        selection="_get_installed_langs",
        required=True,
        default=lambda self: self.env.user.lang or 'en_US',
        help="The language of the kiosk page. Whoever passes the tag is anonymous, so the page cannot follow their own language.",
    )
    line_ids = fields.One2many(string="People", comodel_name="ems.meeting.presence.line", inverse_name="presence_id")

    convened_count = fields.Integer(string="Convened", compute="_compute_counts")
    present_count = fields.Integer(string="Present", compute="_compute_counts")
    pending_count = fields.Integer(string="Pending", compute="_compute_counts")
    justified_count = fields.Integer(string="Justified", compute="_compute_counts")
    absent_count = fields.Integer(string="Absent", compute="_compute_counts")

    @api.model
    def _get_installed_langs(self):
        return self.env['res.lang'].get_installed()

    @api.depends('access_token')
    def _compute_kiosk_url(self):
        # The host the request came in through, not web.base.url: a database restored from
        # production keeps production's, and the kiosk must open on the server the manager is on.
        base_url = request.httprequest.url_root.rstrip('/') if request else self.env['ir.config_parameter'].sudo().get_param('web.base.url', '')
        for presence in self:
            presence.kiosk_url = f"{base_url}/ems/presence/{presence.access_token}" if presence.access_token else False

    @api.depends('date', 'duration')
    def _compute_date_end(self):
        for presence in self:
            presence.date_end = presence.date and presence.date + timedelta(hours=presence.duration)

    def _inverse_date_end(self):
        """The end set by hand becomes the duration. The duration is the stored source of truth, so
        that moving the start moves the whole window instead of stretching the meeting."""
        for presence in self:
            if presence.date and presence.date_end:
                presence.duration = (presence.date_end - presence.date).total_seconds() / 3600

    @api.onchange('date_end')
    def _onchange_date_end(self):
        self._inverse_date_end()

    @api.depends('line_ids.state', 'line_ids.is_convened')
    def _compute_counts(self):
        for presence in self:
            states = presence.line_ids.mapped('state')
            presence.convened_count = len(presence.line_ids.filtered('is_convened'))
            presence.present_count = states.count('present')
            presence.pending_count = states.count('pending')
            presence.justified_count = states.count('justified')
            presence.absent_count = states.count('absent')

    @api.constrains('date', 'date_end', 'duration')
    def _check_ends_after_start(self):
        if any(presence.duration <= 0 for presence in self):
            raise ValidationError(_("The meeting must end after it starts."))

    @api.constrains('scope', 'department_id', 'workgroup_id')
    def _check_scope_target(self):
        for presence in self:
            if presence.scope == 'department' and not presence.department_id:
                raise ValidationError(_("Choose the department to convene."))
            if presence.scope == 'workgroup' and not presence.workgroup_id:
                raise ValidationError(_("Choose the workgroup to convene."))

    @api.model_create_multi
    def create(self, vals_list):
        presences = super().create(vals_list)
        # Whoever creates a meeting expects to see the convened people right away.
        for presence in presences.filtered(lambda item: item.scope != 'manual' and not item.line_ids):
            presence.action_load_convened()
        return presences

    @api.ondelete(at_uninstall=False)
    def _unlink_only_draft(self):
        if any(presence.state != 'draft' for presence in self):
            raise UserError(_("Only a draft meeting attendance can be deleted: archive the others."))

    def _ems_scope_employees(self):
        """The people the scope convenes. Read through hr.employee.public on purpose: the
        secretariat does not imply hr.group_hr_user, so hr.employee itself is out of its reach."""
        self.ensure_one()
        employees = self.env['hr.employee.public']
        domain = [('company_id', '=', self.company_id.id)]
        if self.scope == 'all_teachers':
            return employees.search(domain + [('employee_type', '=', 'teacher')])
        if self.scope == 'all_staff':
            return employees.search(domain)
        if self.scope == 'department':
            return employees.search(domain + [('department_id', 'child_of', self.department_id.id)])
        if self.scope == 'workgroup':
            return self.workgroup_id.employee_ids
        return employees

    def _check_not_closed(self):
        if any(presence.state == 'closed' for presence in self):
            raise UserError(_("This meeting attendance is closed: reopen it to change it."))

    def action_load_convened(self):
        """Add whoever the scope convenes and has no line yet. Only ever adds: a scan already
        made must not be lost because the scope changed afterwards."""
        self._check_not_closed()
        for presence in self:
            missing = presence._ems_scope_employees() - presence.line_ids.employee_id
            if missing:
                presence.line_ids = [(0, 0, {'employee_id': employee.id}) for employee in missing]
        return True

    def action_open(self):
        for presence in self:
            if presence.state != 'draft':
                raise UserError(_("Only a draft meeting attendance can be opened."))
            presence.state = 'open'
        return True

    def action_close(self):
        """Whoever did not pass the tag by now was absent. Done before the state changes: a closed
        session locks its lines."""
        for presence in self:
            if presence.state != 'open':
                raise UserError(_("Only an open meeting attendance can be closed."))
            presence.line_ids.filtered(lambda line: line.state == 'pending').write({'state': 'absent'})
            presence.state = 'closed'
        return True

    def action_reopen(self):
        for presence in self:
            if presence.state != 'closed':
                raise UserError(_("Only a closed meeting attendance can be reopened."))
            presence.state = 'open'
        return True

    def action_open_kiosk(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_url', 'url': self.kiosk_url, 'target': 'new'}

    def _ems_show_code_box(self):
        """Whether the kiosk shows a box for typing a code. It is a testing aid for where there is
        no reader, and only shown outside production: the real kiosk has no box and takes nothing
        that is not typed at a reader's speed, like the clock-in kiosk. Undeclared counts as not
        production (a clean database, CI); deploy.sh always declares it."""
        return self.env['ir.config_parameter'].sudo().get_param('ems.environment_type') != 'production'

    def _ems_kiosk_status(self):
        """What the kiosk page is told about the session itself: 'open', or why it takes no tags.
        Open takes them only between the start and the end, both included: before it the meeting
        has not started, after it the attendance is closed, whatever the session's own state."""
        self.ensure_one()
        status = {'draft': 'not_open', 'open': 'open', 'closed': 'closed'}[self.state]
        if status == 'open':
            now = fields.Datetime.now()
            if now < self.date:
                status = 'not_open'
            elif now > self.date_end:
                status = 'closed'
        return status

    def _ems_local(self, moment):
        """`moment`, a naive UTC datetime as the ORM stores it, in local time (the one of the
        browser or, failing that, of the company: the kiosk's visitor is anonymous)."""
        return self.env['ems.datetime_utils'].utc_datetime_to_local(moment.replace(tzinfo=UTC))

    def _ems_window_label(self):
        """'17:00 - 19:00' in local time (with the dates too when it spans more than a day), for the
        kiosk to say when it takes tags."""
        self.ensure_one()
        start, end = (self._ems_local(moment) for moment in (self.date, self.date_end))
        pattern = '%H:%M' if start.date() == end.date() else '%d/%m %H:%M'
        return f"{start.strftime(pattern)} - {end.strftime(pattern)}"

    def _ems_kiosk_names(self, employees):
        """{employee id: the name the kiosk's lists show} for `employees`: the short one, unless
        somebody else on the company's staff would look exactly the same. Compared with the whole
        staff and not with the people of this meeting, so a name does not change on screen when
        somebody else comes in."""
        self.ensure_one()
        staff = (self.env['hr.employee.public'].search([('company_id', '=', self.company_id.id)]) | employees)
        short = {employee.id: kiosk_short_name(employee.name) for employee in staff}
        seen = Counter(remove_accents(name).casefold() for name in short.values())
        return {
            employee.id: short[employee.id] if seen[remove_accents(short[employee.id]).casefold()] == 1 else employee.name
            for employee in employees
        }

    def _ems_kiosk_progress(self):
        """Who is in and who is still to come, as the kiosk shows it: the two counters and the two
        lists, names only. The lists are what a public page hands to anyone holding the link: it
        gets a name (the short one, see kiosk_short_name), never a photo, an address or anything
        else of the person.

        'convened' are the pending lines, alphabetical (people look for their own name); 'attendees'
        the present ones, the latest arrival first. Someone justified is in neither."""
        self.ensure_one()

        names = self._ems_kiosk_names(self.line_ids.employee_id)

        def name_key(line):
            return remove_accents(names[line.employee_id.id]).casefold()

        pending = self.line_ids.filtered(lambda line: line.state == 'pending').sorted(name_key)
        present = self.line_ids.filtered(lambda line: line.state == 'present').sorted(
            lambda line: (line.checkin_time or fields.Datetime.to_datetime('1970-01-01'), line.id), reverse=True)
        return {
            'present_count': len(present),
            'pending_count': len(pending),
            'convened': [{'id': line.id, 'name': names[line.employee_id.id]} for line in pending],
            'attendees': [{
                'id': line.id,
                'name': names[line.employee_id.id],
                'time': self._ems_local(line.checkin_time).strftime('%H:%M') if line.checkin_time else '',
                'not_convened': not line.is_convened,
            } for line in present],
        }

    def _ems_kiosk_labels(self):
        """Every word the kiosk page shows, translated here (in kiosk_lang, by the caller's context)
        and handed over as a prop: the page is anonymous, so the web client's own translation loading
        does not apply to it."""
        self.ensure_one()
        return {
            'ok': _("Attendance registered"),
            'already': _("Already registered"),
            'not_convened': _("Registered, but not on the convened list"),
            'unknown': _("Unknown tag"),
            'not_open': _("Attendance has not started yet"),
            'closed': _("Attendance is closed"),
            'error': _("The tag could not be registered, try again"),
            'prompt': _("Pass your tag"),
            'type_hint': _("or type its code and press Enter"),
            'convened_people': _("Convened people"),
            'attendees': _("Attendees"),
            'all_in': _("Everyone has registered"),
            'not_convened_note': _("(not convened)"),
        }

    def _ems_register_scan(self, barcode):
        """Register the tag `barcode` was read from. Meant to be called with sudo() from the kiosk
        route, which is anonymous. Returns what the kiosk page shows: a status ('ok', 'already',
        'unknown', 'not_convened', 'not_open' or 'closed'), who it was (when somebody matched) and
        the two counters."""
        self.ensure_one()
        status = self._ems_kiosk_status()
        if status != 'open':
            return {'status': status, **self._ems_kiosk_progress()}
        barcode = (barcode or '').strip()
        employee = self.env['hr.employee'].sudo().search([
            ('barcode', '=', barcode), ('company_id', '=', self.company_id.id),
        ], limit=1) if barcode else self.env['hr.employee']
        if not employee:
            return {'status': 'unknown', **self._ems_kiosk_progress()}

        line = self.line_ids.filtered(lambda item: item.employee_id.id == employee.id)
        status = 'ok'
        if line.state == 'present':
            status = 'already'
        elif line:
            line.with_context(ems_presence_scan=True).write({
                'state': 'present', 'checkin_time': fields.Datetime.now(), 'method': 'nfc',
            })
        else:
            status = self._ems_add_unconvened_scan(employee)
        return {
            'status': status,
            'employee_name': employee.name,
            'employee_avatar': employee.avatar_256 and image_data_uri(employee.avatar_256),
            **self._ems_kiosk_progress(),
        }

    def _ems_add_unconvened_scan(self, employee):
        """Someone who was not convened passed the tag: they are there, so they are added, flagged.
        Two scans arriving together (a double tap) must not both try to create the line."""
        try:
            with self.env.cr.savepoint():
                self.env['ems.meeting.presence.line'].with_context(ems_presence_scan=True).create({
                    'presence_id': self.id,
                    'employee_id': employee.id,
                    'state': 'present',
                    'checkin_time': fields.Datetime.now(),
                    'method': 'nfc',
                    'is_convened': False,
                })
        except psycopg2.IntegrityError:
            return 'already'
        return 'not_convened'
