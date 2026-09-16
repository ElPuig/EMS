# -*- coding: utf-8 -*-

from datetime import timedelta

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
    attendance_id = fields.Many2one(
        string="Attendance",
        comodel_name="hr.attendance",
        required=True,
        ondelete="cascade",
        default=lambda self: self.env.context.get("default_attendance_id"),
    )
    employee_id = fields.Many2one(string="Employee", comodel_name="hr.employee", related="attendance_id.employee_id", store=True, readonly=True)
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

    @api.depends("employee_id", "attendance_id.check_in")
    def _compute_display_name(self):
        for correction in self:
            if correction.employee_id and correction.attendance_id.check_in:
                correction.display_name = _("%(employee)s (%(date)s)") % {
                    "employee": correction.employee_id.display_name,
                    "date": correction.attendance_id.check_in,
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
        # remembered. Once the day's schedule ends (or there was none to begin with - a
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
            return False
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

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # NOTE: attendance_id is readonly="1" in the form (only ever populated via the
            # "Request Correction" button's default_attendance_id context), so the client
            # never sends it in vals - Odoo only merges context defaults into vals inside
            # the base create() (_add_missing_default_values), which runs *after* this
            # override. Falling back to the context default here (instead of assuming vals
            # already has it) is what actually resolves the real attendance record.
            attendance_id = vals.get("attendance_id") or self.env.context.get("default_attendance_id")
            attendance = self.env["hr.attendance"].browse(attendance_id)
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
            for user in approvers:
                correction_sudo.activity_schedule(
                    activity_type_id=activity_type.id,
                    user_id=user.id,
                    summary=_("Attendance correction request"),
                    note=correction.reason,
                    date_deadline=fields.Date.context_today(correction) + timedelta(days=APPROVAL_ACTIVITY_DEADLINE_DAYS),
                )
            correction_sudo.chatter(
                _("Correction requested by %(employee)s.") % {"employee": correction.employee_id.display_name}
            )
        return corrections

    def action_accept(self):
        for correction in self:
            correction._check_approver()
            values = {}
            if correction.requested_check_in:
                values["check_in"] = correction._combine_date_and_time(correction.original_check_in, correction.requested_check_in)
            if correction.requested_check_out:
                # NOTE: falls back to the original check_in's date if it was never checked out, since
                # there is no original check_out to anchor the corrected time's date to.
                reference = correction.original_check_out or correction.original_check_in
                values["check_out"] = correction._combine_date_and_time(reference, correction.requested_check_out)
            correction.attendance_id.sudo().write(values)
            correction._close("accepted")
            correction.message_post(
                body=_("Your correction request has been accepted."),
                partner_ids=correction.create_uid.partner_id.ids,
            )

    def action_reject(self):
        for correction in self:
            correction._check_approver()
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
        self.ensure_one()
        approver_employee = self.employee_id.find_head_of_studies()
        if approver_employee:
            return approver_employee.user_id
        return self.env["res.users"].sudo().search([("groups_id", "=", self.env.ref("ems.group_academic_admin").id)])

    def _check_is_approver(self):
        self.ensure_one()
        if self.env.user.has_group("ems.group_academic_admin"):
            return True
        return self.env.user in self._find_approver()

    def _check_approver(self):
        # NOTE: no longer restricted to state == 'pending' — the approver can revise their own
        # earlier decision (e.g. clicked the wrong button) at any time.
        self.ensure_one()
        if not self._check_is_approver():
            raise UserError(_("Only the resolved approver or an Academic Administrator can decide on this request."))

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
    _inherit = "hr.attendance"

    correction_ids = fields.One2many(string="Correction requests", comodel_name="ems.attendance_correction", inverse_name="attendance_id")
    correction_count = fields.Integer(string="Correction requests count", compute="_compute_correction_count")

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
