# -*- coding: utf-8 -*-

from collections import defaultdict
from datetime import time, timedelta

from pytz import UTC

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

# The absence states the guard duty board plans around (see guard_duty_board.ABSENCE_STATES): an
# absence in any of them is the teacher's own request taking over from a pending one.
ACTIVE_LEAVE_STATES = ('confirm', 'validate1', 'validate')

# The school day a new entry is prefilled with, in the company's timezone.
DEFAULT_HOUR_FROM = 8.0
DEFAULT_HOUR_TO = 15.0

# Issue #696: the last day whose missing check-ins have been turned into detected absences, and
# how many days back the detection catches up when its scheduled action could not run.
DETECTION_MARKER = 'ems.missing_check_in_last_day'
DETECTION_LOOKBACK_DAYS = 7
# The activity a detected absence still not requested leaves on its Head of Studies' list.
NOT_REQUESTED_ACTIVITY_XMLID = 'ems.mail_activity_absence_not_requested'
# Issue #707: every new detected absence waits for its reviewer, the teacher's attendance approver.
REVIEW_ACTIVITY_XMLID = 'ems.mail_activity_absence_pending_review'
# Not resolved yet: the guard duty board plans around them, a check-in or the teacher's own
# absence still resolves them.
UNRESOLVED_STATES = ('pending', 'justification_requested', 'absence_prepared')
# The teacher has been asked to act: reminded until they do.
ASKED_STATES = ('justification_requested', 'absence_prepared')


