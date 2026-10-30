# -*- coding: utf-8 -*-

from datetime import timedelta

from pytz import UTC

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

# How much time the approver is given before the "Review attendance correction
# request" activity is flagged overdue. Set explicitly (activity_schedule()
# otherwise defaults the deadline to today, which reads as "due immediately").
APPROVAL_ACTIVITY_DEADLINE_DAYS = 2


class ems_attendance_correction(models.Model):
    _name = "ems.attendance_correction"
    _description = "Attendance correction: a teacher's request to amend a check-in/check-out."
    _inherit = ["ems.base", "ems.datetime_utils"]
    _order = "create_date desc"
    _sql_constraints = [
        (
            "check_requested_values",
            "CHECK(requested_check_in IS NOT NULL OR requested_check_out IS NOT NULL)",
            "At least one of the requested check-in/check-out times must be set.",
        ),
    ]

    # NOTE: explicit default, matching requested_check_in/out below, instead of relying purely on
    # Odoo's generic default_<field> context lookup.
    # Empty when the teacher asks for a check-in on a detected absence's day with no attendance
    # at all (issue #735): accepting it records one.
    attendance_id = fields.Many2one(
        string="Attendance",
        comodel_name="hr.attendance",
        ondelete="cascade",
        default=lambda self: self.env.context.get("default_attendance_id"),
    )
    # Issue #735: requested from a detected absence the teacher was asked to justify. Its
    # reminders wait while the request is pending.
    absence_pending_id = fields.Many2one(
        string="Detected absence",
        comodel_name="ems.absence_pending",
        ondelete="set null",
        readonly=True,
        default=lambda self: self.env.context.get("default_absence_pending_id"),
    )
    allowed_attendance_ids = fields.Many2many(
        string="Attendances of that day", comodel_name="hr.attendance", compute="_compute_allowed_attendance_ids")
    employee_id = fields.Many2one(
        string="Employee", comodel_name="hr.employee", compute="_compute_employee_id", store=True, readonly=True)
    # NOTE: snapshotted at create() time (not related to attendance_id.check_in/out) so the
    # true original value survives even after action_accept() overwrites the attendance, which
    # is what lets action_reject()/re-deciding restore it later.
    original_check_in = fields.Datetime(string="Original check-in", readonly=True)
    original_check_out = fields.Datetime(string="Original check-out", readonly=True)
    requested_check_in = fields.Float(string="Requested check-in time", default=lambda self: self._default_requested_time("check_in"))
    requested_check_out = fields.Float(string="Requested check-out time", default=lambda self: self._default_requested_time("check_out"))
    reason = fields.Text(string="Reason", required=True)
    state = fields.Selection(
        [("pending", "Pending"), ("accepted", "Accepted"), ("rejected", "Rejected")],
        string="Status",
        default="pending",
        required=True,
    )
    approver_id = fields.Many2one(string="Approver", comodel_name="res.users", readonly=True)
    decision_date = fields.Datetime(string="Decision date", readonly=True)
    decision_note = fields.Text(string="Decision note")
    is_approver = fields.Boolean(string="Is approver", compute="_compute_is_approver", compute_sudo=True, store=False)
    # NOTE: deliberately no compute_sudo=True - found empirically (2026-09) that computing this
    # field via the sudo'd environment compute_sudo switches to breaks resolving attendance_id
    # from the "Request Correction" button's default_attendance_id context on a fresh .new()
    # record (it reads back empty there, even though the same context key is present and
    # correct). _is_check_out_requestable_for()'s own inner sudo() calls already cover the one
    # access-rights concern (reading another employee's resource.calendar.leaves) that
    # compute_sudo would otherwise have been for.
    is_check_out_requestable = fields.Boolean(
        string="Check-out requestable", compute="_compute_is_check_out_requestable", store=False
    )

    @api.depends("attendance_id.employee_id", "absence_pending_id.employee_id")
    def _compute_employee_id(self):
        for correction in self:
            correction.employee_id = correction.attendance_id.employee_id or correction.absence_pending_id.employee_id

    @api.depends("absence_pending_id")
    def _compute_allowed_attendance_ids(self):
        """The attendances the teacher may pick on a detected absence's day (issue #735)."""
        for correction in self:
            correction.allowed_attendance_ids = correction.absence_pending_id._ems_day_attendances()

    @api.depends("employee_id", "attendance_id.check_in", "absence_pending_id.date_from")
    def _compute_display_name(self):
        for correction in self:
            when = correction.attendance_id.check_in or correction.absence_pending_id.date_from
            if correction.employee_id and when:
                correction.display_name = _("%(employee)s (%(date)s)") % {
                    "employee": correction.employee_id.display_name,
                    "date": when,
                }
            else:
                correction.display_name = _("New correction request")

    def _compute_is_approver(self):
        for correction in self:
            correction.is_approver = bool(correction.id) and correction._check_is_approver()

    @api.depends("attendance_id.check_in", "attendance_id.check_out", "attendance_id.employee_id")
    def _compute_is_check_out_requestable(self):
        for correction in self:
            correction.is_check_out_requestable = correction._is_check_out_requestable_for(correction._get_correction_attendance())

    def _get_correction_attendance(self):
        # Shared by every place that needs "the attendance this correction is/will be about".
        # The button's default_attendance_id context is checked first, ahead of attendance_id
        # itself: an already-saved correction (e.g. the approver reopening a pending request)
        # never carries this context key, so it correctly falls back to attendance_id then.
        default_attendance_id = self.env.context.get("default_attendance_id")
        if default_attendance_id:
            return self.env["hr.attendance"].browse(default_attendance_id)
        return self.attendance_id

    def _is_check_out_requestable_for(self, attendance):
        # A teacher who is still clocked in and still within their expected working hours
        # for that day hasn't left yet - any check-out they'd type in would be invented, not
        # remembered (a day nothing was expected of them ends where their framework's does,
        # see _get_closing_hour()). Once the day's schedule ends (or there was none to begin with - a
        # holiday, an absence covering the whole day, a non-working weekday), there's nothing
        # left to be "still within", so the check-out becomes requestable again.
        is_open = bool(attendance.check_in) and not attendance.check_out
        if not is_open:
            return True
        # sudo() on both the model and the employee: _get_last_working_hour() reads
        # resource.calendar.leaves, which core's own ir.rule restricts to the requesting
        # user's own leaves - without it, a Head of Studies/admin evaluating someone else's
        # request could get an incomplete picture of that other employee's calendar.
        last_working_hour = self.env["hr.attendance"].sudo()._get_last_working_hour(
            attendance.employee_id.sudo(), attendance.check_in.date()
        )
        return last_working_hour is None or fields.Datetime.now() >= last_working_hour

    def _default_requested_time(self, kind):
        # NOTE: defaults to the original time so the requester only has to tweak what's wrong.
        attendance = self._get_correction_attendance()
        if not attendance:
            # A detected absence's day without any attendance: its own hours (issue #735).
            absence = self.env["ems.absence_pending"].browse(self.env.context.get("default_absence_pending_id"))
            if not absence:
                return False
            moment = absence.date_from if kind == "check_in" else absence.date_to
            return self.time_to_float(self.utc_datetime_to_local(moment).time())
        original = attendance.check_in if kind == "check_in" else attendance.check_out
        if original:
            return self.time_to_float(self.utc_datetime_to_local(original).time())
        if kind == "check_out" and not self._is_check_out_requestable_for(attendance):
            # Never pre-fill a value the requester can't see (the field is hidden in the
            # view via is_check_out_requestable) - action_accept() would otherwise apply it.
            return False
        return self._schedule_time_for(attendance, kind)

    def _schedule_time_for(self, attendance, kind):
        # Falls back to the requester's working schedule for that weekday (e.g. check_out
        # is empty while still clocked in) instead of leaving the field blank.
        calendar = attendance.employee_id.resource_calendar_id or self.env.company.resource_calendar_id
        if not calendar:
            return False
        reference = attendance.check_in or fields.Datetime.now()
        weekday = str(self.utc_datetime_to_local(reference).weekday())
        lines = calendar.attendance_ids.filtered(lambda line: line.dayofweek == weekday)
        if not lines:
            return False
        return min(lines.mapped("hour_from")) if kind == "check_in" else max(lines.mapped("hour_to"))

    @api.constrains("requested_check_in", "requested_check_out")
    def _check_at_least_one_requested(self):
        for correction in self:
            if not correction.requested_check_in and not correction.requested_check_out:
                raise ValidationError(_("You must request a correction for the check-in and/or the check-out time."))
            # Issue #735: a time typed as "1400" was saved as 1400 hours.
            if not all(0 <= hours <= 24 for hours in (correction.requested_check_in, correction.requested_check_out)):
                raise ValidationError(_("The requested times must be times of the day, between 00:00 and 24:00."))

    @api.constrains("attendance_id", "absence_pending_id", "requested_check_in", "requested_check_out")
    def _check_attendance_or_absence(self):
        """Issue #735: about an attendance, or about a detected absence's day: then the attendance
        must be the same teacher's, and without one both times are needed and in order."""
        for correction in self:
            absence = correction.absence_pending_id
            if not correction.attendance_id and not absence:
                raise ValidationError(_("A correction request must be about an attendance or a detected absence."))
            if correction.attendance_id and absence and correction.attendance_id.employee_id != absence.employee_id:
                raise ValidationError(_("The attendance must be the detected absence teacher's own."))
            if not correction.attendance_id and not (
                    correction.requested_check_in and correction.requested_check_in < correction.requested_check_out):
                raise ValidationError(_("Without an attendance to correct, give both the check-in and a later check-out time."))

    @api.onchange("attendance_id")
    def _onchange_attendance_id(self):
        """Picking another attendance of a detected absence's day starts from its own times, and no
        attendance from the absence's hours (issue #735)."""
        if not self.absence_pending_id:
            return
        local = self.utc_datetime_to_local
        moments = ((self.attendance_id.check_in, self.attendance_id.check_out) if self.attendance_id
                   else (self.absence_pending_id.date_from, self.absence_pending_id.date_to))
        self.requested_check_in, self.requested_check_out = (
            moment and self.time_to_float(local(moment).time()) for moment in moments)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # NOTE: attendance_id is readonly="1" in the form (only ever populated via the
            # "Request Correction" button's default_attendance_id context), so the client
            # never sends it in vals - Odoo only merges context defaults into vals inside
            # the base create() (_add_missing_default_values), which runs *after* this
            # override. Falling back to the context default here (instead of assuming vals
            # already has it) is what actually resolves the real attendance record.
            attendance_id = vals.get("attendance_id", self.env.context.get("default_attendance_id"))
            attendance = self.env["hr.attendance"].browse(attendance_id)
            absence_id = vals.get("absence_pending_id") or self.env.context.get("default_absence_pending_id")
            if absence_id:
                self.env["ems.absence_pending"].browse(absence_id)._ems_check_correction_requestable()
            vals.setdefault("original_check_in", attendance.check_in)
            vals.setdefault("original_check_out", attendance.check_out)
            # Defense-in-depth: the view hides requested_check_out via is_check_out_requestable,
            # but a stale/tampered client could still send a value - never trust it once the
            # server-side check says the check-out isn't requestable yet.
            if vals.get("requested_check_out") and not self._is_check_out_requestable_for(attendance):
                vals["requested_check_out"] = False
        corrections = super().create(vals_list)
        activity_type = self.env.ref("ems.mail_activity_attendance_correction")
        for correction in corrections:
            # NOTE: sudo() needed here since scheduling an activity/posting a chatter
            # log requires write access on the record, but the requester (a teacher)
            # only has read+create on ems.attendance_correction.
            correction_sudo = correction.sudo()
            approvers = correction._find_approver()
            if not approvers:
                correction_sudo.chatter_exception(
                    _(
                        "No Head of Studies could be found in %(employee)s's management chain; "
                        "an Academic Administrator must fix the org chart."
                    )
                    % {"employee": correction.employee_id.display_name}
                )
                continue
            # Not urgent: no "X has assigned you the following activity" email
            # (mail_activity_quick_update). The approver learns of it from the task itself and
            # from the daily pending-tasks digest (models/shared/task_digest.py).
            for user in approvers:
                correction_sudo.with_context(mail_activity_quick_update=True).activity_schedule(
                    activity_type_id=activity_type.id,
                    user_id=user.id,
                    summary=_("Attendance correction request"),
                    note=correction.reason,
                    date_deadline=fields.Date.context_today(correction) + timedelta(days=APPROVAL_ACTIVITY_DEADLINE_DAYS),
                )
            correction_sudo.chatter(
                _("Correction requested by %(employee)s.") % {"employee": correction.employee_id.display_name}
            )
            if correction.absence_pending_id:
                correction.absence_pending_id.sudo().message_post(
                    body=_("Check-in correction requested by %(employee)s.", employee=correction.employee_id.display_name),
                    subtype_xmlid="mail.mt_note")
        return corrections

    def action_accept(self):
        for correction in self:
            correction._check_approver()
            if not correction.attendance_id:
                correction._accept_new_attendance()
                continue
            values = {}
            if correction.requested_check_in:
                values["check_in"] = correction._combine_date_and_time(correction.original_check_in, correction.requested_check_in)
            if correction.requested_check_out:
                # NOTE: falls back to the original check_in's date if it was never checked out, since
                # there is no original check_out to anchor the corrected time's date to.
                reference = correction.original_check_out or correction.original_check_in
                values["check_out"] = correction._combine_date_and_time(reference, correction.requested_check_out)
            correction._attendance_sudo().write(values)
            correction._accepted()

    def _accept_new_attendance(self):
        """Issue #735: the teacher had no attendance on the detected absence's day; one is
        recorded for the times requested, and the request is about it from then on."""
        self.ensure_one()
        reference = self.absence_pending_id.date_from
        self.attendance_id = self._attendance_sudo().create({
            "employee_id": self.employee_id.id,
            "check_in": self._combine_date_and_time(reference, self.requested_check_in),
            "check_out": self._combine_date_and_time(reference, self.requested_check_out),
            "in_mode": "manual",
            "out_mode": "manual",
        })
        self._accepted()

    def _attendance_sudo(self):
        """The attendances, leaving the detected absence this request comes from to
        _accepted (issue #735): it is corrected, not discarded as covered."""
        return self.env["hr.attendance"].sudo().with_context(
            ems_skip_absence_review_ids=self.absence_pending_id.ids).browse(self.attendance_id.ids)

    def _accepted(self):
        self.ensure_one()
        self._close("accepted")
        self.absence_pending_id._ems_resolve_by_correction()
        self.message_post(
            body=_("Your correction request has been accepted."),
            partner_ids=self.create_uid.partner_id.ids,
        )

    def action_reject(self):
        for correction in self:
            correction._check_approver()
            if correction.state == "accepted" and not correction.original_check_in:
                # Issue #735: the attendance it recorded may already have closed detected absences.
                raise UserError(_("This request recorded a new attendance when it was accepted: correct or "
                                  "delete that attendance instead of rejecting it."))
            # NOTE: restores the original value for whichever field was requested, in case this
            # reverses a previous accept() (the approver correcting their own earlier mistake).
            values = {}
            if correction.requested_check_in:
                values["check_in"] = correction.original_check_in
            if correction.requested_check_out:
                values["check_out"] = correction.original_check_out
            if values:
                correction.attendance_id.sudo().write(values)
            correction._close("rejected")
            correction.message_post(
                body=_("Your correction request has been rejected."),
                partner_ids=correction.create_uid.partner_id.ids,
            )

    def _combine_date_and_time(self, reference_datetime, time_float):
        local_date = self.utc_datetime_to_local(reference_datetime).date()
        return self.datetime_to_odoo(self.time_float_to_utc_datetime(local_date, time_float))

    def _find_approver(self):
        """Who the request is routed to (the task): see hr.employee._find_attendance_approvers.
        Others may decide on it too - see _check_is_approver."""
        self.ensure_one()
        return self.employee_id._find_attendance_approvers()

    def _check_is_approver(self):
        """Whether the current user may decide on this request: see
        hr.employee._ems_is_attendance_approver. A Head of Studies still decides on their own
        request, as before: nobody below the Director is above them."""
        self.ensure_one()
        return self.employee_id._ems_is_attendance_approver(self.env.user)

    def _check_approver(self):
        # NOTE: no longer restricted to state == 'pending' — the approver can revise their own
        # earlier decision (e.g. clicked the wrong button) at any time.
        self.ensure_one()
        if not self._check_is_approver():
            raise UserError(_("Only a Head of Studies of the employee's own branch or an Academic Administrator can decide on this request."))

    def _close(self, state):
        self.ensure_one()
        self.write({
            "state": state,
            "approver_id": self.env.user.id,
            "decision_date": fields.Datetime.now(),
        })
        activity_type = self.env.ref("ems.mail_activity_attendance_correction")
        pending_activities = self.activity_ids.filtered(lambda activity: activity.activity_type_id == activity_type)
        if pending_activities:
            pending_activities.action_feedback(feedback=self.decision_note)


