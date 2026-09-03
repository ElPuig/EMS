# -*- coding: utf-8 -*-

from datetime import timedelta

from markupsafe import Markup

from odoo import _, api, fields, models, Command
from odoo.exceptions import AccessError, ValidationError
from odoo.tools import format_date

# The Apps Script this replaces rounded every partial absence to quarters of an hour; the
# centre's monthly report is still read in those terms.
ROUNDING_MINUTES = 15

# Ordered widest-first: see res.users._ems_restrict_time_off_groups(). 'hr.group_hr_user' is in
# the list because hr_holidays' own officer group implies it, so it is granted (and has to be
# taken back) as collateral of the same install.
NATIVE_LEAVE_TYPE_XMLIDS = (
    'hr_holidays.holiday_status_cl',
    'hr_holidays.holiday_status_sl',
    'hr_holidays.holiday_status_unpaid',
    'hr_holidays.holiday_status_comp',
    'hr_holidays_attendance.holiday_status_extra_hours',
)

RESPONSIBLE_GROUP_XMLID = 'hr_holidays.group_hr_holidays_responsible'

TIME_OFF_GROUP_XMLIDS = (
    'hr_holidays.group_hr_holidays_manager',
    'hr_holidays.group_hr_holidays_user',
    RESPONSIBLE_GROUP_XMLID,
    'hr.group_hr_user',
)


def format_time_float(value):
    """A float hour as HH:MM - what the form itself shows for the start and end times."""
    hours, minutes = divmod(round((value or 0.0) * 60), 60)
    return f"{int(hours):02d}:{int(minutes):02d}"


class EmsAbsenceEmployeeBase(models.AbstractModel):
    # NOTE: a plain single-element '_inherit' with no '_name' extends 'hr.employee.base' in
    # place, so both 'hr.employee' and 'hr.employee.public' pick this up - same pattern as
    # 'ems_employee_base' in employee.py.
    _inherit = ["hr.employee.base"]

    @api.depends('department_id')
    def _compute_leave_manager(self):
        """Replaces hr_holidays' native derivation (parent_id.user_id) with the Area Manager of
        the employee's top-level department - see docs/en/developers/employees/absence.md.

        In EMS 'parent_id' is the Seminar Chief or Department Chief (see '_compute_parent_id' in
        employee.py), who is not who approves an absence: that is always the Deputy Head of
        Studies, the Head of Studies or the Secretary, depending on which area the employee
        belongs to. Those three are exactly the Area Managers of the three top-level departments,
        so the approver is derived from data already maintained by the role hierarchy instead of
        being configured anywhere.

        Like '_compute_parent_id', this depends only on 'department_id' - a recursive walk up
        'parent_id' cannot be expressed as an @api.depends - and is re-triggered explicitly from
        'ems_department._cascade_department_heads()' whenever an Area Manager changes.
        """
        for employee in self:
            manager = employee.department_id._top_level_department().manager_id
            # Compared by id, not by record: this abstract model is shared by 'hr.employee' and
            # 'hr.employee.public', which are different models over the same ids, and Odoo's '=='
            # is False across models. An Area Manager cannot approve their own absence, so they
            # fall back to the Director.
            if manager.id == employee.id:
                manager = employee.company_id.director_id
            employee.leave_manager_id = manager.user_id if manager.id != employee.id else False


