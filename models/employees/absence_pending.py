# -*- coding: utf-8 -*-

from collections import defaultdict
from datetime import time, timedelta

from pytz import UTC

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

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


class EmsAbsencePending(models.Model):
    """A teacher's absence nobody has requested yet (issue #509, renamed "detected absence" in
    issue #696). Either informed: the teacher's Department or Seminar Chief (issue #604), the Head
    of Studies or their Deputy already knows it is coming and enters it on the teacher's behalf;
    or detected at the end of the day from a missing check-in (issue #696). The guard duty board
    plans around it, and the teacher is reminded to request it: once the teacher's own absence is
    filed, the two are linked for good and the real one is all that counts from then on."""
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
        selection=[('pending', 'Detected'), ('linked', 'Requested'), ('discarded', 'Discarded')],
        default='pending', required=True, readonly=True, copy=False, tracking=True,
        help="Detected until the teacher requests the absence themselves, then linked to their "
             "request for good: from that moment only the request counts, whatever becomes of it. "
             "Discarded when the teacher's check-in of that day shows up after all.")
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

    def _domain_employee_id(self):
        """The same reach as the record rules: every teacher for a technical administrator
        (rule_absence_pending_system), otherwise the user's own branch of the hierarchy or the
        teachers of the departments they head or lead as Seminar Chief, and of those under the areas
        they manage (rule_absence_pending_hierarchy, issue #569), or whoever teaches a group one
        of those departments manages or is also managed by one of them (issue #622)."""
        domain = [('employee_type', '=', 'teacher')]
        if self.env.user.has_group('base.group_system'):
            return domain
        employees = self.env.user.employee_ids
        departments = employees.headed_department_ids | employees.seminar_department_ids
        return domain + [
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
        """Only the teacher themselves requests their absence, and only while nobody has."""
        for absence in self:
            absence.can_request = absence.state == 'pending' and absence.employee_id.user_id == self.env.user

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for absence in self:
            if absence.date_to <= absence.date_from:
                raise ValidationError(_("The end of an absence must come after its start."))

    def write(self, vals):
        if vals.keys() & {'employee_id', 'date_from', 'date_to'}:
            states = set(self.mapped('state'))
            if 'linked' in states:
                raise ValidationError(_("This absence has already been requested by the teacher: "
                                        "only their own request counts now."))
            if 'discarded' in states:
                raise ValidationError(_("This absence was discarded: the teacher's check-in of "
                                        "that day showed up."))
        result = super().write(vals)
        if vals.get('state') in ('linked', 'discarded'):
            # Nothing is left to follow up on its Head of Studies' list.
            self.sudo().activity_feedback([NOT_REQUESTED_ACTIVITY_XMLID])
        return result

    def action_request_absence(self):
        """Opens a new absence request of the teacher's own, filled in with this one's day and
        hours. Saving it links the two (_link_to_leaves)."""
        self.ensure_one()
        start, stop = self._to_local(self.date_from), self._to_local(self.date_to)
        last_day = (stop - timedelta(microseconds=1)).date()
        context = {
            'default_employee_id': self.employee_id.id,
            'default_request_date_from': start.date(),
            'default_request_date_to': last_day,
        }
        if start.date() == last_day:
            context.update({
                'default_ems_full_day': False,
                'default_request_hour_from': self.time_to_float(start),
                'default_request_hour_to': self.time_to_float(stop) if stop.date() == last_day else 24.0,
            })
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
        """Links every pending entry to the teacher's own absence overlapping it. sudo(): the
        teacher filing that absence has no access to this model at all, which is the point of
        it."""
        Pending = self.sudo()
        for leave in leaves.filtered(lambda leave: leave.state in ACTIVE_LEAVE_STATES):
            start, stop = leave._ems_utc_range()
            Pending.search([
                ('state', '=', 'pending'),
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
        detected absence of theirs still not requested once it is over, every few days, and
        reports it once to their Head of Studies a few days after it (both intervals shared with
        the supporting document reminders, see hr.leave._cron_ems_document_reminder). Each
        message waits for its reader's working day to start: never outside their working hours."""
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
        report_bound = self._utc_bounds(today - timedelta(days=escalation - 1), 0.0, 0.0)[0]
        # Only what is due today, so an entry leaves the search once it has been dealt with.
        absences = self.sudo().search([
            ('state', '=', 'pending'), ('employee_id', 'any', domain), ('date_to', '<=', today_start),
            '|', '|', ('reminder_date', '=', False), ('reminder_date', '<=', today - timedelta(days=interval)),
            '&', ('escalated', '=', False), ('date_to', '<=', report_bound),
        ])
        started = {}
        for absence in absences:
            absence._ems_remind_at_workday_start(
                absence.employee_id.user_id,
                lambda user, absence=absence: absence.with_context(lang=user.lang)._ems_reminder_message(),
                today, now, started, 'reminder_date', interval)
            if not absence.escalated and absence.date_to <= report_bound:
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
        """What the teacher is told: a missing check-in is not the same as an absence they
        announced and have not requested yet."""
        self.ensure_one()
        if self.origin == 'check_in':
            return _("No check-in of yours was recorded on %(when)s, and no absence is requested for "
                     "it. If you were absent, please request the absence from this page. If you were "
                     "at the centre and forgot to check in, ask your Head of Studies to record your "
                     "check-in.", when=self._ems_when())
        return _("Your absence on %(when)s was announced, but you have not requested it yet. "
                 "Please request it from this page so it can be validated.", when=self._ems_when())

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
            ('origin', '=', 'check_in'), ('state', '=', 'pending'),
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