class ems_attendance(models.Model):
    _name = "hr.attendance"
    # The guard duty board reloads when a check-in changes (issue #692).
    _inherit = ["hr.attendance", "ems.guard_board_notifier"]
    _guard_board_fields = ("employee_id", "check_in")

    correction_ids = fields.One2many(string="Correction requests", comodel_name="ems.attendance_correction", inverse_name="attendance_id")
    correction_count = fields.Integer(string="Correction requests count", compute="_compute_correction_count")
    # Issue #692: who checked the employee in on their behalf from the guard duty board ("The
    # teacher is in the classroom"). Its own field: the check-in is created with sudo(), so
    # create_uid would only ever say the superuser.
    ems_checked_in_by_id = fields.Many2one(string="Check-in registered by", comodel_name="res.users", readonly=True)

    @api.depends("correction_ids")
    def _compute_correction_count(self):
        for attendance in self:
            attendance.correction_count = len(attendance.correction_ids)

    def action_view_corrections(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id("ems.action_attendance_correction_tree")
        action["domain"] = [("attendance_id", "=", self.id)]
        action["context"] = {}
        return action

    def _guard_board_spans(self):
        return {(day, day) for day in map(self._guard_board_local_date, self.mapped("check_in"))}

    def _notify_checked_in_by(self):
        """Tells the employee that someone else checked them in (issue #692), and who: an Odoo
        message, to their inbox or by email as their own notification preference says."""
        self.ensure_one()
        partner = self.employee_id.user_id.partner_id or self.employee_id.work_contact_id
        if not partner:
            return
        attendance = self.with_context(lang=partner.lang or self.env.lang)
        utils = self.env["ems.datetime_utils"]
        check_in = utils.utc_datetime_to_local(self.check_in.replace(tzinfo=UTC)).strftime("%H:%M")
        values = {"user": self.ems_checked_in_by_id.name, "time": check_in}
        attendance.sudo().message_notify(
            partner_ids=partner.ids,
            subject=attendance.env._("Check-in registered for you at %(time)s", **values),
            body=attendance.env._(
                "%(user)s registered your check-in at %(time)s from the guard duty board, because you were "
                "in the classroom but had not checked in. If it is not right, request a correction.", **values),
        )