class EmsAbsenceLeaveType(models.Model):
    _inherit = "hr.leave.type"

    ems_counts_hours = fields.Boolean(
        string="Adds the hours to the monthly report", default=True,
        help="Absences of this type are added by default to the monthly hours each Area Manager "
             "reports. It stays editable request by request, because employees do miscategorise.")
    ems_counts_health_allowance = fields.Boolean(
        string="Consumes the health allowance", default=False,
        help="Hours of this type count against the employee's yearly self-declared health "
             "absence allowance.")
    ems_full_day_default = fields.Boolean(
        string="Whole day by default", default=False,
        help="Requests of this type start marked as a whole-day absence.")
    ems_needs_atri = fields.Boolean(
        string="Filed through ATRI", default=False,
        help="The employee files this absence on the Generalitat's ATRI portal. Direction "
             "confirms it was really filed as part of their own check.")


    ems_short_name = fields.Char(
        string="Short name", compute="_compute_ems_short_name",
        help="The absence type's name up to its colon - what the original Apps Script showed in "
             "the calendar and in its emails, keeping the full legal wording for the form where "
             "the employee actually has to read it.")

    @api.depends('name')
    def _compute_ems_short_name(self):
        # Not stored: 'name' is translatable, and a stored copy would freeze one language.
        for leave_type in self:
            name = leave_type.name or ''
            leave_type.ems_short_name = name.split(':')[0].strip() if ':' in name else name

    def _ems_deactivate_native_types(self):
        """Archives the absence types Odoo ships with, leaving only the centre's own nine.

        'Paid Time Off', 'Sick Time Off', 'Unpaid', 'Compensatory Days' and (from
        hr_holidays_attendance) 'Extra Hours' are none of the nine options the original request
        form offered, and an employee picking one would land outside the centre's own rules
        entirely.

        This cannot be done from a data file: all five carry ir_model_data.noupdate = True, and
        that stored flag - not the loading file's own context - is what decides whether an
        existing record gets written (see CLAUDE.md's data folder notes). Archiving instead of
        deleting keeps any request that already points at one readable.

        Idempotent. Returns the types it archived.
        """
        native = self.env['hr.leave.type']
        for xmlid in NATIVE_LEAVE_TYPE_XMLIDS:
            native |= self.env.ref(xmlid, raise_if_not_found=False) or self.env['hr.leave.type']
        stale = native.filtered('active')
        stale.active = False
        return stale


