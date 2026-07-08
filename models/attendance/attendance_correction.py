# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class ems_attendance_correction(models.Model):
    _name = "ems.attendance_correction"
    _description = "Attendance correction: a teacher's request to amend a check-in/check-out."
    _inherit = ["ems.base"]
    _order = "create_date desc"
    _sql_constraints = [
        (
            "check_requested_values",
            "CHECK(requested_check_in IS NOT NULL OR requested_check_out IS NOT NULL)",
            "At least one of the requested check-in/check-out times must be set.",
        ),
    ]

    attendance_id = fields.Many2one(string="Attendance", comodel_name="hr.attendance", required=True, ondelete="cascade")
    employee_id = fields.Many2one(string="Employee", comodel_name="hr.employee", related="attendance_id.employee_id", store=True, readonly=True)
    original_check_in = fields.Datetime(string="Original check-in", related="attendance_id.check_in", readonly=True)
    original_check_out = fields.Datetime(string="Original check-out", related="attendance_id.check_out", readonly=True)
    requested_check_in = fields.Datetime(string="Requested check-in")
    requested_check_out = fields.Datetime(string="Requested check-out")
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

    @api.constrains("requested_check_in", "requested_check_out")
    def _check_at_least_one_requested(self):
        for correction in self:
            if not correction.requested_check_in and not correction.requested_check_out:
                raise ValidationError(_("You must request a correction for the check-in and/or the check-out time."))

    @api.model_create_multi
    def create(self, vals_list):
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
                )
            correction_sudo.chatter(
                _("Correction requested by %(employee)s.") % {"employee": correction.employee_id.display_name}
            )
        return corrections

    def action_accept(self):
        for correction in self:
            correction._check_pending_and_approver()
            values = {}
            if correction.requested_check_in:
                values["check_in"] = correction.requested_check_in
            if correction.requested_check_out:
                values["check_out"] = correction.requested_check_out
            correction.attendance_id.sudo().write(values)
            correction._close("accepted")
            correction.message_post(
                body=_("Your correction request has been accepted."),
                partner_ids=correction.create_uid.partner_id.ids,
            )

    def action_reject(self):
        for correction in self:
            correction._check_pending_and_approver()
            correction._close("rejected")
            correction.message_post(
                body=_("Your correction request has been rejected."),
                partner_ids=correction.create_uid.partner_id.ids,
            )

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

    def _check_pending_and_approver(self):
        self.ensure_one()
        if self.state != "pending":
            raise UserError(_("Only pending requests can be decided."))
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
