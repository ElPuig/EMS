# -*- coding: utf-8 -*-

from datetime import timedelta

from markupsafe import Markup

from odoo import _, api, fields, models, Command
from odoo.exceptions import AccessError, UserError, ValidationError
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

# What hr_holidays' own write() exempts from every restriction it puts on a request that is
# already approved or already started, and therefore all that security/rules/attendance.xml's
# 'rule_absence_own_request_write' is meant to open up.
ATTACHMENT_FIELDS = frozenset({
    'attachment_ids', 'supported_attachment_ids', 'message_main_attachment_id',
})

# The Catalan hr_holidays ships for its two approval activity types is machine-generated
# nonsense, and it is the heading the chatter prints above every request awaiting a decision.
# See mail.activity.type._ems_fix_approval_activity_names().
APPROVAL_ACTIVITY_CA_NAMES = {
    'hr_holidays.mail_act_leave_approval': "Aprovació d'absències",
    'hr_holidays.mail_act_leave_second_approval': "Segona aprovació d'absències",
}

RESPONSIBLE_GROUP_XMLID = 'hr_holidays.group_hr_holidays_responsible'

# Where the Head's side of a request stands once they have acknowledged it, while its supporting
# document is still outstanding. Any other document state means the Head is done with it.
HEAD_STATE_BY_DOCUMENT = {'awaiting': 'pending_document', 'submitted': 'pending_validation'}

# The one activity each stage waits on, and whose it is - see _ems_update_activities().
ACTIVITY_BY_STATUS = {
    'pending_document': 'ems.mail_activity_absence_document_upload',
    'pending_validation': 'ems.mail_activity_absence_document_validate',
    'pending_direction': 'ems.mail_activity_absence_direction_review',
}
OVERDUE_ACTIVITY_XMLID = 'ems.mail_activity_absence_document_overdue'