class EmsAbsenceLeave(models.Model):
    _inherit = "hr.leave"

    ems_counts_hours = fields.Boolean(
        string="Adds the hours to the monthly report", compute="_compute_ems_counts_hours",
        store=True, readonly=False)
    ems_needs_atri = fields.Boolean(
        string="Filed through ATRI", compute="_compute_ems_needs_atri",
        store=True, readonly=False)
    ems_full_day = fields.Boolean(
        string="Whole day?", compute="_compute_ems_full_day", store=True, readonly=False,
        help="The employee did not come in at all that day. A whole-day absence always counts a "
             "full working day, however many lessons they had scheduled.")
    ems_submitted = fields.Boolean(
        string="Submitted", copy=False,
        help="Set by the \u201cSend request\u201d button once the employee has confirmed their "
             "details. A request cannot be saved without it, which is what stops Odoo's own "
             "autosave from filing an absence nobody asked for.")
    ems_responsible_declaration = fields.Boolean(
        string="Responsible declaration",
        help="I declare, under my own responsibility, that the details and the reason given for "
             "this absence are true.")
    ems_direction_state = fields.Selection(
        string="Direction check",
        selection=[('not_done', 'Not done'), ('missing_doc', 'Missing document'), ('done', 'Done')],
        default='not_done', required=True, copy=False, tracking=True,
        help="Direction's own check of the supporting document and, for ATRI absences, of the "
             "request having really been filed on the portal. Independent of the approval: a "
             "request can be approved and still be waiting for its document.")
    ems_health_hours_used = fields.Float(
        string="Health hours used", compute="_compute_ems_health_allowance",
        help="Hours this employee has already used from their health allowance this course, "
             "this request included.")
    ems_health_allowance_exceeded = fields.Boolean(
        string="Over the health allowance", compute="_compute_ems_health_allowance")

    is_absence_manager = fields.Boolean(
        string="Current user manages this absence", compute="_compute_is_absence_manager",
        help="Whether the user reading this request is the one who approves it, or an officer. "
             "Drives which fields stay editable once the request has been approved.")

    # "To Approve" reads as an instruction to whoever is looking at it; from the employee's own
    # list it is simply the state their request is in. The spreadsheet this replaces called it
    # "Pendent", and so does everyone at the centre. selection_add replaces the label of an
    # existing value (fields.py merges values_add over the inherited ones), which keeps the rest
    # of the states in Odoo's hands.
    state = fields.Selection(selection_add=[('confirm', 'Pending')])

    ems_course_id = fields.Many2one(
        string="Course", comodel_name="ems.course", compute="_compute_ems_course_id", store=True,
        help="The school year the absence falls in, September to August. Stored so reports can "
             "filter and group on it - a calendar year cuts a school year in half.")
    ems_health_hours = fields.Float(
        string="Health hours", compute="_compute_ems_health_hours", store=True,
        help="This absence's hours when it consumes the health allowance, zero otherwise. A "
             "column of its own so a report grouped by employee can total it - which is the "
             "figure that has to stay under the yearly allowance.")

    @api.depends('request_date_from')
    def _compute_ems_course_id(self):
        # Courses are few and change once a year; read them once for the whole batch rather than
        # per record. A course created later does not retro-assign old absences, which is fine:
        # they already carry the course they were filed in.
        windows = [(course, *course.date_range())
                   for course in self.env['ems.course'].search([])]
        for leave in self:
            day = leave.request_date_from
            leave.ems_course_id = next(
                (course for course, start, end in windows if day and start <= day <= end),
                self.env['ems.course'])

    ems_counted_hours = fields.Float(
        string="Reported hours", compute="_compute_ems_counted_hours", store=True,
        help="This absence's hours when it is marked as adding to the monthly report, zero "
             "otherwise. Summable, so the monthly report can total it per month the way the "
             "spreadsheet's own 'Totals per mes' tab did.")

    @api.depends('number_of_hours', 'ems_counts_hours')
    def _compute_ems_counted_hours(self):
        for leave in self:
            leave.ems_counted_hours = leave.number_of_hours if leave.ems_counts_hours else 0.0

    @api.depends('number_of_hours', 'holiday_status_id.ems_counts_health_allowance')
    def _compute_ems_health_hours(self):
        for leave in self:
            leave.ems_health_hours = (
                leave.number_of_hours if leave.holiday_status_id.ems_counts_health_allowance else 0.0)

    ems_type_short_name = fields.Char(
        string="Absence type", related="holiday_status_id.ems_short_name")

    @api.depends(
        'tz', 'date_from', 'date_to', 'employee_id',
        'holiday_status_id', 'number_of_hours',
        'leave_type_request_unit', 'number_of_days', 'department_id',
        'holiday_status_id.ems_short_name',
    )
    @api.depends_context('short_name', 'hide_employee_name', 'groupby')
    def _compute_display_name(self):
        """Shortens the absence type wherever Odoo puts a leave's name - the calendar chip above
        all - without touching the type's own display_name, which the request form's radio list
        needs in full so the employee can read the declaration they are choosing.

        Post-processing super()'s result rather than reimplementing it: that method has five
        branches and knows about timezones, grouping and the 'short_name' context, none of which
        this needs to care about. Both strings come from the same record in the same language, so
        the replacement is exact.
        """
        super()._compute_display_name()
        for leave in self:
            long_name = leave.holiday_status_id.name
            short_name = leave.holiday_status_id.ems_short_name
            if long_name and short_name and short_name != long_name and leave.display_name:
                leave.display_name = leave.display_name.replace(long_name, short_name)

    is_absence_direction = fields.Boolean(
        string="Current user is Direction", compute="_compute_is_absence_manager",
        help="Whether the user reading this request may set the Direction check.")

    @api.depends_context('uid')
    def _compute_is_absence_manager(self):
        """The employee picks their own absence type and gets it wrong often enough that the
        manager has to be able to correct it afterwards - which Odoo's own readonly, keyed only
        on the approval state, would prevent."""
        is_officer = self.env.user.has_group('hr_holidays.group_hr_holidays_user')
        is_direction = self._ems_can_set_direction_state()
        for leave in self:
            leave.is_absence_manager = is_officer or leave.employee_id.leave_manager_id == self.env.user
            leave.is_absence_direction = is_direction

    @api.model
    def default_get(self, fields_list):
        """No absence type is preselected on a new request.

        Odoo ticks the first available one (its own default_get, further up this MRO), which on
        this form means a legal declaration the employee never chose is selected the moment the
        screen opens. 'holiday_status_display_name' is hr_holidays' own switch for that block,
        so this turns it off rather than picking the default apart afterwards.
        """
        return super(EmsAbsenceLeave, self.with_context(
            holiday_status_display_name=False)).default_get(fields_list)

    # One compute per field, deliberately, even though all three read the same source: Odoo
    # skips a compute method entirely for a record whose create() vals mention any one of the
    # fields it assigns. Sharing a method would mean that creating a request with 'ems_full_day'
    # set - an import, an API client, the guard-duty automation - silently left
    # 'ems_counts_hours' false, quietly dropping the absence out of the monthly report.
    #
    # All three are stored editable computes: picking a type proposes a value and any later
    # manual change survives, exactly as the Apps Script did when it ticked 'Suma Hores?' on
    # submit and left the manager free to correct it.
    @api.depends('holiday_status_id')
    def _compute_ems_counts_hours(self):
        for leave in self:
            leave.ems_counts_hours = leave.holiday_status_id.ems_counts_hours

    @api.depends('holiday_status_id')
    def _compute_ems_needs_atri(self):
        for leave in self:
            leave.ems_needs_atri = leave.holiday_status_id.ems_needs_atri

    @api.depends('holiday_status_id')
    def _compute_ems_full_day(self):
        for leave in self:
            leave.ems_full_day = leave.holiday_status_id.ems_full_day_default

    @api.depends('holiday_status_id', 'request_unit_half', 'ems_full_day')
    def _compute_request_unit_hours(self):
        super()._compute_request_unit_hours()
        for leave in self:
            if leave.leave_type_request_unit == 'hour' and not leave.request_unit_half:
                leave.request_unit_hours = not leave.ems_full_day

    @api.onchange('request_date_from', 'ems_full_day')
    def _onchange_ems_full_day_dates(self):
        """A whole-day absence is usually a single day, so the end date follows the start until
        the employee says otherwise - they only have to touch it to ask for several days."""
        for leave in self:
            if leave.ems_full_day and leave.request_date_from and (
                    not leave.request_date_to or leave.request_date_to < leave.request_date_from):
                leave.request_date_to = leave.request_date_from

    @api.depends(
        'date_from', 'date_to', 'resource_calendar_id', 'holiday_status_id.request_unit',
        'ems_full_day', 'request_date_from', 'request_date_to')
    def _compute_duration(self):
        # Re-declared in full: @api.depends does not accumulate across an override, and the
        # centre's rule adds three dependencies the native compute does not have.
        return super()._compute_duration()

    def _get_durations(self, check_leave_type=True, resource_calendar=None):
        """Replaces Odoo's duration with the centre's own rule.

        The native computation counts the hours the employee was actually scheduled to work, so
        a teacher with a single lesson that day would be credited one hour for missing the whole
        day. The centre counts the opposite way (see docs/en/developers/employees/absence.md):

        1. Whole-day or multi-day absence -> a full working day per working day in the range,
           regardless of the timetable.
        2. Partial absence -> the real clock time missed, rounded to 15-minute steps.

        Hooked here rather than in '_compute_duration' because this is the method hr_holidays
        itself factored out to be hooked - see its own docstring.
        """
        durations = super()._get_durations(check_leave_type=check_leave_type, resource_calendar=resource_calendar)
        full_day_hours = self.env.company._ems_full_day_hours()
        for leave in self:
            hours = leave._ems_absence_hours(full_day_hours)
            if hours is None or leave.id not in durations:
                continue
            durations[leave.id] = (hours / full_day_hours, hours)
        return durations

    def _ems_absence_hours(self, full_day_hours):
        """Hours this absence is worth, or None when it cannot be determined yet."""
        self.ensure_one()
        date_from, date_to = self.request_date_from, self.request_date_to
        if not date_from or not date_to:
            return None
        if self.ems_full_day or date_from != date_to:
            return full_day_hours * self._ems_working_days(date_from, date_to)
        if not self.date_from or not self.date_to:
            return None
        minutes = (self.date_to - self.date_from).total_seconds() / 60
        return round(minutes / ROUNDING_MINUTES) * ROUNDING_MINUTES / 60

    @staticmethod
    def _ems_working_days(date_from, date_to):
        """Monday-to-Friday days in the inclusive range. The centre works Mon-Fri, the same
        weekday set every schedule-driven EMS feature already assumes (see WEEKDAYS in
        models/employees/employee.py). Public holidays are not deducted."""
        return sum(
            1 for offset in range((date_to - date_from).days + 1)
            if (date_from + timedelta(days=offset)).weekday() < 5
        )

    @api.depends('employee_id', 'holiday_status_id', 'number_of_hours', 'state')
    def _compute_ems_health_allowance(self):
        """Hours consumed from the health allowance over the current course, this request
        included. Not stored: it depends on every other request of the same employee, so a
        stored value would go stale whenever a sibling request changes."""
        company = self.env.company
        allowance = company._ems_health_allowance_hours()
        window = company.current_course_id.date_range()
        for leave in self:
            used = 0.0
            if window and leave.employee_id and leave.holiday_status_id.ems_counts_health_allowance:
                domain = [
                    ('employee_id', '=', leave.employee_id.id),
                    ('holiday_status_id.ems_counts_health_allowance', '=', True),
                    ('state', '!=', 'refuse'),
                    ('request_date_from', '>=', window[0]),
                    ('request_date_from', '<=', window[1]),
                ]
                if isinstance(leave.id, int):
                    domain.append(('id', '!=', leave.id))
                used = sum(leave.search(domain).mapped('number_of_hours')) + leave.number_of_hours
            leave.ems_health_hours_used = used
            leave.ems_health_allowance_exceeded = used > allowance

    def _ems_can_set_direction_state(self):
        return self.env.su or self.env.user.has_group('ems.group_director')

    @api.model_create_multi
    def create(self, vals_list):
        # The column is readable by everyone now that it shows in every absence list, so the
        # barrier has to be a real one rather than the view hiding the field.
        if not self._ems_can_set_direction_state():
            for vals in vals_list:
                vals.pop('ems_direction_state', None)
        return super().create(vals_list)

    def write(self, vals):
        if 'ems_direction_state' in vals and not self._ems_can_set_direction_state():
            raise AccessError(_("Only Direction can change the Direction check on an absence."))
        return super().write(vals)

    # --- Who gets told ----------------------------------------------------------------------

    def _ems_notify_partners(self):
        """The people the centre wants informed about an absence, beyond the employee and the
        approver Odoo already handles.

        The Google form asked every employee which department they belonged to for exactly one
        reason: to look up who to copy, the 'Informat d'absencies' rows of its Config tab. EMS
        already knows the employee's own department chief, so the question disappeared from the
        form and the answer is derived here instead.

        The chief is informed, not given access: 'hr.leave.private_name' still masks the written
        reason for anyone who is not the employee, their approver or an officer, so they learn
        that a colleague is away and of what kind - which is what covering the department needs -
        without the reason behind it.
        """
        partners = self.env['res.partner']
        for leave in self:
            chief = leave.employee_id.department_id.manager_id
            if chief and chief != leave.employee_id:
                partners |= chief.user_id.partner_id or chief.work_contact_id
        return partners

    def _ems_inform_department_chief(self):
        for leave in self:
            partners = leave._ems_notify_partners()
            if partners:
                # Subscribed just before the state change, so the summary below is the first
                # thing they receive - they are told the outcome, not every draft.
                leave.message_subscribe(partner_ids=partners.ids)

    def _ems_post_outcome(self):
        """A summary of what was decided, for everyone following the request.

        Odoo's own notification is a single line and the tracking entry is just
        'Status: Pending → Approved', which tells a department chief nothing they can act on.
        This spells out who, what and when.

        The written reason is deliberately absent: a chief is informed that a colleague is away
        and of what kind, not why - the same line 'hr.leave.private_name' draws in the interface.
        """
        for leave in self:
            when = format_date(self.env, leave.request_date_from)
            if leave.request_date_to and leave.request_date_to != leave.request_date_from:
                when = _("%(start)s to %(end)s", start=when, end=format_date(self.env, leave.request_date_to))
            elif not leave.ems_full_day:
                when = _("%(date)s, from %(start)s to %(end)s", date=when,
                         start=format_time_float(leave.request_hour_from),
                         end=format_time_float(leave.request_hour_to))
            # Called on the mixin rather than inherited: 'ems.base' would also add its own
            # fields to hr.leave, 'active' among them. This is the shared escaping-safe
            # list builder (see EmsBase.build_html_list), not a hand-rolled copy of it.
            details = self.env['ems.base'].build_html_list([
                _("Employee: %(name)s", name=leave.employee_id.display_name),
                _("Absence type: %(type)s", type=leave.holiday_status_id.display_name),
                _("Dates: %(when)s", when=when),
                _("Duration: %(hours).2f h", hours=leave.number_of_hours),
                _("Status: %(state)s", state=dict(
                    leave._fields['state']._description_selection(leave.env))[leave.state]),
            ])
            leave.message_post(
                body=Markup("<p>%s</p>%s") % (
                    _("Absence request of %(name)s", name=leave.employee_id.display_name), details),
                subtype_xmlid='mail.mt_comment')

    def _validate_leave_request(self):
        """Suppresses Odoo's own one-line note, because '_ems_post_outcome' replaces it.

        The native note reads "Your <absence type> planned on <date> has been accepted" with the
        type's full legal wording dropped mid-sentence, and says nothing else. It cannot be
        reworded through translation: `_()` resolves against the module the string is emitted
        from, so an entry in EMS's own catalogue is never consulted for a sentence hr_holidays
        prints. Overriding the whole method instead would mean copying its calendar-meeting
        logic, which is the part actually worth not duplicating - so only the message is stopped,
        and only for the duration of this one call.
        """
        return super(EmsAbsenceLeave, self.with_context(
            ems_suppress_leave_note=True))._validate_leave_request()

    def message_post(self, **kwargs):
        if self.env.context.get('ems_suppress_leave_note'):
            return self.env['mail.message']
        return super().message_post(**kwargs)

    def action_approve(self, check_state=True):
        self._ems_inform_department_chief()
        result = super().action_approve(check_state=check_state)
        self._ems_post_outcome()
        return result

    def action_refuse(self):
        self._ems_inform_department_chief()
        result = super().action_refuse()
        self._ems_post_outcome()
        return result

    @api.constrains('ems_submitted', 'ems_responsible_declaration')
    def _check_ems_submitted(self):
        """Two conditions, neither of which can live in the view alone.

        Odoo saves a form by itself after a while, even one nobody typed into: a teacher who
        merely opened the request screen to look at it would end up with a real absence on
        record. 'ems_submitted' is only ever set by the "Send request" button, so requiring it
        here is what makes that button the only way in - a far smaller change than fighting the
        web client's own save behaviour.

        The responsible declaration is required for every absence type: it is the employee
        asserting that the reason they gave is true, not a formality attached to some of them.
        """
        for leave in self:
            if not leave.ems_submitted:
                raise ValidationError(_(
                    "This absence request has not been sent. Fill it in and use the "
                    "\u201cSend request\u201d button at the bottom of the form; to leave without "
                    "requesting anything, discard it instead."))
            if not leave.ems_responsible_declaration:
                raise ValidationError(_(
                    "The responsible declaration has to be accepted before an absence request "
                    "can be sent."))

    @api.onchange('holiday_status_id', 'request_date_from', 'request_date_to', 'ems_full_day',
                  'request_hour_from', 'request_hour_to')
    def _onchange_ems_health_allowance(self):
        """Warns the employee, never blocks: going over the allowance is the centre's problem to
        resolve with the employee, not something the software decides."""
        if not self.ems_health_allowance_exceeded:
            return None
        return {'warning': {
            'title': _("Health absence allowance"),
            'message': _(
                "This request takes %(name)s to %(used).2f hours of self-declared health "
                "absence this course, over the %(allowance).2f hours allowed. It can still be "
                "submitted, but it will be flagged for the Head of Studies.",
                name=self.employee_id.display_name,
                used=self.ems_health_hours_used,
                allowance=self.env.company._ems_health_allowance_hours()),
        }}