class EmsAbsencePending(models.Model):
    """A teacher's absence nobody has requested yet (issue #509, renamed "detected absence" in
    issue #696). Either informed: the teacher's Department or Seminar Chief (issue #604), the Head
    of Studies or their Deputy already knows it is coming and enters it on the teacher's behalf;
    or detected at the end of the day from a missing check-in (issue #696). The guard duty board
    plans around it. The teacher's attendance approver reviews it first (issue #707), unseen by
    the teacher, and decides: ask the teacher for a justification, prepare the absence request
    for them (the teacher still checks it, accepts the responsible declaration and sends it), both
    with reminders until the teacher acts; correct the check-in; or discard it. Once an absence is
    filed, the two are linked for good and the real one is all that counts."""
    _name = "ems.absence_pending"
    _description = "Detected absence"
    # The guard duty board reloads when an expected absence changes (issue #692).
    # Activities: a detected absence still not requested goes on its Head of Studies' list (issue #696).
    _inherit = ["mail.thread", "mail.activity.mixin", "ems.datetime_utils", "ems.guard_board_notifier"]
    _guard_board_fields = ("employee_id", "date_from", "date_to", "state")
    _order = "date_from desc, id desc"

    employee_id = fields.Many2one(
        string="Teacher", comodel_name="hr.employee", required=True, tracking=True,
        domain=lambda self: self._domain_employee_id(),
        help="Only the teachers below you in the hierarchy, teaching in your area, teaching a group your department manages or also managed by your department.")
    date_from = fields.Datetime(
        string="From", required=True, tracking=True,
        default=lambda self: self._default_local_hour(DEFAULT_HOUR_FROM))
    date_to = fields.Datetime(
        string="To", required=True, tracking=True,
        default=lambda self: self._default_local_hour(DEFAULT_HOUR_TO))
    # Whoever entered it by hand keeps it for their own reference: the teacher reads their
    # detected absences (issue #696), never this note.
    note = fields.Text(string="Notes", groups="ems.group_department_chief,base.group_system")
    origin = fields.Selection(
        string="Origin", selection=[('informed', 'Informed'), ('check_in', 'No check-in')],
        default='informed', required=True, readonly=True, copy=False,
        help="Informed: entered by hand by whoever knew about the absence. No check-in: found at "
             "the end of the day, the teacher did not check in, or arrived after their first lesson.")
    state = fields.Selection(
        string="Status",
        selection=[('pending', 'To review'), ('justification_requested', 'Justification requested'),
                   ('absence_prepared', 'Absence prepared'), ('corrected', 'Check-in corrected'),
                   ('linked', 'Requested'), ('discarded', 'Discarded')],
        default='pending', required=True, readonly=True, copy=False, tracking=True,
        help="To review: the Head of Studies decides what to do with it; the teacher is not told. "
             "Justification requested: the teacher is reminded to request the absence. Absence prepared: "
             "the same, with the absence type already chosen for them. Check-in "
             "corrected: the teacher was at the centre. Requested: linked for good to an absence "
             "request, whatever becomes of it. Discarded: by the reviewer, or because the "
             "teacher's check-in of that day showed up after all.")
    active = fields.Boolean(default=True, help="Archived when the reviewer discards it.")
    # Issue #707: "Create absence" prepares the request for the teacher, never files it: only the
    # teacher accepts the responsible declaration and sends it.
    leave_type_id = fields.Many2one(
        string="Absence type", comodel_name="hr.leave.type", readonly=True, copy=False,
        help="Chosen by the Head of Studies: the teacher's request opens with it.")
    justification_date = fields.Date(
        string="Justification requested on", readonly=True, copy=False,
        help="The reminders to the teacher and the report to their Head of Studies count from this day.")
    leave_id = fields.Many2one(
        string="Absence requested", comodel_name="hr.leave", readonly=True, copy=False,
        ondelete="set null")
    reminder_date = fields.Date(
        string="Last reminder", readonly=True, copy=False,
        help="The last day the teacher was reminded to request the absence.")
    escalated = fields.Boolean(
        string="Reported", readonly=True, copy=False,
        help="Already reported to the teacher's Head of Studies, who got an activity to follow it up.")
    can_request = fields.Boolean(compute="_compute_can_request")
    can_review = fields.Boolean(string="Can review", compute="_compute_can_review")
    can_correct_check_in = fields.Boolean(string="Can correct check-in", compute="_compute_can_review")

    def _domain_employee_id(self):
        """The same reach as the record rules: every teacher for an administrator
        (rule_absence_pending_system), otherwise the user's own branch of the hierarchy or the
        teachers of the departments they head or lead as Seminar Chief, and of those under the areas
        they manage (rule_absence_pending_hierarchy, issue #569), or whoever teaches a group one
        of those departments manages or is also managed by one of them (issue #622)."""
        domain = [('employee_type', '=', 'teacher')]
        if self.env.user.has_group('base.group_system') or self.env.user.has_group('ems.group_academic_admin'):
            return domain
        employees = self.env.user.employee_ids
        departments = employees.headed_department_ids | employees.seminar_department_ids
        # Never the user themselves: their own absence they request, and their own entry waiting
        # for review is hidden from them (rule_absence_pending_hierarchy).
        return domain + [('user_id', '!=', self.env.uid)] + [
            '|', '|', '|', '|', ('id', 'child_of', employees.ids), ('department_id', 'child_of', departments.ids),
            ('managing_department_ids', 'child_of', departments.ids),
            ('teaching_ids.group_id.study_id.managing_department_id', 'child_of', departments.ids),
            ('teaching_ids.group_id.parent_group_ids.study_id.managing_department_id', 'child_of', departments.ids)]

    def _default_local_hour(self, hour):
        return self.datetime_to_odoo(self.time_float_to_utc_datetime(self.get_local_today(), hour))

    @api.depends('employee_id', 'date_from', 'date_to')
    def _compute_display_name(self):
        for absence in self:
            if not (absence.employee_id and absence.date_from and absence.date_to):
                absence.display_name = absence.employee_id.name or _("New")
                continue
            start, stop = (self._to_local(value) for value in (absence.date_from, absence.date_to))
            absence.display_name = _(
                "%(teacher)s (%(start)s - %(stop)s)", teacher=absence.employee_id.name,
                start=start.strftime('%d/%m/%Y %H:%M'), stop=stop.strftime('%d/%m/%Y %H:%M'))

    @api.depends('state', 'employee_id')
    @api.depends_context('uid')
    def _compute_can_request(self):
        """Only the teacher themselves requests their absence, once asked to and while nobody has."""
        for absence in self:
            absence.can_request = absence.state in ASKED_STATES and absence.employee_id.user_id == self.env.user

    @api.depends('state', 'employee_id', 'date_to')
    @api.depends_context('uid')
    def _compute_can_review(self):
        now = fields.Datetime.now()
        for absence in self:
            absence.can_review = absence.state == 'pending' and absence._ems_can_review()
            absence.can_correct_check_in = absence.can_review and absence.date_to <= now

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for absence in self:
            if absence.date_to <= absence.date_from:
                raise ValidationError(_("The end of an absence must come after its start."))

    @api.model_create_multi
    def create(self, vals_list):
        absences = super().create(vals_list)
        absences._ems_schedule_review()
        return absences

    def write(self, vals):
        if vals.keys() & {'employee_id', 'date_from', 'date_to'}:
            states = set(self.mapped('state'))
            if 'linked' in states:
                raise ValidationError(_("This absence has already been requested: only the request "
                                        "counts now."))
            if 'corrected' in states:
                raise ValidationError(_("This absence was resolved by correcting the teacher's check-in."))
            if 'discarded' in states:
                raise ValidationError(_("This absence was discarded."))
        result = super().write(vals)
        if vals.get('state') and vals['state'] != 'pending':
            # Reviewed, one way or another: off the reviewer's list.
            activities = [REVIEW_ACTIVITY_XMLID]
            if vals['state'] not in UNRESOLVED_STATES:
                # Nothing is left to follow up on its Head of Studies' list either.
                activities.append(NOT_REQUESTED_ACTIVITY_XMLID)
            self.sudo().activity_feedback(activities)
        return result

    # --- Review (issue #707) ----------------------------------------------------------------------

    def _ems_schedule_review(self):
        """One "Review detected absence" task for the teacher's attendance approvers (the same
        people a check-in correction request goes to), never the teacher themselves, who must not
        see it yet. No email of its own: the task list and the daily digest are where it shows."""
        activity_type = self.env.ref(REVIEW_ACTIVITY_XMLID)
        today = self.get_local_today()
        for absence in self.sudo():
            employee = absence.employee_id
            # A Head of Studies' own entry: never to themselves, to the administrators instead.
            approvers = employee._find_attendance_approvers()
            if approvers == employee.user_id:
                approvers = employee._find_attendance_approvers(skip_hierarchy=True)
            reviewers = approvers - employee.user_id
            for user in reviewers:
                absence.with_context(mail_activity_quick_update=True).activity_schedule(
                    activity_type_id=activity_type.id, user_id=user.id, date_deadline=today)

    def _ems_can_review(self):
        """Whether the current user may decide on this entry: an attendance approver of the
        teacher (hr.employee._ems_is_attendance_approver), never the teacher themselves."""
        self.ensure_one()
        employee = self.employee_id
        return bool(employee) and employee.user_id != self.env.user \
            and employee._ems_is_attendance_approver(self.env.user)

    def _ems_review(self, apply, check=None):
        """Applies `apply(absences)` to the entries still waiting for review that the user may
        review, plus whatever `check(absence)` (a reason, or None) lets through; the rest are left
        alone and the user is told how many and why. Checked here for every record, whatever the
        screen offered."""
        reasons = defaultdict(int)
        eligible = self.browse()
        for absence in self:
            reason = (_("no longer waiting for review") if absence.state != 'pending'
                      else _("not yours to review") if not absence._ems_can_review()
                      else check and check(absence))
            if reason:
                reasons[reason] += 1
            else:
                eligible |= absence
        summary = ", ".join(_("%(count)s %(reason)s", count=count, reason=reason) for reason, count in reasons.items())
        if not eligible:
            raise UserError(_("Nothing was done: %(reasons)s.", reasons=summary))
        apply(eligible)
        reload = {'type': 'ir.actions.client', 'tag': 'soft_reload'}
        if not reasons:
            return reload
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'warning',
                'message': _("Done for %(done)s detected absences. Skipped: %(reasons)s.",
                             done=len(eligible), reasons=summary),
                'next': reload,
            },
        }

    def _ems_post_review_note(self, message):
        for absence in self.sudo():
            absence.message_post(body=message, subtype_xmlid='mail.mt_note')

    def _ems_ask_teacher(self, values, note):
        """The teacher is asked to act: the reminders start (see _cron_ems_detected_absences),
        counted from today."""
        self.sudo().write({**values, 'justification_date': self.get_local_today(),
                           'reminder_date': False, 'escalated': False})
        self._ems_post_review_note(note)

    def action_request_justification(self):
        """The teacher is asked to justify it."""
        return self._ems_review(lambda absences: absences._ems_ask_teacher(
            {'state': 'justification_requested'},
            _("Justification requested by %(user)s.", user=self.env.user.name)))

    def action_correct_check_in(self):
        """The teacher was at the centre: their attendance is completed for the hours detected,
        without telling anyone. Their own attendances are left as they are."""
        now = fields.Datetime.now()

        def apply(absences):
            Attendance = self.env['hr.attendance'].sudo()
            for absence in absences:
                spans = absence._ems_uncovered_spans()
                # Before the attendances: the check-in review they cause must not discard it.
                absence.sudo().state = 'corrected'
                Attendance.create([{
                    'employee_id': absence.employee_id.id, 'check_in': start, 'check_out': stop,
                    'in_mode': 'manual', 'out_mode': 'manual', 'ems_checked_in_by_id': self.env.uid,
                } for start, stop in spans])
            absences._ems_post_review_note(_("Check-in corrected by %(user)s.", user=self.env.user.name))
        return self._ems_review(apply, lambda absence: absence.date_to > now and _("still going on"))

    def action_create_absence(self):
        """Asks for the absence type, then prepares the request for the teacher to send (see the
        wizard and _ems_prepare_absences)."""
        return {
            'type': 'ir.actions.act_window',
            'name': _("Create absence"),
            'res_model': 'ems.absence_pending.leave_wizard',
            'views': [(False, 'form')],
            'target': 'new',
            'context': {'default_absence_ids': self.ids},
        }

    def action_discard(self):
        """Closed and archived, nothing else: no message, no attendance, no absence."""
        def apply(absences):
            absences.sudo().write({'state': 'discarded', 'active': False})
            absences._ems_post_review_note(_("Discarded by %(user)s.", user=self.env.user.name))
        return self._ems_review(apply)

    def _ems_prepare_absences(self, leave_type):
        """The absence request is prepared for the teacher with `leave_type`, never filed: they
        open it from the entry already filled in, check it, accept the responsible declaration and
        send it, which links the two (_link_to_leaves). Reminded until they do."""
        return self._ems_review(lambda absences: absences._ems_ask_teacher(
            {'state': 'absence_prepared', 'leave_type_id': leave_type.id},
            _("Absence prepared by %(user)s.", user=self.env.user.name)))

    def _ems_uncovered_spans(self):
        """[(start, stop)] of this entry's span that none of the teacher's attendances covers."""
        self.ensure_one()
        attendances = self.env['hr.attendance'].sudo().search([
            ('employee_id', '=', self.employee_id.id), ('check_in', '<', self.date_to),
            '|', ('check_out', '=', False), ('check_out', '>', self.date_from)], order='check_in')
        spans, cursor = [], self.date_from
        for attendance in attendances:
            if attendance.check_in > cursor:
                spans.append((cursor, attendance.check_in))
            cursor = max(cursor, attendance.check_out or self.date_to)
        if cursor < self.date_to:
            spans.append((cursor, self.date_to))
        return spans

    def _ems_leave_values(self):
        """The absence request matching this entry: its day and, within one day, its hours."""
        self.ensure_one()
        start, stop = self._to_local(self.date_from), self._to_local(self.date_to)
        last_day = (stop - timedelta(microseconds=1)).date()
        values = {
            'employee_id': self.employee_id.id,
            'request_date_from': start.date(),
            'request_date_to': last_day,
        }
        if start.date() == last_day:
            values.update({
                'ems_full_day': False,
                'request_hour_from': self.time_to_float(start),
                'request_hour_to': self.time_to_float(stop) if stop.date() == last_day else 24.0,
            })
        return values

    def action_request_absence(self):
        """Opens a new absence request of the teacher's own, filled in with this one's day and
        hours. Saving it links the two (_link_to_leaves)."""
        self.ensure_one()
        context = {f'default_{field}': value for field, value in self._ems_leave_values().items()}
        if self.state == 'absence_prepared':
            context['default_holiday_status_id'] = self.leave_type_id.id
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'hr.leave',
            'views': [(False, 'form')],
            'target': 'current',
            'context': context,
        }

    def _to_local(self, value):
        return self.utc_datetime_to_local(value.replace(tzinfo=UTC))

    def _get_local_hours(self, day):
        """(hour_from, hour_to) of the part of this absence that falls on `day`, in the company's
        timezone, or None when it does not touch that day - the same shape the guard duty board
        reads an hr.leave in."""
        self.ensure_one()
        start, stop = self._to_local(self.date_from), self._to_local(self.date_to)
        if start.date() > day or stop.date() < day or (stop.date() == day and stop.time() == time.min):
            return None
        hour_from = self.time_to_float(start) if start.date() == day else 0.0
        hour_to = self.time_to_float(stop) if stop.date() == day else 24.0
        return hour_from, hour_to

    @api.model
    def _link_to_leaves(self, leaves):
        """Links every unresolved entry to the teacher's own absence overlapping it. sudo(): the
        teacher filing that absence only reads their own entries, and not those still under
        review."""
        Pending = self.sudo()
        for leave in leaves.filtered(lambda leave: leave.state in ACTIVE_LEAVE_STATES):
            start, stop = leave._ems_utc_range()
            Pending.search([
                ('state', 'in', UNRESOLVED_STATES),
                ('employee_id', '=', leave.employee_id.id),
                ('date_from', '<', stop),
                ('date_to', '>', start),
            ]).write({'state': 'linked', 'leave_id': leave.id})

    def _utc_bounds(self, day, hour_from, hour_to):
        """Naive UTC datetimes for `hour_from` on `day` and `hour_to` on `day` (24.0 meaning the
        next day's midnight), in the company's timezone."""
        stop_day, hour_to = (day + timedelta(days=1), 0.0) if hour_to >= 24.0 else (day, hour_to)
        return tuple(self.datetime_to_odoo(self.time_float_to_utc_datetime(when, hour))
                     for when, hour in ((day, hour_from), (stop_day, hour_to)))

    def _guard_board_spans(self):
        return {(self._guard_board_local_date(absence.date_from), self._guard_board_local_date(absence.date_to))
                for absence in self}

    # --- Missing check-ins (issue #696) -----------------------------------------------------------

    @api.model
    def _ems_missing_check_ins(self, day, employees, arrivals=None):
        """`{employee.id: (hour_from, hour_to)}`: the part of `day` each of `employees` was
        expected and did not check in, in the company's hours. Expected: their own schedule's
        periods that weekday, read as the guard duty board reads them. Missing: the whole span of
        those periods without any check-in that day, or from the first period to the check-in when
        it came after the first period was over (a late arrival that only cut a period short is
        no absence). `arrivals` (from hr.attendance._ems_first_check_in_hours) when already read.
        sudo: it runs for a scheduled action and for whoever checks the teacher in, and only
        hours leave this method."""
        if not employees:
            return {}
        week_type = str(self.env['resource.calendar.attendance'].get_week_type(day))
        slots = self.env['ems.course'].sudo()._get_guard_duty_board_attendance_ids([
            ('dayofweek', '=', str(day.weekday())), ('calendar_id.employee_id', 'in', employees.ids),
            ('display_type', '=', False), ('day_period', '!=', 'lunch')])
        periods = defaultdict(list)
        for slot in slots:
            if not (slot.two_weeks_calendar and slot.week_type != week_type):
                periods[slot.calendar_id.employee_id.id].append((slot.hour_from, slot.hour_to))
        if arrivals is None:
            arrivals = self.env['hr.attendance']._ems_first_check_in_hours(day, employees)
        missing = {}
        for employee_id, employee_periods in periods.items():
            first_from = min(start for start, _stop in employee_periods)
            first_to = min(stop for start, stop in employee_periods if start == first_from)
            last_to = max(stop for _start, stop in employee_periods)
            arrival = arrivals.get(employee_id)
            if arrival is None:
                missing[employee_id] = (first_from, last_to)
            elif arrival > first_to:
                missing[employee_id] = (first_from, min(arrival, last_to))
        return missing

    @api.model
    def _ems_detect_missing_check_ins(self, day):
        """Turns `day`'s missing check-ins of the teachers in the circuit (the areas chosen in the
        settings) into detected absences. Nothing on a public holiday, nor on a day nobody in the
        circuit checked in (a school holiday the calendar does not know about, the summer), nor
        where the teacher already has an absence or a detected absence overlapping it."""
        domain = self.env.company._ems_absence_circuit_domain()
        if domain is None:
            return self.browse()
        day_start, day_end = self._utc_bounds(day, 0.0, 24.0)
        if self.env['resource.calendar.leaves'].sudo().search_count([
                ('resource_id', '=', False), ('date_from', '<', day_end), ('date_to', '>', day_start)], limit=1):
            return self.browse()
        teachers = self.env['hr.employee'].sudo().search(domain)
        arrivals = self.env['hr.attendance']._ems_first_check_in_hours(day, teachers)
        if not arrivals:
            return self.browse()
        candidates = {employee_id: self._utc_bounds(day, *hours)
                      for employee_id, hours in self._ems_missing_check_ins(day, teachers, arrivals).items()}
        if not candidates:
            return self.browse()
        taken = [leave._ems_utc_range() + (leave.employee_id.id,) for leave in self.env['hr.leave'].sudo().search([
            ('employee_id', 'in', list(candidates)), ('state', 'in', ACTIVE_LEAVE_STATES),
            ('request_date_from', '<=', day), ('request_date_to', '>=', day)])]
        taken += [(absence.date_from, absence.date_to, absence.employee_id.id) for absence in self.sudo().search([
            ('employee_id', 'in', list(candidates)), ('state', '!=', 'discarded'),
            ('date_from', '<', day_end), ('date_to', '>', day_start)])]
        busy = {employee_id for start, stop, employee_id in taken
                if start < candidates[employee_id][1] and stop > candidates[employee_id][0]}
        # No "created" line in the chatter: the scheduled action would write it in its own language.
        return self.sudo().with_context(mail_create_nolog=True).create([{
            'employee_id': employee_id, 'date_from': start, 'date_to': stop, 'origin': 'check_in',
        } for employee_id, (start, stop) in candidates.items() if employee_id not in busy])

    @api.model
    def _ems_detect_pending_days(self, today):
        """Detects every day since the last one detected, up to yesterday: a day is only over
        once it is no longer today. At most DETECTION_LOOKBACK_DAYS back, and only from yesterday
        on the very first run, so switching the circuit on never reaches into the past."""
        parameters = self.env['ir.config_parameter'].sudo()
        last = fields.Date.to_date(parameters.get_param(DETECTION_MARKER) or False)
        yesterday = today - timedelta(days=1)
        day = max(last + timedelta(days=1), today - timedelta(days=DETECTION_LOOKBACK_DAYS)) if last else yesterday
        while day <= yesterday:
            self._ems_detect_missing_check_ins(day)
            day += timedelta(days=1)
        if not last or last < yesterday:
            parameters.set_param(DETECTION_MARKER, fields.Date.to_string(yesterday))

    @api.model
    def _cron_ems_detected_absences(self):
        """Detects the days just over, then reminds every teacher in the circuit of each
        detected absence of theirs they were asked to justify (issue #707) once it is over, every
        few days, and reports it once to their Head of Studies a few days after the justification
        was requested (both intervals shared with the supporting document reminders, see
        hr.leave._cron_ems_document_reminder). Each message waits for its reader's working day to
        start: never outside their working hours."""
        company = self.env.company
        today = self.get_local_today()
        now = fields.Datetime.now()
        self._ems_detect_pending_days(today)
        domain = company._ems_absence_circuit_domain()
        if domain is None:
            return
        interval = company._ems_absence_document_reminder_days()
        escalation = company._ems_absence_document_escalation_days()
        today_start = self._utc_bounds(today, 0.0, 0.0)[0]
        report_bound = today - timedelta(days=escalation)
        # Only what is due today, so an entry leaves the search once it has been dealt with.
        absences = self.sudo().search([
            ('state', 'in', ASKED_STATES), ('employee_id', 'any', domain), ('date_to', '<=', today_start),
            '|', '|', ('reminder_date', '=', False), ('reminder_date', '<=', today - timedelta(days=interval)),
            '&', ('escalated', '=', False), ('justification_date', '<=', report_bound),
        ])
        started = {}
        for absence in absences:
            absence._ems_remind_at_workday_start(
                absence.employee_id.user_id,
                lambda user, absence=absence: absence.with_context(lang=user.lang)._ems_reminder_message(),
                today, now, started, 'reminder_date', interval)
            if not absence.escalated and absence.justification_date <= report_bound:
                absence._ems_report_at_workday_start(
                    absence.employee_id._find_attendance_approvers(),
                    lambda user, absence=absence: absence.with_context(lang=user.lang)._ems_report_message(),
                    NOT_REQUESTED_ACTIVITY_XMLID, today, now, started, 'escalated')

    def _ems_when(self):
        """The day and hours of the absence, in the company's timezone."""
        self.ensure_one()
        start, stop = self._to_local(self.date_from), self._to_local(self.date_to)
        if start.date() == (stop - timedelta(microseconds=1)).date():
            return _("%(day)s from %(start)s to %(stop)s", day=start.strftime('%d/%m/%Y'),
                     start=start.strftime('%H:%M'), stop=stop.strftime('%H:%M'))
        return _("%(start)s to %(stop)s", start=start.strftime('%d/%m/%Y %H:%M'), stop=stop.strftime('%d/%m/%Y %H:%M'))

    def _ems_reminder_message(self):
        """What the teacher is told: an absence prepared for them, a missing check-in, or an
        absence they announced and have not requested yet."""
        self.ensure_one()
        if self.state == 'absence_prepared':
            return _("An absence request for %(when)s has been prepared for you, as %(type)s. Please "
                     "open it from this page, check it, accept the responsible declaration and send it "
                     "so it can be validated.", when=self._ems_when(), type=self.leave_type_id.name)
        if self.origin == 'check_in':
            return _("No check-in of yours was recorded on %(when)s, and no absence is requested for "
                     "it. If you were absent, please request the absence from this page. If you were "
                     "at the centre and forgot to check in, ask your Head of Studies to record your "
                     "check-in.", when=self._ems_when())
        return _("Your absence on %(when)s was announced, but you have not requested it yet. "
                 "Please request it from this page so it can be validated.", when=self._ems_when())

    @api.model
    def _ems_start_review_circuit(self):
        """Issue #707, for the entries already waiting when the review arrived: those the teacher
        was already reminded of (or reported) carry on as if a justification had been requested
        when the absence ended, so the reminders go on as the teacher expects; the others wait for
        review, with their task."""
        Pending = self.sudo().with_context(active_test=False)
        reminded = Pending.search([('state', '=', 'pending'), '|', ('reminder_date', '!=', False), ('escalated', '=', True)])
        for absence in reminded:
            absence.write({'state': 'justification_requested', 'justification_date': (
                absence._to_local(absence.date_to) - timedelta(microseconds=1)).date()})
        Pending.search([('state', '=', 'pending')])._ems_schedule_review()

    def _ems_report_message(self):
        """What the teacher's Head of Studies is told once it has gone on for too long."""
        self.ensure_one()
        if self.origin == 'check_in':
            return _("%(name)s has still not requested an absence for %(when)s, when no check-in of "
                     "theirs was recorded.", name=self.employee_id.name, when=self._ems_when())
        return _("%(name)s has still not requested the absence of %(when)s that was announced.",
                 name=self.employee_id.name, when=self._ems_when())