TIME_OFF_GROUP_XMLIDS = (
    'hr.group_hr_manager',
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


class EmsAbsenceActivityType(models.Model):
    _inherit = "mail.activity.type"

    def _ems_fix_approval_activity_names(self):
        """Repairs Odoo's Catalan translation of the two Time Off approval activity types.

        Odoo ships "Temps de desaprovació" for "Time Off Approval" and "Temps d'apagada de la
        segona aproximació" for "Time Off Second Approve" - machine translations that mean
        nothing in Catalan ("apagada" is a power cut, "aproximació" an estimate). It is not a
        detail buried in a settings screen: it is the line the chatter prints at the top of every
        request awaiting a decision, so it is the first thing the employee who just filed one
        reads. The Spanish translations are correct and are left alone.

        This cannot be a .po entry, even though a .po reference may perfectly well name a record
        another module owns: both records carry ir_model_data.noupdate = True, and
        TranslationImporter.save() only overwrites an existing translation on such a record when
        called with force_overwrite, which no module load ever passes. Same reason
        _ems_deactivate_native_types() has to be code rather than a data file.

        No-op when Catalan is not installed. Idempotent. Returns the types it corrected.
        """
        fixed = self.browse()
        if not self.env['res.lang'].search_count([('code', '=', 'ca_ES'), ('active', '=', True)]):
            return fixed
        for xmlid, name in APPROVAL_ACTIVITY_CA_NAMES.items():
            activity_type = self.env.ref(xmlid, raise_if_not_found=False)
            if not activity_type:
                continue
            catalan = activity_type.sudo().with_context(lang='ca_ES')
            if catalan.name != name:
                catalan.name = name
                fixed |= activity_type
        return fixed


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
        string="Direction status",
        selection=[('not_done', 'Pending'), ('done', 'Done'), ('refused', 'Refused')],
        default='not_done', required=True, copy=False, tracking=True,
        help="Direction's own approval, the last step: once the Head has validated the request "
             "and its supporting document, Direction checks it too (for ATRI absences, that it "
             "was really filed on the portal). Refusing it refuses the whole request.")
    ems_document_state = fields.Selection(
        string="Supporting document status",
        selection=[
            ('not_required', 'Not required'),
            ('awaiting', 'Awaiting documentation'),
            ('submitted', 'Pending validation'),
            ('validated', 'Validated'),
        ],
        copy=False, tracking=True, readonly=True,
        help="Set when the Head acknowledges the request: absence types that require a "
             "supporting document wait for it, and attaching it sends the request back to the "
             "Head for validation.")
    ems_document_reminder_date = fields.Date(
        string="Last document reminder", copy=False, readonly=True,
        help="The last day the employee was reminded that the supporting document is missing.")
    ems_document_escalated = fields.Boolean(
        string="Missing document reported to the Head", copy=False, readonly=True)
    ems_head_state = fields.Selection(
        string="Head status",
        selection=[
            ('pending', 'Pending'),
            ('pending_document', 'Awaiting documentation'),
            ('pending_validation', 'Pending validation'),
            ('approved', 'Approved'),
            ('refused', 'Refused'),
        ],
        compute="_compute_ems_head_state", store=True, copy=False,
        help="The Head's side of the request: the Area Manager who approves this employee's "
             "absences acknowledges it, waits for the supporting document when its type "
             "requires one, and validates it.")
    ems_status = fields.Selection(
        string="Overall status",
        selection=[
            ('pending', 'Pending'),
            ('pending_document', 'Awaiting documentation'),
            ('pending_validation', 'Pending validation'),
            ('pending_direction', 'Pending Direction'),
            ('approved', 'Approved'),
            ('refused', 'Refused'),
            ('cancel', 'Cancelled'),
        ],
        compute="_compute_ems_status", store=True, copy=False,
        help="Where the request stands: the Head acknowledges it, the employee attaches the "
             "supporting document when its type requires one, the Head validates it and "
             "Direction validates it last. The absence takes effect (calendar, hour balance, "
             "guard duty board) as soon as the Head acknowledges it.")
    ems_health_hours_used = fields.Float(
        string="Health hours used", compute="_compute_ems_health_allowance",
        help="Hours this employee has already used from their health allowance this course, "
             "this request included.")
    ems_health_allowance_exceeded = fields.Boolean(
        string="Over the health allowance", compute="_compute_ems_health_allowance")

    is_absence_head = fields.Boolean(
        string="Current user is the Head", compute="_compute_is_absence_manager",
        help="Whether the user reading this request acts as its Head: the employee's approver, "
             "or an officer other than Direction.")
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

    @api.depends('state', 'ems_document_state')
    def _compute_ems_head_state(self):
        """Odoo's own state is the Head's acknowledgement, and the supporting document's state
        is how far they still are from validating it - with two exceptions Odoo's state cannot
        tell apart on its own, where the column keeps whatever the Head had decided before: a
        refusal that was Direction's ('ems_direction_state' is already 'refused' by the time the
        state changes, see action_ems_direction_refuse), and the employee cancelling their own
        request.

        Deliberately not depending on 'ems_direction_state': the Head's column must not move
        when only Direction acts. A request approved with no document state at all (created
        directly as approved) counts as validated."""
        for leave in self:
            if leave.state in ('validate', 'validate1'):
                leave.ems_head_state = HEAD_STATE_BY_DOCUMENT.get(leave.ems_document_state, 'approved')
            elif leave.state == 'refuse' and leave.ems_direction_state != 'refused':
                leave.ems_head_state = 'refused'
            elif leave.state == 'confirm' or not leave.ems_head_state:
                leave.ems_head_state = 'pending'

    @api.depends('state', 'ems_head_state', 'ems_direction_state')
    def _compute_ems_status(self):
        for leave in self:
            if leave.state in ('refuse', 'cancel'):
                leave.ems_status = 'refused' if leave.state == 'refuse' else 'cancel'
            elif leave.ems_head_state == 'approved':
                leave.ems_status = 'approved' if leave.ems_direction_state == 'done' else 'pending_direction'
            elif leave.ems_head_state in ('pending_document', 'pending_validation'):
                leave.ems_status = leave.ems_head_state
            else:
                leave.ems_status = 'pending'

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
        is_director = self.env.user.has_group('ems.group_director')
        for leave in self:
            is_approver = leave.employee_id.leave_manager_id == self.env.user
            leave.is_absence_manager = is_officer or is_approver
            # The same line _compute_can_approve draws: Direction is the Head only of the Area
            # Managers' own absences.
            leave.is_absence_head = is_approver or (is_officer and not is_director)
            leave.is_absence_direction = is_direction

    def _compute_can_approve(self):
        """Direction does not approve on the Head's behalf.

        Direction holds the officer group through Head of Studies, so Odoo would offer it the
        Approve and Refuse buttons on every request - right beside the Head's column, where
        clicking them decides for the Head instead of recording Direction's own review, which
        has its own buttons. They stay only where Direction really is the approver: an Area
        Manager's own absence (see _compute_leave_manager). The server-side rights are left
        alone; this is what the screens offer."""
        super()._compute_can_approve()
        if self.env.su or not self.env.user.has_group('ems.group_director'):
            return
        for leave in self:
            if leave.employee_id.leave_manager_id != self.env.user:
                leave.can_approve = False

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
        the employee says otherwise - they only have to touch it to ask for several days.

        Unconditional once the two guard conditions hold, deliberately not also checking
        whether 'request_date_to' already looks "set" or "later": this onchange only ever fires
        from a 'request_date_from'/'ems_full_day' change (see the decorator), never from editing
        'request_date_to' itself, so there is no risk of clobbering a deliberate multi-day
        choice - that edit happens afterwards, on a field this onchange never re-triggers on.
        A previous version tried to detect "already deliberately set" via 'not to or to < from',
        which broke for a past 'request_date_from' (a retroactively-filed absence, common for
        sick/health leave): native hr_holidays' own default_get() seeds a brand-new request's
        'request_date_to' at today regardless of what 'request_date_from' becomes, so 'to' (today)
        was never "less than" a 'from' set to a past date, and the stale today's-date default
        silently survived instead of collapsing to the single day requested (found 2026-09-09,
        via a genuinely clean install - test_whole_day_copies_the_start_date_to_the_end_date only
        exercises this onchange directly, every other test builds the record via create() with
        both dates given explicitly, which is why this went unnoticed until now)."""
        for leave in self:
            if leave.ems_full_day and leave.request_date_from:
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
        # Only ever set by the Head's own steps, never filed with the request.
        if not self.env.su:
            for vals in vals_list:
                vals.pop('ems_document_state', None)
        leaves = super().create(vals_list)
        leaves._ems_announce_request()
        return leaves

    def write(self, vals):
        if 'ems_direction_state' in vals and not self._ems_can_set_direction_state():
            raise AccessError(_("Only Direction can change the Direction check on an absence."))
        if 'ems_document_state' in vals and not self.env.su and not all(
                leave.is_absence_head or leave.is_absence_direction for leave in self):
            raise AccessError(_("Only the Head or Direction can change the supporting document "
                                "status of an absence."))
        self._ems_check_own_approved_write(vals)
        result = super().write(vals)
        if vals.keys() & ATTACHMENT_FIELDS:
            self._ems_submit_document()
        if vals.keys() & {'state', 'ems_document_state', 'ems_direction_state'}:
            self._ems_update_activities()
        return result

    def _ems_check_own_approved_write(self, vals):
        """The field-level half of 'rule_absence_own_request_write'.

        That rule lets an employee write their own request whatever its state, because the
        justification is filed after the fact far more often than not. An ir.rule cannot name
        fields, so it necessarily opens the whole record - and this closes it back down to the
        attachments, which is all it was widened for. Everything else about an approved request
        stays the approver's to change, exactly as before.

        Applied to officers too, and only to their *own* request. Odoo's own officer rule
        (hr_leave_rule_officer_update) carries the same carve-out - '("employee_id.user_id", "=",
        user.id), ("state", "!=", "validate")' - so without this an officer would have gained,
        through the wider rule above, an ability they never had: editing their own approved
        absence. Somebody else's stays theirs to correct, which is the whole point of being an
        officer.
        """
        if self.env.su or not (vals.keys() - ATTACHMENT_FIELDS):
            return
        employee = self.env.user.employee_id
        blocked = self.filtered(
            lambda leave: leave.state in ('validate', 'validate1') and leave.employee_id == employee)
        if blocked:
            raise AccessError(_(
                "An approved absence request can no longer be changed. Its supporting document "
                "can still be filed; anything else has to go through whoever approved it."))

    # --- Who gets told ----------------------------------------------------------------------

    def _ems_notify_partners(self):
        """The people the centre wants informed about an absence, beyond the employee and the
        approver Odoo already handles: the chiefs of the employee's own department, its
        Department Chief and, when it has one, its Seminar Chief.

        The Google form asked every employee which department they belonged to for exactly one
        reason: to look up who to copy, the 'Informat d'absencies' rows of its Config tab. EMS
        already knows the employee's own chiefs, so the question disappeared from the form and
        the answer is derived here instead.

        A chief is informed, not given access: 'hr.leave.private_name' still masks the written
        reason for anyone who is not the employee, their approver or an officer, so they learn
        that a colleague is away and of what kind - which is what covering the department needs -
        without the reason behind it.
        """
        partners = self.env['res.partner']
        for leave in self:
            department = leave.employee_id.department_id
            for chief in (department.manager_id | department.seminar_chief_id) - leave.employee_id:
                partners |= chief.user_id.partner_id or chief.work_contact_id
        return partners

    def _ems_direction_partners(self):
        """Direction, told of every approval: its own review of the supporting document starts
        there. Not when Direction is the absent employee or is itself approving."""
        partners = self.env['res.partner']
        for leave in self:
            director = leave.employee_id.company_id.director_id or self.env.company.director_id
            if not director or director == leave.employee_id or director.user_id == self.env.user:
                continue
            partners |= director.user_id.partner_id or director.work_contact_id
        return partners

    def _ems_inform_chiefs(self, with_direction=False):
        """Subscribes the chiefs (and Direction, on approval) just before the state change, so
        the outcome summary reaches them. The chiefs already follow a request filed through
        '_ems_announce_request'; this covers the ones filed before it existed."""
        for leave in self:
            partners = leave._ems_notify_partners()
            if with_direction:
                partners |= leave._ems_direction_partners()
            if partners:
                leave.message_subscribe(partner_ids=partners.ids)

    def _ems_announce_request(self):
        """Tells the chiefs a request has been filed, so they can plan the department's cover
        ahead instead of learning of it once decided. They follow it from then on, like anyone
        else involved, and receive whatever is posted on it.

        A note addressed to them alone: the approver already has the approval activity and the
        employee filed it themselves. 'sudo' because the employee filing it cannot subscribe
        anybody else - Odoo's own create subscribes the approver the same way."""
        for leave in self.sudo():
            partners = leave._ems_notify_partners()
            if partners:
                leave.message_subscribe(partner_ids=partners.ids)
                leave._ems_notify(partners, leave._ems_summary())

    def _ems_when(self):
        """The absence's dates as a sentence fragment, for the messages about it."""
        self.ensure_one()
        when = format_date(self.env, self.request_date_from)
        if self.request_date_to and self.request_date_to != self.request_date_from:
            return _("%(start)s to %(end)s", start=when, end=format_date(self.env, self.request_date_to))
        if not self.ems_full_day:
            return _("%(date)s, from %(start)s to %(end)s", date=when,
                     start=format_time_float(self.request_hour_from),
                     end=format_time_float(self.request_hour_to))
        return when

    def _ems_summary(self):
        """Who, what and when, for the messages the chiefs receive about a request.

        Odoo's own notification is a single line and the tracking entry is just
        'Status: Pending → Approved', which tells a department chief nothing they can act on.

        The written reason is deliberately absent: a chief is informed that a colleague is away
        and of what kind, not why - the same line 'hr.leave.private_name' draws in the interface.
        """
        self.ensure_one()
        # Called on the mixin rather than inherited: 'ems.base' would also add its own
        # fields to hr.leave, 'active' among them. This is the shared escaping-safe
        # list builder (see EmsBase.build_html_list), not a hand-rolled copy of it.
        details = self.env['ems.base'].build_html_list([
            _("Employee: %(name)s", name=self.employee_id.display_name),
            _("Absence type: %(type)s", type=self.holiday_status_id.display_name),
            _("Dates: %(when)s", when=self._ems_when()),
            _("Duration: %(hours).2f h", hours=self.number_of_hours),
            _("Status: %(state)s", state=dict(
                self._fields['ems_status']._description_selection(self.env))[self.ems_status]),
        ])
        return Markup("<p>%s</p>%s") % (
            _("Absence request of %(name)s", name=self.employee_id.display_name), details)

    def _ems_post_outcome(self):
        """The summary of what was decided, for everyone following the request."""
        for leave in self:
            leave.message_post(body=leave._ems_summary(), subtype_xmlid='mail.mt_comment')

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

    def activity_update(self):
        """Shortens the absence type in the approval activity hr_holidays schedules.

        Its note is "New %(leave_type)s Request created by %(user)s" with the type's *full*
        wording dropped into it, which here is a whole legal sentence - so the chatter entry the
        employee sees the moment they file a request reads as a paragraph of legalese instead of
        as a request somebody has to act on. Same treatment, for the same reason, as
        '_compute_display_name' gives every other place Odoo prints a leave.

        Rewritten afterwards rather than reimplemented: 'activity_update' is forty lines of
        state handling and deadline arithmetic that has nothing to do with this, and the note is
        built inline inside it with no hook of its own.
        """
        result = super().activity_update()
        for leave in self:
            long_name = leave.holiday_status_id.name
            short_name = leave.holiday_status_id.ems_short_name
            if not long_name or not short_name or short_name == long_name:
                continue
            for activity in leave.activity_ids:
                # str(), not the Markup an Html field returns: Markup.replace() escapes both of
                # its arguments, so a type whose name carries an apostrophe would stop matching
                # itself. Sudo because the activity belongs to the approver, not to the employee
                # who just filed the request and triggered this.
                note = str(activity.note or '')
                if long_name in note:
                    activity.sudo().note = note.replace(long_name, short_name)
        return result

    def action_approve(self, check_state=True):
        """The Head's acknowledgement. It takes effect straight away, as Odoo's own approval
        always has (calendar, hour balance, guard duty board), but it is not yet the Head's
        validation when the absence type requires a supporting document: the request then waits
        for it, or goes straight to validation if it was attached with the request."""
        for leave in self.filtered(lambda leave: leave.state == 'confirm'):
            if not leave.leave_type_support_document:
                document_state = 'not_required'
            elif leave.attachment_ids:
                document_state = 'submitted'
            else:
                document_state = 'awaiting'
            # sudo: the Head's right to acknowledge it is Odoo's own approval check, below.
            leave.sudo().ems_document_state = document_state
        self._ems_inform_chiefs(with_direction=True)
        result = super().action_approve(check_state=check_state)
        self._ems_post_outcome()
        return result

    def action_refuse(self):
        self._ems_inform_chiefs()
        result = super().action_refuse()
        self._ems_post_outcome()
        return result

    # --- The supporting document ------------------------------------------------------------

    def _ems_submit_document(self):
        """Attaching the supporting document to a request awaiting it hands it back to the Head,
        with no button for the employee to forget. sudo: the employee cannot set the status
        themselves (see write()), only cause it by attaching the file."""
        submitted = self.filtered(
            lambda leave: leave.ems_document_state == 'awaiting' and leave.attachment_ids)
        if submitted:
            submitted.sudo().write({'ems_document_state': 'submitted'})

    def _ems_check_is_head(self):
        if not self.env.su and not all(leave.is_absence_head for leave in self):
            raise AccessError(_("Only the Head who approves this absence can validate its "
                                "supporting document."))

    def _ems_check_status(self, status, message):
        if any(leave.ems_status != status for leave in self):
            raise UserError(message)

    def action_ems_document_validate(self):
        """The Head's validation of the supporting document, after which the request goes to
        Direction."""
        self._ems_check_is_head()
        self._ems_check_status('pending_validation', _(
            "Only a request whose supporting document is pending validation can be validated."))
        self.write({'ems_document_state': 'validated'})
        return True

    def action_ems_document_insufficient(self):
        """Sends the request back to the employee for a valid supporting document, from the Head
        (validating it) or from Direction (reviewing it). The reminders start over."""
        for leave in self:
            if leave.ems_status == 'pending_validation':
                leave._ems_check_is_head()
            elif leave.ems_status == 'pending_direction':
                if not leave.is_absence_direction:
                    raise AccessError(_("Only Direction can change the Direction check on an absence."))
            else:
                raise UserError(_("Only a request under validation can be sent back for its "
                                  "supporting document."))
        self.write({'ems_document_state': 'awaiting'})
        self.sudo().write({'ems_document_reminder_date': False, 'ems_document_escalated': False})
        for leave in self:
            leave._ems_notify(leave.employee_id.user_id.partner_id, _(
                "The supporting document for your absence of %(when)s is not sufficient. Please "
                "attach a valid one to the request.", when=leave._ems_when()))
        return True

    def _ems_notify(self, partners, message):
        """A note addressed to these partners only: unlike a comment, it is not sent to every
        follower of the request - the department chief and Direction do not need each
        reminder."""
        self.ensure_one()
        if partners:
            self.message_post(body=message, partner_ids=partners.ids, subtype_xmlid='mail.mt_note')

    def _ems_head_users(self):
        """Who acts as this request's Head: the employee's approver, or, when they have none,
        whoever Odoo would route the approval to."""
        self.ensure_one()
        return self.sudo()._get_responsible_for_approval()

    def _ems_direction_users(self):
        self.ensure_one()
        director = self.employee_id.company_id.director_id or self.env.company.director_id
        return director.user_id if director != self.employee_id else self.env['res.users']

    def _ems_update_activities(self):
        """Keeps exactly one activity open on each request: the next step and whose it is -
        the employee attaching the document, the Head validating it, Direction reviewing it.
        The previous step's is marked done; a refused or cancelled request keeps none. The
        activity is what reaches each person's own to-do list, and the employee's turns red
        on its own once the absence is over and the document is still missing."""
        today = self.env['ems.datetime_utils'].get_local_today()
        stale_xmlids = [*ACTIVITY_BY_STATUS.values(), OVERDUE_ACTIVITY_XMLID]
        for leave in self.sudo():
            target = ACTIVITY_BY_STATUS.get(leave.ems_status)
            stale = [xmlid for xmlid in stale_xmlids if xmlid != target]
            if leave.ems_status in ('refused', 'cancel'):
                leave.activity_unlink(stale)
            else:
                leave.activity_feedback(stale)
            if not target or leave.activity_ids.filtered(
                    lambda activity: activity.activity_type_id == self.env.ref(target)):
                continue
            if leave.ems_status == 'pending_document':
                users = leave.employee_id.user_id
                deadline = max(today, (leave.request_date_to or today) + timedelta(days=1))
            elif leave.ems_status == 'pending_validation':
                users, deadline = leave._ems_head_users(), today
            else:
                users, deadline = leave._ems_direction_users(), today
            for user in users:
                leave.activity_schedule(target, date_deadline=deadline, user_id=user.id)

    @api.model
    def _cron_ems_document_reminder(self):
        """Reminds every employee whose absence is over and whose supporting document is still
        missing, every day by default, and reports it to their Head once, a few days after the
        absence (both configurable in the settings). Calendar days, in the centre's own
        timezone."""
        company = self.env.company
        today = self.env['ems.datetime_utils'].get_local_today()
        interval = company._ems_absence_document_reminder_days()
        escalation = company._ems_absence_document_escalation_days()
        leaves = self.search([('ems_status', '=', 'pending_document'), ('request_date_to', '<', today)])
        for leave in leaves:
            last = leave.ems_document_reminder_date
            if not last or (today - last).days >= interval:
                leave._ems_notify(leave.employee_id.user_id.partner_id, _(
                    "Reminder: the supporting document for your absence of %(when)s is still "
                    "missing. Please attach it to the request so it can be validated.",
                    when=leave._ems_when()))
                leave.ems_document_reminder_date = today
            if not leave.ems_document_escalated and (today - leave.request_date_to).days >= escalation:
                heads = leave._ems_head_users()
                leave._ems_notify(heads.partner_id, _(
                    "%(name)s has still not attached the supporting document for the absence of "
                    "%(when)s.", name=leave.employee_id.display_name, when=leave._ems_when()))
                for head in heads:
                    leave.activity_schedule(OVERDUE_ACTIVITY_XMLID, date_deadline=today, user_id=head.id)
                leave.ems_document_escalated = True

    # --- Direction's own approval -----------------------------------------------------------
    # Plain writes: hr.leave.write() is what keeps them Direction's alone, for these buttons and
    # for any other way in.

    def _ems_set_direction_state(self, value):
        self.write({'ems_direction_state': value})
        return True

    def action_ems_direction_done(self):
        """Direction validates last, once the Head has validated the request and its document."""
        self._ems_check_status('pending_direction', _(
            "Direction validates a request once the Head has validated it and its supporting "
            "document."))
        return self._ems_set_direction_state('done')

    def action_ems_direction_reset(self):
        return self._ems_set_direction_state('not_done')

    def action_ems_direction_refuse(self):
        """Refuses the whole request, as final as the Head's refusal. Direction's column is set
        first, so _compute_ems_head_state knows the refusal about to happen is not the Head's."""
        self._ems_set_direction_state('refused')
        return self.action_refuse()

    def action_reset_confirm(self):
        """Odoo's own reset only ever touches 'state' - left alone, a Direction refusal would
        strand 'ems_direction_state' on 'refused' after the request is reopened, with nothing
        left on screen to explain why the overall status still won't move. Direction's own
        review has to be redone, exactly like the Head's already is by
        '_compute_ems_head_state' reacting to 'state' alone.

        'sudo()' on the write: reaching this method at all already requires the Time Off
        Manager group (Odoo's own 'hr.leave._check_approval_update', called from 'write()' for
        every non-superuser), a strictly wider right than '_ems_can_set_direction_state()' asks
        for - so clearing a now-stale refusal as a side effect of that reset is not a fresh
        Direction decision needing its own check."""
        refused_by_direction = self.filtered(lambda leave: leave.ems_direction_state == 'refused')
        result = super().action_reset_confirm()
        refused_by_direction.sudo()._ems_set_direction_state('not_done')
        # Same for the supporting document: the Head acknowledges the reopened request afresh.
        self.sudo().write({'ems_document_state': False, 'ems_document_reminder_date': False,
                           'ems_document_escalated': False})
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

        Plain 'hr' does the exact same thing independently of hr_holidays -
        'hr/security/hr_security.xml' grants 'hr.group_hr_manager' to 'base.default_user' at
        install time too (noupdate="1", so it is not something a .po/data fix can touch), which
        by implication also carries 'hr.group_hr_user'. Found 2026-09-09 via a genuinely clean
        install (this centre's own dev database predates the fix and never surfaced it):
        'hr.group_hr_manager' is 'hr.group_hr_user's other source of unearned entitlement, on top
        of hr_holidays' own groups, and every new account was silently born an HR Administrator
        - full read/write on every colleague's personal HR record - regardless of role. It is now
        in 'TIME_OFF_GROUP_XMLIDS' for the same reason 'hr.group_hr_user' already was: EMS's own
        'ems.group_secretary_admin' is the one legitimate holder (security/groups.xml), so the
        same "revoke unless some other group still implies it" rule applies to it unchanged.

        The rule applied is Odoo's own implication semantics rather than a hardcoded list: a
        user keeps one of these groups only if they hold some *other* group that transitively
        implies it - which, after security/groups.xml, means the Head of Studies chain.

        The one group that cannot come from a chain is 'group_hr_holidays_responsible', the one
        that lets somebody approve. Who approves is not a role anybody holds: it is whoever is
        named as an employee's 'leave_manager_id' (the Area Manager of a top-level department,
        see _compute_leave_manager). Notably that is *not* the whole Secretary group - only the
        ASP area's own manager - so this grants it from that relation instead, which keeps it
        exact and self-maintaining as Area Managers change.

        **Archived users are part of this, 'base.default_user' above all.** That template is
        itself an archived user, and 'res.groups.users' does not return archived ones - so a
        first version of this method left the very record hr_holidays granted the Administrator
        group to untouched, and every user created from then on was born holding it again
        ('res.users._default_groups' copies the template's groups verbatim). The whole recordset
        is therefore read with 'active_test=False', which also covers former staff: an archived
        employee who comes back gets their groups from the role hierarchy
        ('hr.employee._sync_security_groups'), not from what was left on their old account.

        Idempotent, and safe to run at any time. Returns {xmlid: [login, ...]} of what it
        revoked, so a migration can log it.
        """
        protected = self.env.ref('base.user_root') | self.env.ref('base.user_admin')
        revoked = {}
        # Widest first: revoking 'manager' before 'user' means a user who legitimately keeps
        # 'manager' is still recognised as entitled to 'user' on the next iteration.
        for xmlid in TIME_OFF_GROUP_XMLIDS:
            group = self.env.ref(xmlid).with_context(active_test=False)
            implying = self.env['res.groups'].with_context(active_test=False).search([]).filtered(
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