class EmsAbsenceUsers(models.Model):
    _inherit = "res.users"

    def _ems_sync_time_off_groups(self):
        """Revokes the Time Off groups from users who have no business holding them.

        Installing hr_holidays grants its Administrator group to 'base.default_user', the
        template every new user is copied from, and Odoo propagates that to the existing users
        at install time. On this centre's database that handed all 37 internal users
        'group_hr_holidays_manager' plus, by implication, 'group_hr_holidays_user' and
        'hr.group_hr_user' - so every teacher could read every colleague's absence reason and
        supporting document, which is exactly what the confidentiality rule forbids (see
        docs/en/developers/employees/absence.md), and every employee record besides.

        The rule applied is Odoo's own implication semantics rather than a hardcoded list: a
        user keeps one of these groups only if they hold some *other* group that transitively
        implies it - which, after security/groups.xml, means the Head of Studies chain.

        The one group that cannot come from a chain is 'group_hr_holidays_responsible', the one
        that lets somebody approve. Who approves is not a role anybody holds: it is whoever is
        named as an employee's 'leave_manager_id' (the Area Manager of a top-level department,
        see _compute_leave_manager). Notably that is *not* the whole Secretary group - only the
        ASP area's own manager - so this grants it from that relation instead, which keeps it
        exact and self-maintaining as Area Managers change.

        Idempotent, and safe to run at any time. Returns {xmlid: [login, ...]} of what it
        revoked, so a migration can log it.
        """
        protected = self.env.ref('base.user_root') | self.env.ref('base.user_admin')
        revoked = {}
        # Widest first: revoking 'manager' before 'user' means a user who legitimately keeps
        # 'manager' is still recognised as entitled to 'user' on the next iteration.
        for xmlid in TIME_OFF_GROUP_XMLIDS:
            group = self.env.ref(xmlid)
            implying = self.env['res.groups'].search([]).filtered(
                lambda candidate: candidate != group and group in candidate.trans_implied_ids)
            entitled = implying.users | protected
            if xmlid == RESPONSIBLE_GROUP_XMLID:
                approvers = self.env['hr.employee'].sudo().search(
                    [('leave_manager_id', '!=', False)]).leave_manager_id
                missing = approvers - group.users
                if missing:
                    group.sudo().write({'users': [Command.link(user.id) for user in missing]})
                entitled |= approvers
            surplus = group.users - entitled
            if surplus:
                group.sudo().write({'users': [Command.unlink(user.id) for user in surplus]})
                revoked[xmlid] = surplus.mapped('login')
        return revoked
