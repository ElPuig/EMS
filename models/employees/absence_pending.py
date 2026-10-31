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
UNRESOLVED_STATES = ('pending', 'justification_requested', 'absence_prepared', 'correction_requested')
# The teacher has been asked to act: reminded until they do.
ASKED_STATES = ('justification_requested', 'absence_prepared')
# Linked to an absence request of the teacher's (issue #735): in progress, or approved for good.
REQUESTED_STATES = ('linked', 'justified')
# An absence request approved for good: the detected absence is justified.
APPROVED_LEAVE_STATE = 'validate'


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
        selection=[('pending', 'To review'), ('justification_requested', 'Action requested'),
                   ('absence_prepared', 'Justification prepared'), ('correction_requested', 'Correction requested'),
                   ('corrected', 'Check-in corrected'), ('linked', 'Requested'), ('justified', 'Justified'),
                   ('discarded', 'Discarded')],
        default='pending', required=True, readonly=True, copy=False, tracking=True,
        help="To review: the Head of Studies decides what to do with it; the teacher is not told. "
             "Action requested: the teacher is reminded to request the absence or a check-in "
             "correction. Justification prepared: the same, with the absence request prepared for them. "
             "Correction requested: the teacher's check-in correction waits for a decision. Check-in "
             "corrected: the teacher was at the centre. Requested: the teacher's absence request is "
             "being dealt with. Justified: it was approved. Discarded: by the reviewer, or because "
             "the teacher's check-in of that day showed up after all. A refused absence request or a "
             "rejected correction sends it back to review.")
    # Readonly so that Odoo offers no Archive/Unarchive of its own: Discard is the only way, with
    # its checks and its note (issue #707).
    active = fields.Boolean(default=True, readonly=True, help="Archived when the reviewer discards it.")
    # Issue #707: "Prepare justification" prepares the request for the teacher, never files it: only the
    # teacher accepts the responsible declaration and sends it.
    leave_type_id = fields.Many2one(
        string="Absence type", comodel_name="hr.leave.type", readonly=True, copy=False,
        help="Chosen by the Head of Studies: the teacher's request opens with it.")
    justification_date = fields.Date(
        string="Teacher notified on", readonly=True, copy=False,
        help="The day the Head of Studies asked the teacher for a justification or prepared the absence for them: "
             "the reminders to the teacher and the report to their Head of Studies count from it.")
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
    # Issue #735: the teacher, asked to justify it, may answer that they were at the centre.
    can_request_correction = fields.Boolean(string="Can request a check-in correction", compute="_compute_can_request")
    status_path = fields.Char(string="Status steps", compute="_compute_status_path")
    correction_ids = fields.One2many(
        string="Check-in correction requests", comodel_name="ems.attendance_correction",
        inverse_name="absence_pending_id", readonly=True)
    is_own = fields.Boolean(string="Is own", compute="_compute_is_own")
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

    @api.depends('state', 'employee_id', 'date_to')
    @api.depends_context('uid')
    def _compute_can_request(self):
        """Only the teacher themselves requests their absence, once asked to and while nobody has,
        or a correction of their check-in instead, once the absence is over (issue #735). Neither
        while a correction they requested waits for a decision: they already said they were at
        the centre."""
        now = fields.Datetime.now()
        for absence in self:
            absence.can_request = absence.state in ASKED_STATES and absence.employee_id.user_id == self.env.user
            absence.can_request_correction = absence.can_request and absence.date_to <= now

    @api.depends('employee_id')
    @api.depends_context('uid')
    def _compute_is_own(self):
        """The teacher reading their own entry: their status bar has no "To review" step, a stage
        they never see (issue #707)."""
        for absence in self:
            absence.is_own = bool(absence.employee_id.user_id) and absence.employee_id.user_id == self.env.user

    @api.depends('state', 'justification_date', 'leave_type_id', 'employee_id', 'correction_ids.state')
    @api.depends_context('uid')
    def _compute_status_path(self):
        """The steps the status bar shows (issue #735): those this entry went through, ending in
        its state, then the ones still ahead. The review first, which the teacher never sees;
        then, if the teacher was asked to act, how (justification_date says it was asked,
        leave_type_id that the absence was prepared); then the way they answered, a check-in
        correction (requested, corrected) or an absence request (requested, justified once
        approved). Comma-separated, for the ems_statusbar_path widget."""
        ahead = {'pending': ['justification_requested', 'linked', 'justified'],
                 'justification_requested': ['linked', 'justified'], 'absence_prepared': ['linked', 'justified'],
                 'correction_requested': ['corrected'], 'linked': ['justified']}
        for absence in self:
            state = absence.state
            steps = [] if absence.is_own else ['pending']
            if absence.justification_date or state in ASKED_STATES:
                steps.append('absence_prepared' if absence.leave_type_id else 'justification_requested')
            if state == 'correction_requested' or (
                    state == 'corrected' and 'accepted' in absence.sudo().correction_ids.mapped('state')):
                steps.append('correction_requested')
            if state == 'justified':
                steps.append('linked')
            steps.append(state)
            steps += [step for step in ahead.get(state, []) if step not in steps]
            absence.status_path = ','.join(dict.fromkeys(steps))

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
        # A part split from an entry already reviewed is not reviewed again (_ems_split).
        absences.filtered(lambda absence: absence.state == 'pending')._ems_schedule_review()
        return absences

    def write(self, vals):
        if vals.keys() & {'employee_id', 'date_from', 'date_to'}:
            states = set(self.mapped('state'))
            if states & set(REQUESTED_STATES):
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

    @api.model
    def _ems_close_dialog(self, result):
        """What a review dialog returns: closing it reloads whatever opened it, showing on the
        way the notice of what _ems_review skipped, if any."""
        close = {'type': 'ir.actions.act_window_close'}
        if result.get('tag') != 'display_notification':
            return close
        result['params']['next'] = close
        return result

    def _ems_post_review_note(self, message):
        for absence in self.sudo():
            absence.message_post(body=message, subtype_xmlid='mail.mt_note')

    def _ems_ask_teacher(self, values, note):
        """The teacher is asked to act: the reminders start (see _cron_ems_detected_absences),
        counted from today."""
        self.sudo().write({**values, 'justification_date': self.get_local_today(),
                           'reminder_date': False, 'escalated': False})
        self._ems_post_review_note(note)

    def _ems_ask_to_act(self, leave_type=None, when=None):
        """Request action, or Prepare justification with `leave_type` (issue #735): the teacher is
        asked to regularize these entries, with the absence request prepared for them if a type
        is given. `when`: the hours chosen, when only part of the entry was."""
        user = self.env.user.name
        if leave_type:
            values = {'state': 'absence_prepared', 'leave_type_id': leave_type.id}
            note = (_("Justification prepared by %(user)s for %(when)s. The rest is still to review.", user=user, when=when)
                    if when else _("Justification prepared by %(user)s.", user=user))
        else:
            values = {'state': 'justification_requested'}
            note = (_("Action requested by %(user)s for %(when)s. The rest is still to review.", user=user, when=when)
                    if when else _("Action requested by %(user)s.", user=user))
        self._ems_ask_teacher(values, note)

    def action_request_justification(self):
        """Request action: the teacher is asked to regularize it, requesting the absence or a
        check-in correction."""
        return self._ems_review(lambda absences: absences._ems_ask_to_act())

    def _ems_check_correctable(self, absence):
        return absence.date_to > fields.Datetime.now() and _("still going on")

    def _ems_fill_attendances(self, spans, start, stop):
        """Completes the teacher's attendance in the part of `spans` (_ems_uncovered_spans, read
        beforehand) between `start` and `stop`, leaving their own attendances as they are."""
        self.ensure_one()
        self.env['hr.attendance'].sudo().create([{
            'employee_id': self.employee_id.id, 'check_in': max(span_start, start), 'check_out': min(span_stop, stop),
            'in_mode': 'manual', 'out_mode': 'manual', 'ems_checked_in_by_id': self.env.uid,
        } for span_start, span_stop in spans if span_start < stop and span_stop > start])

    def action_correct_check_in(self):
        """The teacher was at the centre: their attendance is completed for the hours detected,
        without telling anyone."""
        def apply(absences):
            for absence in absences:
                spans = absence._ems_uncovered_spans()
                # Before the attendances: the check-in review they cause must not discard it.
                absence.sudo().state = 'corrected'
                absence._ems_fill_attendances(spans, absence.date_from, absence.date_to)
            absences._ems_post_review_note(_("Check-in corrected by %(user)s.", user=self.env.user.name))
        return self._ems_review(apply, self._ems_check_correctable)

    def _ems_open_review_dialog(self, decision, title):
        """The form's review decisions (issues #731, #735) ask for the hours they apply to, the
        whole entry by default (ems.absence_pending.review_wizard)."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': title,
            'res_model': 'ems.absence_pending.review_wizard',
            'views': [(False, 'form')],
            'target': 'new',
            'context': {'default_absence_id': self.id, 'default_decision': decision,
                        'default_date_from': self.date_from, 'default_date_to': self.date_to},
        }

    def action_open_request_action(self):
        return self._ems_open_review_dialog('request', _("Request action"))

    def action_open_prepare_justification(self):
        return self._ems_open_review_dialog('prepare', _("Prepare justification"))

    def action_open_correct_check_in(self):
        return self._ems_open_review_dialog('correct', _("Correct check-in"))

    def _ems_review_range(self, decision, start, stop, leave_type=None):
        """The reviewer's `decision` (request, prepare or correct) on this entry between `start`
        and `stop` only: the rest, before and after, is still to review, as one entry or two
        (issues #731, #735). The whole entry is the usual decision."""
        self.ensure_one()
        if start <= self.date_from and stop >= self.date_to:
            if decision == 'correct':
                return self.action_correct_check_in()
            return self._ems_review(lambda absences: absences._ems_ask_to_act(leave_type))
        user = self.env.user.name

        def apply(absence):
            when = _("%(start)s to %(stop)s", start=self._to_local(start).strftime('%H:%M'),
                     stop=self._to_local(stop).strftime('%H:%M'))
            rest = [span for span in ((absence.date_from, start), (stop, absence.date_to)) if span[0] < span[1]]
            if decision == 'correct':
                spans = absence._ems_uncovered_spans()
                # Before the attendances: the check-in review they cause must not touch what is left.
                absence._ems_split(rest, _("check-in corrected by %(user)s from %(when)s.", user=user, when=when))
                absence._ems_fill_attendances(spans, start, stop)
                absence._ems_post_review_note(_("Check-in corrected by %(user)s from %(when)s. The rest is still to review.",
                                                user=user, when=when))
                return
            # The entry keeps the hours chosen; its copies, the rest, wait for review with their own task.
            absence._ems_split([(start, stop)] + rest, _("the rest of a decision by %(user)s for %(when)s.",
                                                         user=user, when=when))
            absence._ems_ask_to_act(leave_type, when)
        return self._ems_review(apply, self._ems_check_correctable if decision == 'correct' else None)

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
        return self._ems_review(lambda absences: absences._ems_ask_to_act(leave_type))

    def _ems_uncovered_spans(self, covered=()):
        """[(start, stop)] of this entry's span that none of the teacher's attendances covers, nor
        any of `covered` [(start, stop)] (an absence request's span, issue #735)."""
        self.ensure_one()
        attendances = self.env['hr.attendance'].sudo().search([
            ('employee_id', '=', self.employee_id.id), ('check_in', '<', self.date_to),
            '|', ('check_out', '=', False), ('check_out', '>', self.date_from)], order='check_in')
        busy = sorted([(attendance.check_in, attendance.check_out or self.date_to) for attendance in attendances]
                      + list(covered))
        spans, cursor = [], self.date_from
        for start, stop in busy:
            if start > cursor:
                spans.append((cursor, min(start, self.date_to)))
            cursor = max(cursor, stop)
        if cursor < self.date_to:
            spans.append((cursor, self.date_to))
        return [(start, stop) for start, stop in spans if start < stop]

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

    def _ems_attendance_to_correct(self):
        """The teacher's attendance a correction request of this entry is about, never chosen by
        the teacher (issue #735), on the day it starts in the company's timezone: the first one
        from the entry's start on (a late arrival: the one the entry ends at), otherwise the last
        one before it; with none, the technical one Odoo's absence detection leaves on a day
        without check-in (the one shown in red, which teachers have always asked to correct);
        otherwise none, and accepting the request records one."""
        self.ensure_one()
        start, stop = self._utc_bounds(self._to_local(self.date_from).date(), 0.0, 24.0)
        attendances = self.env['hr.attendance'].sudo().search([
            ('employee_id', '=', self.employee_id.id), ('check_in', '>=', start), ('check_in', '<', stop)],
            order='check_in')
        real = attendances.filtered(lambda attendance: attendance.in_mode != 'technical')
        after = real.filtered(lambda attendance: attendance.check_in >= self.date_from)
        return after[:1] or real[-1:] or attendances[:1]

    def _ems_check_correction_requestable(self):
        """Checked on the server whatever the screen offered (issue #735)."""
        self.ensure_one()
        if not self.can_request_correction:
            raise UserError(_("A check-in correction can only be requested by the teacher, for a detected absence "
                              "they were asked to regularize, once it is over and while no other one is pending."))

    def action_request_check_in_correction(self):
        """Issue #735: the teacher was at the centre. Opens a correction request of their attendance
        that day (_ems_attendance_to_correct), or of the day itself when they have none: the
        approver accepting it records the attendance, and that resolves this entry."""
        self.ensure_one()
        self._ems_check_correction_requestable()
        context = {'default_absence_pending_id': self.id}
        attendance = self._ems_attendance_to_correct()
        if attendance:
            context['default_attendance_id'] = attendance.id
        return {
            'type': 'ir.actions.act_window',
            'name': _("Request check-in correction"),
            'res_model': 'ems.attendance_correction',
            'views': [(False, 'form')],
            'target': 'new',
            'context': context,
        }

    def _ems_resolve_by_correction(self):
        """The teacher's correction request was accepted (issue #735): corrected once their
        attendance covers it (a detected one, what still holds a whole period, as its review reads
        it), otherwise it keeps what is still missed."""
        absence = self.sudo()
        if absence.state not in UNRESOLVED_STATES:
            return
        if absence._ems_carve([], {'state': 'corrected'}, _("its check-in was corrected for part of it.")):
            absence._ems_post_review_note(_("Check-in corrected: %(user)s accepted the teacher's correction request.",
                                            user=self.env.user.name))

    def _ems_left_spans(self, covered=()):
        """What of this entry is still to regularize besides `covered` and the teacher's
        attendances: for a detected one, what still holds a whole period of their schedule
        (_ems_missed_spans); for an informed one, whatever is left uncovered."""
        self.ensure_one()
        return self._ems_missed_spans(covered) if self.origin == 'check_in' else self._ems_uncovered_spans(covered)

    def _ems_carve(self, covered, values, note):
        """Issue #735: the part of this entry `covered` and the teacher's attendances resolve gets
        `values` (linked to an absence request, corrected); what is still left keeps its stage,
        as copies (_ems_split, `note` on them). The resolved part stays this very entry, so
        whatever points at it (its request, its correction) still does, and dropping that later
        reopens only what it resolved. Returns whether anything was resolved."""
        self.ensure_one()
        left = self._ems_left_spans(covered)
        if left == [(self.date_from, self.date_to)]:
            return False
        resolved, cursor = [], self.date_from
        for start, stop in left:
            if start > cursor:
                resolved.append((cursor, start))
            cursor = stop
        if cursor < self.date_to:
            resolved.append((cursor, self.date_to))
        stage = {'state': self._ems_stage()}
        self._ems_split([(start, stop, values) for start, stop in resolved]
                        + [(start, stop, stage) for start, stop in left], note)
        return True

    def _ems_stage(self):
        """The stage of the review this entry is at, leaving aside a correction of the teacher's
        waiting for a decision (issue #735): a part split off it is not what that correction is
        about, so it goes back to where the entry stood before it."""
        self.ensure_one()
        if self.state != 'correction_requested':
            return self.state
        return ('absence_prepared' if self.leave_type_id
                else 'justification_requested' if self.justification_date else 'pending')

    def _ems_reopen(self, reason):
        """Issue #735: what resolved these entries fell through (an absence request refused,
        cancelled, deleted or moved away; a check-in correction rejected): they go back to the
        review, as new, `reason` in their chatter. The teacher hears nothing until asked again."""
        entries = self.sudo().with_context(active_test=False).filtered(lambda absence: absence.state != 'pending')
        if not entries:
            return
        entries.write({'state': 'pending', 'active': True, 'leave_id': False, 'leave_type_id': False,
                       'justification_date': False, 'reminder_date': False, 'escalated': False})
        entries._ems_post_review_note(reason)
        entries._ems_schedule_review()

    @api.model
    def _ems_entry_for_correction(self, attendance):
        """Issue #735: the teacher's entry still unresolved on the day of `attendance` (company's
        timezone), which a correction of it answers whatever way it was asked for."""
        if not attendance.check_in:
            return self.browse()
        start, stop = self._utc_bounds(self._to_local(attendance.check_in).date(), 0.0, 24.0)
        return self.sudo().search([
            ('employee_id', '=', attendance.employee_id.id), ('state', 'in', UNRESOLVED_STATES),
            ('date_from', '<', stop), ('date_to', '>', start)], order='date_from', limit=1)

    def action_request_absence(self):
        """Opens a new absence request of the teacher's own, filled in with this one's day and
        hours. Saving it links the two (_link_to_leaves)."""
        self.ensure_one()
        if not self.can_request:
            # Checked on the server whatever the screen offered (issue #735).
            raise UserError(_("Only the teacher can request this absence, once asked to regularize it and while no "
                              "check-in correction of theirs is waiting for a decision."))
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
            entries = Pending.search([
                ('state', 'in', UNRESOLVED_STATES),
                ('employee_id', '=', leave.employee_id.id),
                ('date_from', '<', stop),
                ('date_to', '>', start),
            ])
            # Issue #735: the absence answers it; a check-in correction still waiting is withdrawn.
            entries.correction_ids.filtered(lambda correction: correction.state == 'pending')._withdraw()
            # Only the part it covers: the rest is still to regularize.
            state = 'justified' if leave.state == APPROVED_LEAVE_STATE else 'linked'
            for entry in entries:
                entry._ems_carve([(start, stop)], {'state': state, 'leave_id': leave.id},
                                 _("the absence request %(leave)s covers part of it.", leave=leave.display_name))

    @api.model
    def _ems_relink(self, leaves):
        """Issue #735: `leaves` changed. The entries one of them resolved and no longer covers
        (refused, cancelled, moved to another day or teacher) go back to the review; then the
        active ones link what they cover."""
        for entry in self.sudo().search([('leave_id', 'in', leaves.ids), ('state', 'in', REQUESTED_STATES)]):
            leave = entry.leave_id
            start, stop = leave._ems_utc_range()
            if (leave.state not in ACTIVE_LEAVE_STATES or leave.employee_id != entry.employee_id
                    or not (entry.date_from < stop and entry.date_to > start)):
                entry._ems_reopen(_("Reopened: the absence request %(leave)s no longer covers it.",
                                    leave=leave.display_name))
                continue
            # Justified once the request is approved for good, back to Requested if that is undone.
            state = 'justified' if leave.state == APPROVED_LEAVE_STATE else 'linked'
            if entry.state != state:
                entry.state = state
        self._link_to_leaves(leaves)

    @api.model
    def _ems_detect_dropped(self, spans):
        """Issue #735: the days an absence request covered and no longer does [(employee, first
        day, last day)] are detected again for that teacher, as the end of the day would have: a
        request filed beforehand kept them out of the detection, so a refused one would never be
        claimed otherwise. Only the days the detection has already been through (from the first
        detected absence to its last detected day): the later ones it reaches on its own."""
        last = fields.Date.to_date(self.env['ir.config_parameter'].sudo().get_param(DETECTION_MARKER) or False)
        first = self.sudo().search([('origin', '=', 'check_in')], order='date_from', limit=1)
        if not last or not first:
            return
        first_day = self._to_local(first.date_from).date()
        for employee, day_from, day_to in spans:
            day = max(day_from, first_day)
            while day <= min(day_to, last):
                self._ems_detect_missing_check_ins(day, employee)
                day += timedelta(days=1)

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
    def _ems_scheduled_periods(self, day, employees):
        """`{employee.id: [(hour_from, hour_to)]}`: each of `employees`' own schedule periods on
        `day`, in the company's hours, read as the guard duty board reads them (no lunch, the
        right week of a two-week schedule). sudo: only hours leave this method."""
        week_type = str(self.env['resource.calendar.attendance'].get_week_type(day))
        slots = self.env['ems.course'].sudo()._get_guard_duty_board_attendance_ids([
            ('dayofweek', '=', str(day.weekday())), ('calendar_id.employee_id', 'in', employees.ids),
            ('display_type', '=', False), ('day_period', '!=', 'lunch')])
        periods = defaultdict(list)
        for slot in slots:
            if not (slot.two_weeks_calendar and slot.week_type != week_type):
                periods[slot.calendar_id.employee_id.id].append((slot.hour_from, slot.hour_to))
        return periods

    def _ems_missed_spans(self, covered=()):
        """[(start, stop)] of this entry no attendance covers and that still hold a whole period
        of the teacher's schedule: being there for part of a period is no absence, the same rule
        the detection follows for a late arrival (issue #731). Without a schedule that day, every
        span left uncovered."""
        self.ensure_one()
        day = self._to_local(self.date_from).date()
        periods = [self._utc_bounds(day, *hours)
                   for hours in self._ems_scheduled_periods(day, self.employee_id).get(self.employee_id.id, [])]
        spans = self._ems_uncovered_spans(covered)
        if not periods:
            return spans
        return [(start, stop) for start, stop in spans
                if any(start <= period_start and period_stop <= stop for period_start, period_stop in periods)]

    def _ems_keep_missed_spans(self):
        """Keeps only what the teacher's attendances leave missed (_ems_missed_spans): shortened,
        split, or discarded when nothing is left. Returns whether something is left."""
        self.ensure_one()
        spans = self._ems_missed_spans()
        if not spans:
            self.sudo().state = 'discarded'
            self.sudo().message_post(body=_("Discarded: the teacher's attendance covers it."),
                                     subtype_xmlid='mail.mt_note')
            return False
        if spans != [(self.date_from, self.date_to)]:
            self._ems_split(spans, _("the teacher's attendance covers part of it."))
        return True

    def _ems_split(self, spans, note):
        """This entry keeps the first of `spans` and a copy of it (same teacher, origin and stage
        of the review) takes each of the others; `note` on the copies, which tells where they come
        from. Whoever followed the entry follows its copies too. Only an entry still to review
        gets its review task (create). A span may carry values of its own as a third item (issue
        #735: the part an absence request or a correction resolves)."""
        self.ensure_one()
        source = self.display_name
        base = {
            'employee_id': self.employee_id.id, 'origin': self.origin, 'state': self._ems_stage(),
            'leave_type_id': self.leave_type_id.id, 'note': self.sudo().note,
            'justification_date': self.justification_date, 'reminder_date': self.reminder_date,
            'escalated': self.escalated,
        }
        parts = [(span[0], span[1], span[2] if len(span) > 2 else {}) for span in spans]
        start, stop, values = parts[0]
        self.sudo().write({'date_from': start, 'date_to': stop, **values})
        if len(parts) == 1:
            return self.browse()
        copies = self.sudo().with_context(mail_create_nolog=True).create([
            {**base, 'date_from': start, 'date_to': stop, **values} for start, stop, values in parts[1:]])
        for copy in copies:
            copy.message_subscribe(partner_ids=self.sudo().message_partner_ids.ids)
            copy.message_post(body=_("Split from %(entry)s: %(reason)s", entry=source, reason=note),
                              subtype_xmlid='mail.mt_note')
        return copies

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
        periods = self._ems_scheduled_periods(day, employees)
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
    def _ems_detect_missing_check_ins(self, day, employees=None):
        """Turns `day`'s missing check-ins of the teachers in the circuit (the areas chosen in the
        settings) into detected absences. Nothing on a public holiday, nor on a day nobody in the
        circuit checked in (a school holiday the calendar does not know about, the summer), nor
        where the teacher already has an absence or a detected absence overlapping it. Only those
        of `employees` when given (issue #735), the rest of the circuit still telling whether it
        was a school day."""
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
        if employees is not None:
            teachers &= employees.sudo()
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
                     "at the centre and forgot to check in, request a check-in correction from this "
                     "page.", when=self._ems_when())
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

    @api.model
    def _ems_reopen_dropped_requests(self):
        """Issue #735, for the entries linked before it: those whose absence request was refused,
        cancelled or deleted since go back to the review."""
        Pending = self.sudo()
        Pending.search([('state', '=', 'linked'), '|', ('leave_id', '=', False),
                        ('leave_id.state', 'not in', ACTIVE_LEAVE_STATES)])._ems_reopen(
            _("Reopened: the absence request that resolved it was refused, cancelled or deleted."))
        Pending.search([('state', '=', 'linked'), ('leave_id.state', '=', APPROVED_LEAVE_STATE)]).write(
            {'state': 'justified'})

    @api.model
    def _ems_reopen_wrongly_discarded(self):
        """Issue #731, for the entries discarded before it: a check-in recorded afterwards
        discarded them as soon as it fell on their day, even outside their hours. Those a check-in
        discarded (still active: a reviewer's discard archives) come back at the stage of the
        review they had reached, keeping only what is still missed (_ems_keep_missed_spans); the
        teacher's reminders, if they had been asked, count from today. Nobody is told."""
        today = self.get_local_today()
        for absence in self.sudo().search([('origin', '=', 'check_in'), ('state', '=', 'discarded')]):
            spans = absence._ems_missed_spans()
            if not spans:
                continue
            # The stage they had reached: Prepare justification sets the type, both requests the date.
            state = ('absence_prepared' if absence.leave_type_id
                     else 'justification_requested' if absence.justification_date else 'pending')
            # Written without write(): it would mark the entry's tasks done again.
            absence.env.cr.execute("UPDATE ems_absence_pending SET state = %s WHERE id = %s", (state, absence.id))
            absence.invalidate_recordset(['state'])
            if state != 'pending':
                absence.write({'justification_date': today, 'reminder_date': False, 'escalated': False})
            # Its copies, if split, get their own review task when created.
            absence._ems_split(spans, _("the teacher's attendance covers part of it."))
            if state == 'pending':
                absence._ems_schedule_review()
            absence.message_post(body=_("Reopened: it had been discarded by a check-in outside its hours."),
                                 subtype_xmlid='mail.mt_note')

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
        watched = vals.keys() & {'employee_id', 'state', 'request_date_from', 'request_date_to',
                                 'request_hour_from', 'request_hour_to', 'ems_full_day'}
        # Issue #735: the days it covered, detected again if it no longer covers them.
        dropped = [(leave.employee_id, leave.request_date_from, leave.request_date_to) for leave in self
                   ] if watched - {'state'} or vals.get('state', 'confirm') not in ACTIVE_LEAVE_STATES else []
        result = super().write(vals)
        if watched:
            Pending = self.env['ems.absence_pending']
            Pending._ems_relink(self)
            Pending._ems_detect_dropped(dropped)
        return result

    def unlink(self):
        """Issue #735: what it resolved goes back to the review, and its days are detected again."""
        Pending = self.env['ems.absence_pending'].sudo()
        entries = Pending.search([('leave_id', 'in', self.ids), ('state', 'in', REQUESTED_STATES)])
        dropped = [(leave.employee_id, leave.request_date_from, leave.request_date_to) for leave in self]
        result = super().unlink()
        entries._ems_reopen(_("Reopened: the absence request that resolved it was deleted."))
        Pending._ems_detect_dropped(dropped)
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
        if vals.keys() & {'employee_id', 'check_in', 'check_out'}:
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
        """An attendance recorded afterwards (checked in from the guard duty board, by their Head
        of Studies, a correction) reviews the teacher's detected absences it overlaps (issue #696):
        each keeps only what is still missed (_ems_missed_spans), shortened at either end, split
        when the attendance falls in its middle, discarded when nothing is left. Never one it
        does not overlap: its hours may be the ones the reviewer narrowed it to (issue #731)."""
        attendances = self.filtered(lambda attendance: attendance.check_in and attendance.in_mode != 'technical')
        if not attendances:
            return
        domain = [('origin', '=', 'check_in'), ('state', 'in', UNRESOLVED_STATES),
                  # The one an accepted correction request resolves itself (issue #735).
                  ('id', 'not in', self.env.context.get('ems_skip_absence_review_ids', [])),
                  ('employee_id', 'in', attendances.employee_id.ids),
                  ('date_to', '>', min(attendances.mapped('check_in')))]
        if all(attendances.mapped('check_out')):
            domain.append(('date_from', '<', max(attendances.mapped('check_out'))))
        for absence in self.env['ems.absence_pending'].sudo().search(domain):
            if any(attendance.employee_id == absence.employee_id and attendance.check_in < absence.date_to
                   and (not attendance.check_out or attendance.check_out > absence.date_from)
                   for attendance in attendances):
                absence._ems_keep_missed_spans()