class EmsAbsencePendingLeave(models.Model):
    _name = "hr.leave"
    # The guard duty board reloads when an absence changes (issue #692).
    _inherit = ["hr.leave", "ems.guard_board_notifier"]
    _guard_board_fields = ("employee_id", "state", "request_date_from", "request_date_to", "request_hour_from",
                           "request_hour_to", "request_unit_hours", "ems_full_day")

    ems_pending_absence_ids = fields.One2many(
        string="Detected absences", comodel_name="ems.absence_pending", inverse_name="leave_id",
        readonly=True, groups="ems.group_head_of_studies")

    def _ems_utc_range(self):
        """(start, stop) as naive UTC datetimes, read the same way the guard duty board does: the
        requested hours for a partial one-day absence, whole days in the company's timezone
        otherwise. Not Odoo's own date_from/date_to, which clip a whole day to the employee's
        working hours."""
        self.ensure_one()
        Pending = self.env['ems.absence_pending']
        partial = self.request_unit_hours and self.request_date_from == self.request_date_to
        if partial:
            return Pending._utc_bounds(self.request_date_from, self.request_hour_from, self.request_hour_to)
        start, _stop = Pending._utc_bounds(self.request_date_from, 0.0, 24.0)
        _start, stop = Pending._utc_bounds(self.request_date_to, 0.0, 24.0)
        return start, stop

    @api.model_create_multi
    def create(self, vals_list):
        leaves = super().create(vals_list)
        self.env['ems.absence_pending']._link_to_leaves(leaves)
        return leaves

    def write(self, vals):
        result = super().write(vals)
        if vals.keys() & {'employee_id', 'state', 'request_date_from', 'request_date_to',
                          'request_hour_from', 'request_hour_to', 'ems_full_day'}:
            self.env['ems.absence_pending']._link_to_leaves(self)
        return result

    def _guard_board_spans(self):
        return {(leave.request_date_from, leave.request_date_to) for leave in self}


