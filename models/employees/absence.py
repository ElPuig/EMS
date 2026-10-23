# -*- coding: utf-8 -*-

from datetime import timedelta

from markupsafe import Markup

from odoo import _, api, fields, models, Command
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.osv.expression import OR
from odoo.tools import format_date, plaintext2html

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
    'pending_atri': 'ems.mail_activity_absence_atri_request',
    'pending_validation': 'ems.mail_activity_absence_document_validate',
    'pending_direction': 'ems.mail_activity_absence_direction_review',
}
OVERDUE_ACTIVITY_XMLID = 'ems.mail_activity_absence_document_overdue'
ATRI_OVERDUE_ACTIVITY_XMLID = 'ems.mail_activity_absence_atri_overdue'
# The two statuses in which the request waits for the employee, who is reminded once the absence
# is over: (last reminder field, reported-to-the-Head field, the Head's follow-up activity).
# See _cron_ems_document_reminder().
EMPLOYEE_STEPS = {
    'pending_document': ('ems_document_reminder_date', 'ems_document_escalated', OVERDUE_ACTIVITY_XMLID),
    'pending_atri': ('ems_atri_reminder_date', 'ems_atri_escalated', ATRI_OVERDUE_ACTIVITY_XMLID),
}

# What the employee filed: a change to any of these by somebody else is reported back to them
# with the next decision on the request - see _ems_notify_request_changes().
REQUEST_FIELDS = (
    'holiday_status_id', 'request_date_from', 'request_date_to', 'ems_full_day',
    'request_hour_from', 'request_hour_to',
)
# Statuses with no decision left to carry that report, so a change is reported when it is saved.
CLOSED_STATUSES = ('approved', 'refused', 'cancel')
# The three fields a decision moves, and so what undoing one puts back - see _ems_undo().
DECISION_FIELDS = ('state', 'ems_document_state', 'ems_atri_state', 'ems_direction_state')
# Not 'ems_atri_state': confirming it is requested in ATRI is the employee's own step, not a
# decision, and undoing the Head's validation leaves what they confirmed as it was.
NOT_DECIDED = {'state': 'confirm', 'ems_document_state': False, 'ems_direction_state': 'not_done'}

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
            ('waived', 'Waived'),
        ],
        copy=False, tracking=True, readonly=True,
        help="Set when the Head acknowledges the request: absence types that require a "
             "supporting document wait for it, and attaching it sends the request back to the "
             "Head for validation. Waived: the Head or Direction let the request go on without "
             "it.")
    ems_document_reminder_date = fields.Date(
        string="Last document reminder", copy=False, readonly=True,
        help="The last day the employee was reminded that the supporting document is missing.")
    ems_document_escalated = fields.Boolean(
        string="Missing document reported to the Head", copy=False, readonly=True)
    ems_document_return_reason = fields.Text(
        string="Why the document was sent back", copy=False, readonly=True,
        help="Written by the Head or Direction when the supporting document is not sufficient. "
             "Shown to the employee until they attach a new one.")
    ems_atri_state = fields.Selection(
        string="ATRI confirmation",
        selection=[
            ('not_required', 'Not required'),
            ('awaiting', 'Pending ATRI confirmation'),
            ('requested', 'Confirmed by the employee'),
        ],
        copy=False, tracking=True, readonly=True,
        help="Once the Head has validated an ATRI absence, it always waits for the employee to "
             "confirm they have requested it on the Generalitat's ATRI portal before it goes on "
             "to Direction, which can send it back there when it is not really in ATRI.")
    ems_atri_reminder_date = fields.Date(
        string="Last ATRI reminder", copy=False, readonly=True,
        help="The last day the employee was reminded to confirm the absence is requested in ATRI.")
    ems_atri_escalated = fields.Boolean(
        string="Missing ATRI confirmation reported to the Head", copy=False, readonly=True)
    ems_atri_return_reason = fields.Text(
        string="Why it was sent back as not in ATRI", copy=False, readonly=True,
        help="Written by Direction when the absence does not appear in ATRI. Shown to the "
             "employee until they confirm they have requested it.")
    ems_can_mark_atri = fields.Boolean(
        string="Current user can confirm it is requested in ATRI", compute="_compute_ems_can_mark_atri",
        help="Whether the user reading this request may confirm it has been requested in ATRI: "
             "the employee themselves, or whoever manages the absence on their behalf.")
    ems_can_waive_document = fields.Boolean(
        string="Current user can waive the supporting document",
        compute="_compute_ems_can_waive_document",
        help="Whether the user reading this request may let it go on without its supporting "
             "document: the Head, Direction and the administrator, while it is awaited.")
    ems_refusal_reason = fields.Text(
        string="Reason for the refusal", copy=False, readonly=True,
        help="Written by the Head or Direction when refusing the request. Sent to the employee "
             "alone and shown to them on the request while it stays refused.")
    ems_original_request = fields.Json(
        string="Request before its corrections", copy=False, readonly=True,
        help="What the employee had filed, kept from the moment somebody else corrects the "
             "request until the employee has been told what was changed.")
    ems_decision_before = fields.Json(
        string="Decisions before the last one", copy=False, readonly=True,
        help="Where the request stood before it was refused, cancelled or sent back for its "
             "supporting document: what undoing that puts back.")
    ems_can_undo = fields.Boolean(
        string="Current user can undo the last decision", compute="_compute_ems_can_undo",
        help="Whether the user reading this request may take back the last decision on it: "
             "whoever took it, anyone above them, and the administrator.")
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
            ('pending_atri', 'Pending ATRI confirmation'),
            ('pending_direction', 'Pending Direction'),
            ('approved', 'Approved'),
            ('refused', 'Refused'),
            ('cancel', 'Cancelled'),
        ],
        compute="_compute_ems_status", store=True, copy=False,
        help="Where the request stands: the Head acknowledges it, the employee attaches the "
             "supporting document when its type requires one, the Head validates it, the "
             "employee confirms it is requested in ATRI when it is an ATRI absence and "
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

    @api.depends('state', 'ems_head_state', 'ems_direction_state', 'ems_atri_state')
    def _compute_ems_status(self):
        for leave in self:
            if leave.state in ('refuse', 'cancel'):
                leave.ems_status = 'refused' if leave.state == 'refuse' else 'cancel'
            elif leave.ems_head_state == 'approved' and leave.ems_direction_state == 'done':
                leave.ems_status = 'approved'
            elif leave.ems_head_state == 'approved':
                # The Head is done with it: an ATRI absence then always waits for the employee
                # to confirm it is requested in ATRI before it is Direction's (issue #619).
                leave.ems_status = 'pending_atri' if leave.ems_atri_state == 'awaiting' else 'pending_direction'
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

    @api.depends_context('uid')
    @api.depends('ems_status', 'ems_direction_state', 'ems_decision_before', 'employee_id')
    def _compute_ems_can_undo(self):
        for leave in self:
            leave.ems_can_undo = leave._ems_can_undo()

    @api.depends_context('uid')
    @api.depends('ems_status', 'employee_id')
    def _compute_ems_can_mark_atri(self):
        for leave in self:
            leave.ems_can_mark_atri = leave.ems_status == 'pending_atri' and (
                leave.employee_id.user_id == self.env.user or leave.is_absence_manager
                or leave.is_absence_direction or leave._ems_is_absence_admin())

    @api.depends_context('uid')
    @api.depends('ems_status')
    def _compute_ems_can_waive_document(self):
        for leave in self:
            leave.ems_can_waive_document = leave.ems_status == 'pending_document' and (
                leave.is_absence_head or leave.is_absence_direction or leave._ems_is_absence_admin())

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

    @api.model
    def _ems_covers_working_day(self, employee, day, hour_from, hour_to):
        """Whether being away between these times leaves nothing of what the employee was
        expected to work that day: such an absence is a whole day, whatever times were given
        unless the requester says otherwise (issue #613). Never for an employee with no
        timetable that day - there is nothing to compare with.

        sudo: the employee filing a request reads their own timetable here, which the plain
        employee record does not let every role do."""
        if not employee or not day or (hour_to or 0.0) <= (hour_from or 0.0):
            return False
        expected = employee.sudo()._ems_expected_intervals(fields.Date.to_date(day))
        if not expected:
            return False
        utils = self.env['ems.datetime_utils']
        first = min(utils.time_to_float(start.time()) for start, _end in expected)
        last = max(utils.time_to_float(end.time()) for _start, end in expected)
        return hour_from <= first and hour_to >= last

    @api.onchange('employee_id', 'request_date_from', 'request_hour_from', 'request_hour_to')
    def _onchange_ems_whole_timetable(self):
        """Times that cover the employee's whole timetable for the day are a whole-day absence:
        the box is ticked for them, saying why, rather than left to be found out from the hours
        counted. A proposal, like the one the absence type makes: not triggered by the box
        itself, so unticking it stands - the day may not really be lost (a lesson moved to
        another time is exactly what the guard duty board arranges, issue #605)."""
        if self.ems_full_day or self.request_date_from != self.request_date_to:
            return None
        if not self._ems_covers_working_day(
                self.employee_id, self.request_date_from, self.request_hour_from, self.request_hour_to):
            return None
        self.ems_full_day = True
        return {'warning': {
            'title': _("Whole-day absence"),
            'message': _(
                "These times cover the whole timetable of that day, so the absence is marked as "
                "a whole day: not coming in at all counts %(hours).2f hours, however many "
                "lessons there were.", hours=self.env.company._ems_full_day_hours()),
        }}

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
                vals.pop('ems_atri_state', None)
        self._ems_mark_whole_days(vals_list)
        leaves = super().create(vals_list)
        leaves._ems_announce_request()
        return leaves

    def unlink(self):
        """A request withdrawn before it was decided (Odoo lets the employee delete it while it
        is pending) will not take place either: the Department Chief and the Seminar Chief are
        told, through message_notify since the request and its chatter are about to go."""
        for leave in self.sudo().filtered(lambda leave: leave.state not in ('refuse', 'cancel')):
            partners = leave._ems_notify_partners() - self.env.user.partner_id
            if partners:
                self.env['mail.thread'].sudo().message_notify(
                    partner_ids=partners.ids, subject=_("Absence request withdrawn"),
                    body=Markup("<p>%s</p>%s") % (
                        _("This absence will not take place: its request has been withdrawn."),
                        leave._ems_summary()),
                    email_layout_xmlid='mail.mail_notification_light')
        return super().unlink()

    def _ems_mark_whole_days(self, vals_list):
        """What _onchange_ems_whole_timetable does on the form, for a request filed any other
        way: one whose times cover the employee's whole timetable for its day is filed as a
        whole day. Only when "Whole day?" was left out: a value given explicitly, the form's
        own included, is the requester's answer."""
        default_employee = self.env.context.get('default_employee_id') or self.env.user.employee_id.id
        to_date = fields.Date.to_date
        for vals in vals_list:
            day = to_date(vals.get('request_date_from'))
            if 'ems_full_day' in vals or not day or to_date(vals.get('request_date_to') or day) != day:
                continue
            employee = self.env['hr.employee'].browse(vals.get('employee_id') or default_employee)
            if self._ems_covers_working_day(
                    employee, day, vals.get('request_hour_from'), vals.get('request_hour_to')):
                vals['ems_full_day'] = True

    def write(self, vals):
        if 'ems_direction_state' in vals and not self._ems_can_set_direction_state():
            raise AccessError(_("Only Direction can change the Direction check on an absence."))
        if 'ems_document_state' in vals and not self.env.su and not all(
                leave.is_absence_head or leave.is_absence_direction for leave in self):
            raise AccessError(_("Only the Head or Direction can change the supporting document "
                                "status of an absence."))
        if 'ems_atri_state' in vals and not self.env.su:
            # Only ever moved by the Head's validation, the employee's own statement and
            # Direction sending it back, each with its own check.
            raise AccessError(_("The ATRI confirmation of an absence cannot be changed by hand."))
        self._ems_check_own_approved_write(vals)
        self._ems_keep_decision_before(vals)
        corrected = self._ems_keep_original_request(vals)
        cover_before = {leave.id: leave._ems_cover_values() for leave in self} \
            if vals.keys() & {'state', *REQUEST_FIELDS} else {}
        result = super().write(vals)
        self._ems_inform_department(cover_before)
        # No decision is left to report the correction with: the employee is told now.
        corrected.filtered(
            lambda leave: leave.ems_status in CLOSED_STATUSES)._ems_notify_request_changes()
        if vals.keys() & ATTACHMENT_FIELDS:
            self._ems_submit_document()
        if vals.keys() & set(DECISION_FIELDS):
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

    def _ems_stage_users(self):
        """Whoever has the request in hand at its current stage, and so talks with the employee
        about it (issue #632): the Head until they validate it and pass it on to Direction, the
        Director from then on. An ATRI absence Direction sent back is settled on the ATRI portal
        and comes straight back to it, so it stays Direction's; a supporting document it sent
        back is the Head's to validate again, so that request is the Head's again. With no
        Director to review it (none configured, or the Director is the one absent) the Head
        keeps it throughout."""
        self.ensure_one()
        status = self.ems_status
        directions = status in ('pending_direction', 'approved') or (
            status == 'pending_atri' and self._ems_last_decision_is_directions())
        return (directions and self._ems_direction_users()) or self._ems_head_users()

    def _ems_sync_followers(self, announce=True):
        """Keeps the employee and whoever has the request in hand (_ems_stage_users) as its
        followers, so a message written on it reaches the other side of the conversation and
        nobody else. Only the Head and the Director change hands: anybody else following it, by
        choice or because they wrote on it, is left alone. A refused or cancelled request keeps
        whoever had it when it was closed.

        Whoever newly takes it is told, unless they are the one who moved it there. Returns the
        partners told, whose activity for the same step needs no email of its own."""
        told = self.env['res.partner']
        for leave in self.sudo():
            if leave.ems_status in ('refused', 'cancel'):
                continue
            employee = leave.employee_id
            owners = leave._ems_stage_users().partner_id
            roles = (leave._ems_head_users() | leave._ems_direction_users()).partner_id
            followers = leave.message_partner_ids
            leaving = (roles & followers) - owners - (employee.user_id.partner_id or employee.work_contact_id)
            if leaving:
                leave.message_unsubscribe(partner_ids=leaving.ids)
            arriving = owners - followers
            if arriving:
                leave.message_subscribe(partner_ids=arriving.ids)
            arriving -= self.env.user.partner_id
            # Back to Pending, the approval activity's own email already says so (activity_update).
            if announce and arriving and leave.ems_status != 'pending':
                leave._ems_notify(arriving, Markup("%s<p>%s</p>") % (
                    leave._ems_summary(), _("It is now in your hands.")))
                told |= arriving
        return told

    def _ems_reset_followers(self):
        """For requests filed before issue #632, which the Department Chief, the Seminar Chief
        and the Director followed from the start: the Department Chief and the Seminar Chief
        stop following them, unless they have them in hand, and every request still open is
        left with the followers _ems_sync_followers gives it. Nobody is told."""
        for leave in self.sudo():
            keep = leave._ems_stage_users().partner_id
            chiefs = leave._ems_notify_partners() - keep
            if chiefs:
                leave.message_unsubscribe(partner_ids=chiefs.ids)
        self._ems_sync_followers(announce=False)

    def _ems_announce_request(self):
        """Tells the Department Chief and the Seminar Chief a request has been filed, so they
        can arrange the department's cover ahead instead of learning of it once decided. They
        do not follow it: what they hear afterwards is only what changes that cover (see
        _ems_inform_department), never the conversation about the request (issue #632).

        A note addressed to them alone: the approver has their own email asking for the
        approval and the employee filed it themselves. 'sudo' because the employee filing it
        need not be allowed to read the approver's activity."""
        for leave in self.sudo():
            partners = leave._ems_notify_partners()
            if partners:
                # A chief who is also the approver has the same summary in the email asking
                # them to approve it (see activity_update): one email, not two.
                leave._ems_notify(
                    partners - leave.activity_ids.user_id.partner_id, leave._ems_summary())

    def _ems_cover_values(self):
        """What the Department Chief and the Seminar Chief arranged the cover for: whether the
        absence takes place, and when and of which kind."""
        self.ensure_one()
        return self.state in ('refuse', 'cancel'), self._ems_when(), self.holiday_status_id

    def _ems_inform_department(self, before):
        """Tells the Department Chief and the Seminar Chief what changed the cover they
        arranged since 'before' (_ems_cover_values per request, read before the write): the
        absence no longer takes place, takes place again, or moved to other dates or another
        type. Nothing else reaches them. sudo: whoever changed it need not read the department."""
        for leave in self.sudo():
            if leave.id not in before:
                continue
            was_closed, when, leave_type = before[leave.id]
            closed = leave.state in ('refuse', 'cancel')
            if closed and not was_closed:
                headline = _("This absence will not take place: its request has been refused.") \
                    if leave.state == 'refuse' else \
                    _("This absence will not take place: its request has been cancelled.")
            elif was_closed and not closed:
                headline = _("This absence request is going ahead again.")
            elif not closed and (when, leave_type) != (leave._ems_when(), leave.holiday_status_id):
                headline = _("The dates or the type of this absence have changed.")
            else:
                continue
            partners = leave._ems_notify_partners() - self.env.user.partner_id
            leave._ems_notify(partners, Markup("<p>%s</p>%s") % (headline, leave._ems_summary()))

    def _ems_when(self):
        """The absence's dates as a sentence fragment, for the messages about it."""
        self.ensure_one()
        return self._ems_format_when(self._ems_request_values())

    def _ems_format_when(self, values):
        """Same, for the REQUEST_FIELDS values of a request as _ems_request_values() keeps them."""
        date_from = fields.Date.to_date(values['request_date_from'])
        date_to = fields.Date.to_date(values['request_date_to'])
        when = format_date(self.env, date_from)
        if date_to and date_to != date_from:
            return _("%(start)s to %(end)s", start=when, end=format_date(self.env, date_to))
        if not values['ems_full_day']:
            return _("%(date)s, from %(start)s to %(end)s", date=when,
                     start=format_time_float(values['request_hour_from']),
                     end=format_time_float(values['request_hour_to']))
        return when

    # --- Corrections to what the employee filed ---------------------------------------------

    def _ems_request_values(self):
        """What the employee filed, in a form a Json field can keep."""
        self.ensure_one()
        return {
            'holiday_status_id': self.holiday_status_id.id,
            'request_date_from': fields.Date.to_string(self.request_date_from),
            'request_date_to': fields.Date.to_string(self.request_date_to),
            'ems_full_day': self.ems_full_day,
            'request_hour_from': self.request_hour_from,
            'request_hour_to': self.request_hour_to,
        }

    def _ems_keep_original_request(self, vals):
        """Called by write() before it changes anything: keeps what the employee had filed on
        the requests somebody else is about to correct, unless it is already kept from an
        earlier correction they have not been told about yet. Returns those requests.

        sudo: whoever corrects a request need not be allowed to write this field, which nobody
        sets by hand."""
        corrected = self.browse()
        if not vals.keys() & set(REQUEST_FIELDS):
            return corrected
        for leave in self:
            if leave.employee_id.user_id == self.env.user:
                continue
            corrected |= leave
            if not leave.ems_original_request:
                leave.sudo().ems_original_request = leave._ems_request_values()
        return corrected

    def _ems_request_changes(self):
        """What somebody else changed in the request since the employee was last told, one
        line per change. Read against the request as it is now, so a correction that was undone
        is not reported."""
        self.ensure_one()
        original = self.ems_original_request
        if not original:
            return []
        changes = []
        leave_type = self.env['hr.leave.type'].browse(original['holiday_status_id'])
        if leave_type != self.holiday_status_id:
            changes.append(_("Absence type: %(old)s → %(new)s", old=leave_type.ems_short_name,
                             new=self.holiday_status_id.ems_short_name))
        before, now = self._ems_format_when(original), self._ems_when()
        if before != now:
            changes.append(_("Dates: %(old)s → %(new)s", old=before, new=now))
        return changes

    def _ems_ask_change_message(self, method, refusal=False):
        """The dialog a decision button opens first: when the request was corrected, whoever is
        deciding may explain the correction to the employee (issue #615); a refusal always
        opens it, for its reason - and it is also what stands between a stray click and a
        refused request. Only from a button that asks for it ('ems_ask_change_message' in its
        context) and for a single request, so calling the decision from code, or on a
        selection, just takes it."""
        if not self.env.context.get('ems_ask_change_message') or len(self) != 1:
            return None
        if not refusal and not self._ems_request_changes():
            return None
        return {
            'type': 'ir.actions.act_window',
            'name': _("Refuse this absence request") if refusal else _("Changes to the request"),
            'res_model': 'ems.absence.change_notice_wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_leave_id': self.id, 'default_method': method},
        }

    def _ems_notify_request_changes(self, refusal=False):
        """Tells the employee, and nobody else, what was changed in their request, with where it
        stands now and what whoever decided may have written in the dialog ('ems_change_message'
        in the context): a message about the changes, or the reason for a refusal - which is
        sent even when nothing was changed. Otherwise nothing is sent for a request nobody
        corrected."""
        message = self.env.context.get('ems_change_message')
        for leave in self:
            changes = leave._ems_request_changes()
            if leave.ems_original_request:
                leave.sudo().ems_original_request = False
            if not changes and not (refusal and message):
                continue
            if changes:
                body = Markup("<p>%s</p><p>%s</p>%s") % (
                    _("Your absence request of %(when)s has been modified. Its status is: %(status)s.",
                      when=leave._ems_when(), status=leave._ems_status_label()),
                    _("Changes made to the request:"),
                    self.env['ems.base'].build_html_list(changes))
            else:
                body = Markup("<p>%s</p>") % _(
                    "Your absence request of %(when)s has been refused.", when=leave._ems_when())
            if message:
                label = _("Reason for the refusal, from %(name)s:", name=self.env.user.name) if refusal \
                    else _("Message from %(name)s:", name=self.env.user.name)
                body += Markup("<p>%s</p>%s") % (label, plaintext2html(message))
            employee = leave.employee_id
            leave._ems_notify(employee.user_id.partner_id or employee.work_contact_id, body)

    def _ems_status_label(self):
        self.ensure_one()
        return dict(self._fields['ems_status']._description_selection(self.env))[self.ems_status]

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
            _("Status: %(state)s", state=self._ems_status_label()),
        ])
        return Markup("<p>%s</p>%s") % (
            _("Absence request of %(name)s", name=self.employee_id.display_name), details)

    def _track_subtype(self, init_values):
        """Keeps the approval's own tracking entry ("Status: Pending → Approved") a plain note
        on the request. hr_holidays gives it a subtype every follower is emailed with, and
        '_ems_post_outcome' already sends them the summary of that same approval: two emails
        for one decision (issue #625)."""
        if 'state' in init_values and self.state == 'validate':
            return self.env.ref('mail.mt_note')
        return super()._track_subtype(init_values)

    def _ems_post_outcome(self):
        """The summary of what was decided, for the employee. Whoever takes the request next is
        told by _ems_sync_followers, and the Department Chief and the Seminar Chief by
        _ems_inform_department - each only what concerns them (issue #632)."""
        for leave in self:
            employee = leave.employee_id
            leave._ems_notify(employee.user_id.partner_id or employee.work_contact_id, leave._ems_summary())

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
        """Replaces the email of the approval activity hr_holidays schedules, and shortens the
        absence type in its note.

        The email Odoo sends whoever the activity is assigned to says a document has been
        assigned to them and nothing else: not the dates, not the hours. Approving an absence
        starts with knowing what has to be covered, so they get the same summary the chiefs do,
        with the request for their approval, and Odoo's own email is not sent
        ('mail_activity_quick_update', which is what stops it).

        The note is "New %(leave_type)s Request created by %(user)s" with the type's *full*
        wording dropped into it, which here is a whole legal sentence - so the chatter entry the
        employee sees the moment they file a request reads as a paragraph of legalese instead of
        as a request somebody has to act on. Same treatment, for the same reason, as
        '_compute_display_name' gives every other place Odoo prints a leave.

        Both done afterwards rather than by reimplementing it: 'activity_update' is forty lines
        of state handling and deadline arithmetic that has nothing to do with this, and the note
        is built inline inside it with no hook of its own.
        """
        activities_before = {leave.id: leave.sudo().activity_ids for leave in self}
        result = super(EmsAbsenceLeave, self.with_context(
            mail_activity_quick_update=True)).activity_update()
        # Sudo because the activity belongs to the approver, not to the employee who just filed
        # the request and triggered this.
        for leave in self.sudo():
            assigned = leave.activity_ids - activities_before[leave.id]
            long_name = leave.holiday_status_id.name
            short_name = leave.holiday_status_id.ems_short_name
            if long_name and short_name and short_name != long_name:
                for activity in leave.activity_ids:
                    # str(), not the Markup an Html field returns: Markup.replace() escapes both
                    # of its arguments, so a type whose name carries an apostrophe would stop
                    # matching itself.
                    note = str(activity.note or '')
                    if long_name in note:
                        activity.note = note.replace(long_name, short_name)
            # Not whoever caused it: Odoo does not email them their own activity either.
            approvers = assigned.user_id - self.env.user
            leave._ems_notify(approvers.partner_id, Markup("%s<p>%s</p>") % (
                leave._ems_summary(), _("It is waiting for your approval.")))
        return result

    def action_approve(self, check_state=True):
        """The Head's acknowledgement. It takes effect straight away, as Odoo's own approval
        always has (calendar, hour balance, guard duty board), but it is not yet the Head's
        validation when the absence type requires a supporting document: the request then waits
        for it, or goes straight to validation if it was attached with the request."""
        wizard = self._ems_ask_change_message('action_approve')
        if wizard:
            return wizard
        self._ems_forget_decision_before()
        for leave in self.filtered(lambda leave: leave.state == 'confirm'):
            if not leave.leave_type_support_document:
                document_state = 'not_required'
            elif leave.attachment_ids:
                document_state = 'submitted'
            else:
                document_state = 'awaiting'
            # An ATRI absence always waits for the employee's confirmation once the Head is
            # done - the Head validates first because employees do pick ATRI for what is not,
            # and the other way round. Only a confirmation already given (the Head undid their
            # own validation and repeats it) is not asked for twice.
            if not leave.ems_needs_atri:
                atri_state = 'not_required'
            else:
                atri_state = 'requested' if leave.ems_atri_state == 'requested' else 'awaiting'
            # sudo: the Head's right to acknowledge it is Odoo's own approval check, below.
            leave.sudo().write({'ems_document_state': document_state, 'ems_atri_state': atri_state})
        result = super().action_approve(check_state=check_state)
        self._ems_post_outcome()
        self._ems_notify_request_changes()
        return result

    def action_refuse(self):
        wizard = self._ems_ask_change_message('action_refuse', refusal=True)
        if wizard:
            return wizard
        result = super().action_refuse()
        # The reason written in the dialog, kept on the request for the employee to read there
        # too. sudo: whoever may refuse need not be allowed to write the field itself.
        self.sudo().write({'ems_refusal_reason': self.env.context.get('ems_change_message') or False})
        self._ems_post_outcome()
        self._ems_notify_request_changes(refusal=True)
        return result

    # --- The supporting document ------------------------------------------------------------

    def _ems_submit_document(self):
        """Attaching the supporting document to a request awaiting it hands it back to the Head,
        with no button for the employee to forget. sudo: the employee cannot set the status
        themselves (see write()), only cause it by attaching the file."""
        submitted = self.filtered(
            lambda leave: leave.ems_document_state == 'awaiting' and leave.attachment_ids)
        if submitted:
            submitted._ems_forget_decision_before()
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
        Direction. A reason it was sent back earlier no longer applies to the document now
        validated."""
        self._ems_check_is_head()
        self._ems_check_status('pending_validation', _(
            "Only a request whose supporting document is pending validation can be validated."))
        wizard = self._ems_ask_change_message('action_ems_document_validate')
        if wizard:
            return wizard
        self._ems_forget_decision_before()
        self.write({'ems_document_state': 'validated'})
        self.sudo().write({'ems_document_return_reason': False})
        self._ems_notify_request_changes()
        return True

    def action_ems_document_waive(self):
        """Lets a request awaiting its supporting document go on without it, when it is not
        going to arrive and is not needed after all (issue #634). Recorded as 'waived', never as
        validated, so nobody takes it for a document somebody checked. A reason it had been
        sent back with is kept: undoing the waiver shows it to the employee again."""
        self._ems_check_status('pending_document', _(
            "Only a request awaiting its supporting document can be exempted from it."))
        if not all(leave.ems_can_waive_document for leave in self):
            raise AccessError(_("Only the Head who approves this absence, Direction or the "
                                "administrator can exempt it from its supporting document."))
        wizard = self._ems_ask_change_message('action_ems_document_waive')
        if wizard:
            return wizard
        self._ems_forget_decision_before()
        # sudo: the right to waive it is checked above, and the administrator need not be the
        # Head or Direction write() requires.
        self.sudo().write({'ems_document_state': 'waived'})
        for leave in self:
            leave._ems_notify(leave.employee_id.user_id.partner_id, _(
                "The supporting document for your absence of %(when)s is no longer required.",
                when=leave._ems_when()))
        self._ems_notify_request_changes()
        return True

    def action_ems_document_insufficient(self):
        """Asks the Head (validating the document) or Direction (reviewing it) why it is not
        sufficient before sending the request back: the employee needs to know what to attach
        instead. When the new document is sent back again, the previous reason is offered for
        editing rather than written from scratch.

        An ATRI absence is justified on the portal, not in EMS: Direction sends it back to
        "Pending ATRI confirmation", never to the Head's "Awaiting documentation" (issue #627)."""
        self.ensure_one()
        context = {'default_leave_id': self.id}
        if self._ems_justified_in_atri():
            self._ems_check_can_return_atri()
            context['default_kind'] = 'atri_document'
        else:
            self._ems_check_can_return_document()
            context['default_reason'] = self.ems_document_return_reason
        return {
            'type': 'ir.actions.act_window',
            'name': _("Documentation insufficient"),
            'res_model': 'ems.absence.document_return_wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': context,
        }

    def _ems_justified_in_atri(self):
        """Whether what Direction is reviewing is justified on the ATRI portal rather than with
        a supporting document in EMS."""
        self.ensure_one()
        return self.ems_needs_atri and self.ems_status == 'pending_direction'

    def _ems_check_can_return_document(self):
        for leave in self:
            if leave._ems_justified_in_atri():
                raise UserError(_("An ATRI absence is justified on the ATRI portal: it is sent "
                                  "back there, not for a supporting document in EMS."))
            if leave.ems_status == 'pending_validation':
                leave._ems_check_is_head()
            elif leave.ems_status == 'pending_direction':
                if not leave.is_absence_direction:
                    raise AccessError(_("Only Direction can change the Direction check on an absence."))
            else:
                raise UserError(_("Only a request under validation can be sent back for its "
                                  "supporting document."))

    def _ems_return_document(self, reason):
        """Sends the request back to the employee for a valid supporting document, telling them
        why. The reminders start over. The reason is written first so the employee's new
        activity, scheduled by write(), carries it."""
        self._ems_check_can_return_document()
        before = {leave.id: leave._ems_decision_values() for leave in self}
        self.sudo().write({'ems_document_return_reason': reason, 'ems_document_reminder_date': False,
                           'ems_document_escalated': False})
        self.write({'ems_document_state': 'awaiting'})
        for leave in self.sudo():
            leave.ems_decision_before = before[leave.id]
        for leave in self:
            leave._ems_notify(leave.employee_id.user_id.partner_id, _(
                "The supporting document for your absence of %(when)s is not sufficient. "
                "Reason: %(reason)s. Please attach a valid one to the request.",
                when=leave._ems_when(), reason=reason))
        self._ems_notify_request_changes()
        return True

    # --- The request in ATRI (issue #619) ---------------------------------------------------

    def action_ems_atri_requested(self):
        """The employee's step on an ATRI absence their Head has validated: they confirm they
        have requested it on the portal, which hands it to Direction. sudo: the employee cannot
        write this status, nor their own approved request (see write() and
        _ems_check_own_approved_write), only cause this."""
        for leave in self:
            if not leave.ems_can_mark_atri:
                raise AccessError(_("Only the employee, or whoever manages their absence, can "
                                    "confirm that it has been requested in ATRI."))
        self._ems_forget_decision_before()
        self.sudo().write({'ems_atri_state': 'requested', 'ems_atri_return_reason': False})
        return True

    def action_ems_atri_missing(self):
        """Asks Direction why the absence is not in ATRI before sending it back to the employee,
        the way "Documentation insufficient" does."""
        self.ensure_one()
        self._ems_check_can_return_atri()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Not in ATRI"),
            'res_model': 'ems.absence.document_return_wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_leave_id': self.id, 'default_kind': 'atri'},
        }

    def _ems_check_can_return_atri(self):
        for leave in self:
            if not (leave.is_absence_direction or leave._ems_is_absence_admin()):
                raise AccessError(_("Only Direction can send an absence back as not in ATRI."))
            if leave.ems_status != 'pending_direction' or not leave.ems_needs_atri:
                raise UserError(_("Only an ATRI absence Direction is reviewing can be sent back "
                                  "as not in ATRI."))

    def _ems_return_atri(self, reason, documentation=False):
        """Sends the request back to the employee because it is not in ATRI - or, with
        'documentation', because what they attached to it there is not sufficient - telling
        them why. The reminders start over. The reason is written first
        so the employee's new activity, scheduled by write(), carries it."""
        self._ems_check_can_return_atri()
        before = {leave.id: leave._ems_decision_values() for leave in self}
        # The status is written last: it is what schedules the employee's activity and hands the
        # request on (_ems_stage_users), which needs to know the decision was Direction's.
        self.sudo().write({'ems_atri_return_reason': reason, 'ems_atri_reminder_date': False,
                           'ems_atri_escalated': False})
        for leave in self.sudo():
            leave.ems_decision_before = before[leave.id]
        self.sudo().write({'ems_atri_state': 'awaiting'})
        for leave in self:
            employee = leave.employee_id
            if documentation:
                message = _(
                    "The documentation of your absence of %(when)s in ATRI is not sufficient. "
                    "Reason: %(reason)s. Please complete it on the ATRI portal and then confirm "
                    "it on the absence request.", when=leave._ems_when(), reason=reason)
            else:
                message = _(
                    "Your absence of %(when)s does not appear in ATRI. Reason: %(reason)s. Please "
                    "request it on the ATRI portal and then confirm it on the absence request.",
                    when=leave._ems_when(), reason=reason)
            leave._ems_notify(employee.user_id.partner_id or employee.work_contact_id, message)
        self._ems_notify_request_changes()
        return True

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
        the employee attaching the document, the Head validating it, the employee requesting
        it in ATRI, Direction reviewing it.
        The previous step's is marked done; a refused or cancelled request keeps none. The
        activity is what reaches each person's own to-do list, and the employee's turns red
        on its own once the absence is over and the document is still missing."""
        today = self.env['ems.datetime_utils'].get_local_today()
        stale_xmlids = [*ACTIVITY_BY_STATUS.values(), OVERDUE_ACTIVITY_XMLID, ATRI_OVERDUE_ACTIVITY_XMLID]
        # Whoever the summary just told the request is in their hands needs no second email
        # for the activity of that same step.
        told = self._ems_sync_followers()
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
            note = ''
            if leave.ems_status in EMPLOYEE_STEPS:
                users = leave.employee_id.user_id
                deadline = max(today, (leave.request_date_to or today) + timedelta(days=1))
                reason = leave.ems_document_return_reason if leave.ems_status == 'pending_document' \
                    else leave.ems_atri_return_reason
                note = plaintext2html(reason) if reason else ''
            elif leave.ems_status == 'pending_validation':
                users, deadline = leave._ems_head_users(), today
            else:
                users, deadline = leave._ems_direction_users(), today
            for user in users:
                leave.with_context(mail_activity_quick_update=user.partner_id in told).activity_schedule(
                    target, date_deadline=deadline, user_id=user.id, note=note)

    @api.model
    def _cron_ems_document_reminder(self):
        """Reminds every employee whose absence is over and who still owes their step on it -
        the supporting document, or requesting it in ATRI (EMPLOYEE_STEPS) - every day by
        default, and reports it once, a few days after the absence, to whoever has the request
        in hand - their Head, or the Director for an ATRI absence it sent back (both intervals
        configurable in the settings). Calendar days, in the centre's own timezone.

        Each message waits for its reader's working day to start (issue #696): the scheduled
        action runs every few minutes and sends each one on the first run after that, never
        outside their working hours, and never on a day they don't work."""
        company = self.env.company
        today = self.env['ems.datetime_utils'].get_local_today()
        now = fields.Datetime.now()
        interval = company._ems_absence_document_reminder_days()
        escalation = company._ems_absence_document_escalation_days()
        # Only what is due today, so a request leaves the search once it has been dealt with.
        leaves = self.search([('request_date_to', '<', today)] + OR([[
            ('ems_status', '=', status),
            '|', '|', (reminder_field, '=', False), (reminder_field, '<=', today - timedelta(days=interval)),
            '&', (escalated_field, '=', False), ('request_date_to', '<=', today - timedelta(days=escalation)),
        ] for status, (reminder_field, escalated_field, _xmlid) in EMPLOYEE_STEPS.items()]))
        started = {}
        for leave in leaves:
            reminder_field, escalated_field, overdue_xmlid = EMPLOYEE_STEPS[leave.ems_status]
            leave._ems_remind_at_workday_start(
                leave.employee_id.user_id,
                lambda user, leave=leave: leave.with_context(lang=user.lang)._ems_reminder_messages()[0],
                today, now, started, reminder_field, interval)
            if not leave[escalated_field] and (today - leave.request_date_to).days >= escalation:
                # Whoever has it in hand: the Director for an ATRI absence it sent back.
                leave._ems_report_at_workday_start(
                    leave._ems_stage_users(),
                    lambda user, leave=leave: leave.with_context(lang=user.lang)._ems_reminder_messages()[1],
                    overdue_xmlid, today, now, started, escalated_field)

    def _ems_reminder_messages(self):
        """(reminder for the employee, report for their Head) of the step the request waits on."""
        self.ensure_one()
        when, name = self._ems_when(), self.employee_id.display_name
        if self.ems_status == 'pending_atri':
            return (
                _("Reminder: please confirm on the absence request that your absence of "
                  "%(when)s is requested in ATRI, so it can go on to Direction. If you have not "
                  "requested it on the ATRI portal yet, do that first.", when=when),
                _("%(name)s has still not confirmed that the absence of %(when)s is requested "
                  "in ATRI.", name=name, when=when))
        return (
            _("Reminder: the supporting document for your absence of %(when)s is still "
              "missing. Please attach it to the request so it can be validated.", when=when),
            _("%(name)s has still not attached the supporting document for the absence of "
              "%(when)s.", name=name, when=when))

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
        wizard = self._ems_ask_change_message('action_ems_direction_done')
        if wizard:
            return wizard
        self._ems_forget_decision_before()
        self._ems_set_direction_state('done')
        self._ems_notify_request_changes()
        return True

    def action_ems_direction_refuse(self):
        """Refuses the whole request, as final as the Head's refusal. Direction's column is set
        first, so _compute_ems_head_state knows the refusal about to happen is not the Head's."""
        wizard = self._ems_ask_change_message('action_ems_direction_refuse', refusal=True)
        if wizard:
            return wizard
        # Read before it is overwritten, for write() to keep: what undoing the refusal restores.
        before = {leave.id: leave.ems_direction_state for leave in self}
        self._ems_set_direction_state('refused')
        return self.with_context(ems_direction_before=before).action_refuse()

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
                           'ems_document_escalated': False, 'ems_document_return_reason': False,
                           'ems_decision_before': False, 'ems_refusal_reason': False,
                           'ems_atri_reminder_date': False, 'ems_atri_escalated': False,
                           'ems_atri_return_reason': False})
        return result

    # --- Undoing the last decision (issue #614) ---------------------------------------------

    def _ems_decision_values(self):
        self.ensure_one()
        return {name: self[name] for name in DECISION_FIELDS}

    def _ems_keep_decision_before(self, vals):
        """Called by write() before a request is refused or cancelled, whichever way that
        happens (the Head, Direction, the employee's own cancellation): keeps where it stood,
        which nothing else could tell afterwards. Direction's own column is already 'refused'
        by then (see action_ems_direction_refuse), which passes what it was."""
        if vals.get('state') not in ('refuse', 'cancel'):
            return
        direction_before = self.env.context.get('ems_direction_before') or {}
        for leave in self.filtered(lambda leave: leave.state not in ('refuse', 'cancel')):
            before = leave._ems_decision_values()
            before['ems_direction_state'] = direction_before.get(leave.id, before['ems_direction_state'])
            leave.sudo().ems_decision_before = before

    def _ems_forget_decision_before(self):
        """A decision that moves the request forward leaves nothing kept to go back to: undoing
        it follows the sequence itself."""
        self.sudo().filtered('ems_decision_before').ems_decision_before = False

    def _ems_is_absence_admin(self):
        """The administrator is above Direction for every permission, though outside the
        employees' hierarchy."""
        return self.env.su or self.env.user.has_group('base.group_system') \
            or self.env.user.has_group('ems.group_academic_admin')

    def _ems_last_decision_is_directions(self):
        """Whose decision an undo would take back: Direction's own (its validation, its refusal,
        a document it sent back after the Head had validated it, an absence it sent back as
        not in ATRI) or the Head's."""
        self.ensure_one()
        if self.ems_status == 'approved':
            return True
        if self.ems_status == 'refused':
            return self.ems_direction_state == 'refused'
        if self.ems_status == 'pending_atri':
            # Waiting on the employee since the Head validated it, unless Direction sent it back.
            return bool(self.ems_decision_before)
        return self.ems_status == 'pending_document' \
            and (self.ems_decision_before or {}).get('ems_document_state') == 'validated'

    def _ems_can_undo(self):
        """Whoever took the last decision can take it back, and so can anyone above them: the
        Head their own, Direction the Head's and its own, the administrator all of them. Nobody
        undoes a decision on their own absence unless they are Direction or the administrator."""
        self.ensure_one()
        if not self.id or self.ems_status == 'pending':
            return False
        if self._ems_is_absence_admin() or self.is_absence_direction:
            return True
        return self.is_absence_head and not self._ems_last_decision_is_directions() \
            and self.employee_id.user_id != self.env.user

    def action_ems_undo(self):
        """Takes back the last decision on the request, one step at a time: Approved goes back
        to Pending Direction, that to Pending validation (back to Awaiting documentation when
        the document was waived, or straight to Pending when its type requires no document), and the Head's acknowledgement back to Pending; a refused,
        cancelled or sent-back request returns to where it stood just before. Taking back the
        acknowledgement takes the absence out of the calendar, the hour balance and the guard
        duty board until it is acknowledged again."""
        for leave in self:
            if leave.ems_status == 'pending':
                raise UserError(_("Nothing has been decided on this absence request yet."))
            if not leave._ems_can_undo():
                raise AccessError(_("Only whoever took the last decision on this absence, or "
                                    "someone above them, can undo it."))
        for leave in self.sudo():
            state = leave.state
            leave._ems_undo()
            if leave.state != state:
                # In or out of effect: everyone following the request has to know.
                leave._ems_post_outcome()
            else:
                employee = leave.employee_id
                leave._ems_notify(employee.user_id.partner_id or employee.work_contact_id, _(
                    "The last decision on your absence request of %(when)s has been undone. "
                    "Its status is: %(status)s.",
                    when=leave._ems_when(), status=leave._ems_status_label()))
        return True

    def _ems_undo(self):
        """sudo: the right to undo is action_ems_undo()'s own check, which Odoo's (only a Time
        Off Manager resets a request) knows nothing about."""
        self.ensure_one()
        before = self.ems_decision_before
        if self.ems_status in ('refused', 'cancel'):
            self._ems_restore_decisions(before or NOT_DECIDED)
        elif self.ems_status in EMPLOYEE_STEPS and before:
            self._ems_restore_decisions(before)
        elif self.ems_status == 'approved':
            self.ems_direction_state = 'not_done'
        elif self.ems_status == 'pending_direction' and self.ems_document_state == 'validated':
            self.ems_document_state = 'submitted'
        elif self.ems_status in ('pending_atri', 'pending_direction') and self.ems_document_state == 'waived':
            self.ems_document_state = 'awaiting'
        else:
            self._ems_restore_decisions(NOT_DECIDED)
        self.ems_decision_before = False

    def _ems_restore_decisions(self, values):
        """Puts the request back to these DECISION_FIELDS values, through Odoo's own steps so
        the calendar entries, the approval activity and everything else hanging off 'state'
        follow."""
        self.ensure_one()
        if self.state in ('refuse', 'cancel'):
            self.action_reset_confirm()
        elif values['state'] == 'confirm':
            # Odoo has no way back from an approval; this is its reset, from 'validate'.
            self.meeting_id.active = False
            self.write({'state': 'confirm', 'first_approver_id': False, 'second_approver_id': False})
            self.activity_update()
        if values['state'] != 'confirm' and self.state == 'confirm':
            self.action_validate(check_state=False)
        restored = {
            'ems_document_state': values['ems_document_state'] or False,
            'ems_direction_state': values['ems_direction_state'] or 'not_done',
            'ems_document_return_reason': False,
            'ems_atri_return_reason': False,
        }
        # Only what was kept: undoing the Head's validation (NOT_DECIDED) leaves the ATRI
        # confirmation alone, and so does a request refused before that status existed.
        if values.get('ems_atri_state'):
            restored['ems_atri_state'] = values['ems_atri_state']
        self.write(restored)

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