class EmsAbsencePendingAttendance(models.Model):
    _inherit = "hr.attendance"

    @api.model_create_multi
    def create(self, vals_list):
        attendances = super().create(vals_list)
        attendances._ems_review_detected_absences()
        return attendances

    def write(self, vals):
        result = super().write(vals)
        if vals.keys() & {'employee_id', 'check_in'}:
            self._ems_review_detected_absences()
        return result

    @api.model
    def _ems_first_check_in_hours(self, day, employees):
        """`{employee.id: hour}`: each employee's first check-in on `day`, a float hour in the
        company's timezone, leaving out the technical attendances Odoo's own absence detection
        creates (they are no presence). One query for every employee. sudo: whoever reads the
        guard duty board, and the detected absences, need to know whether a colleague is in, and
        only that hour leaves this method."""
        utils = self.env['ems.datetime_utils']
        day_start, day_end = (utils.datetime_to_odoo(utils.time_float_to_utc_datetime(when, 0.0))
                              for when in (day, day + timedelta(days=1)))
        check_ins = self.sudo()._read_group(
            [('employee_id', 'in', employees.ids), ('check_in', '>=', day_start), ('check_in', '<', day_end),
             ('in_mode', '!=', 'technical')],
            ['employee_id'], ['check_in:min'])
        return {employee.id: utils.time_to_float(utils.utc_datetime_to_local(first.replace(tzinfo=UTC)))
                for employee, first in check_ins}

    def _ems_review_detected_absences(self):
        """A check-in recorded afterwards (checked in from the guard duty board, by their Head of
        Studies, a correction) reviews that day's detected absence of the teacher (issue #696):
        discarded when nothing is missing any more, shortened when they arrived earlier than it
        said."""
        attendances = self.filtered(lambda attendance: attendance.check_in and attendance.in_mode != 'technical')
        if not attendances:
            return
        Pending = self.env['ems.absence_pending'].sudo()
        days = {(attendance.employee_id.id, Pending._to_local(attendance.check_in).date()) for attendance in attendances}
        absences = Pending.search([
            ('origin', '=', 'check_in'), ('state', 'in', UNRESOLVED_STATES),
            ('employee_id', 'in', attendances.employee_id.ids),
            ('date_from', '<', max(attendances.mapped('check_in')) + timedelta(days=1)),
            ('date_to', '>', min(attendances.mapped('check_in')) - timedelta(days=1)),
        ])
        for absence in absences:
            day = Pending._to_local(absence.date_from).date()
            if (absence.employee_id.id, day) not in days:
                continue
            missing = Pending._ems_missing_check_ins(day, absence.employee_id).get(absence.employee_id.id)
            if not missing:
                absence.state = 'discarded'
                absence.message_post(body=_("Discarded: the teacher's check-in of that day has been recorded."),
                                     subtype_xmlid='mail.mt_note')
            else:
                date_to = Pending._utc_bounds(day, *missing)[1]
                if date_to < absence.date_to:
                    absence.date_to = date_to
