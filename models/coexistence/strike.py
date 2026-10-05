# -*- coding: utf-8 -*-

from datetime import timedelta, timezone

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ems_strike(models.Model):
    _name = "ems.strike"
    _description = "Strike: a disciplinary notice issued by a teacher against a student."
    _inherit = ["ems.base"]
    _order = "date desc, id desc"

    student_id = fields.Many2one(string="Student", comodel_name="res.partner", domain="[('contact_type', '=', 'student')]", required=True, ondelete="cascade", default=lambda self: self.env.context.get("strike_student_id"))
    teacher_id = fields.Many2one(string="Teacher", comodel_name="hr.employee", required=True, default=lambda self: self.env.user.employee_id)
    attendance_session_line_id = fields.Many2one(string="Session line", comodel_name="ems.attendance_session_line", ondelete="set null", index=True)
    # Where the incident happened (issues #546, #570), frozen when the strike is issued: only
    # depends on student_id/attendance_session_line_id, so a later group change or session edit
    # never rewrites an old strike. A strike issued outside a class has no subject nor classroom.
    group_id = fields.Many2one(string="Group", comodel_name="ems.group", compute="_compute_session_data", store=True, index=True)
    subject_id = fields.Many2one(string="Subject", comodel_name="ems.subject", compute="_compute_session_data", store=True)
    space_id = fields.Many2one(string="Classroom", comodel_name="ems.space", compute="_compute_session_data", store=True)
    reason_id = fields.Many2one(string="Reason", comodel_name="ems.strike.reason", required=True, default=lambda self: self._default_reason_id())
    date = fields.Datetime(string="Date and time", default=fields.Datetime.now, required=True)
    notes = fields.Text(string="Details")
    kicked_out = fields.Boolean(string="Kicked out of class", default=False)
    send_to = fields.Char(string="Sent to", readonly=True, copy=False)
    strike_count = fields.Integer(string="Strike count", compute="_compute_strike_count")
    duplicate_warning = fields.Char(string="Possible duplicate", compute="_compute_duplicate_warning")

    @api.model
    def _default_reason_id(self):
        """First active reason by its own order, the same one the roll-call dialog preselects
        (attendance_session_view.js), so both ways of issuing a strike agree."""
        return self.env["ems.strike.reason"].search([], limit=1)

    @api.depends("student_id", "date", "reason_id")
    def _compute_display_name(self):
        for strike in self:
            strike.display_name = f"{strike.student_id.display_name} | {strike.date} | {strike.reason_id.name}"

    @api.depends("student_id", "attendance_session_line_id")
    def _compute_session_data(self):
        for strike in self:
            line = strike.attendance_session_line_id
            # The student's group when the roll-call was taken, as the attendance reports use it.
            strike.group_id = line.student_group_id if line else strike.student_id.main_group_id
            strike.subject_id = line.subject_id
            strike.space_id = line.attendance_session_id.space_id

    @api.depends("student_id")
    def _compute_strike_count(self):
        for strike in self:
            strike.strike_count = self.search_count([
                ("student_id", "=", strike.student_id.id), ("id", "<=", strike.id),
            ]) if strike.id else 0

    @api.depends("student_id", "teacher_id", "attendance_session_line_id")
    def _compute_duplicate_warning(self):
        # Only while issuing a new one (the New strike dialog's onchange): a saved strike would
        # find itself. A new record's NewId is falsy.
        for strike in self:
            strike.duplicate_warning = False if strike.id else self.get_duplicate_warning(
                strike.student_id.id, strike.teacher_id.id, strike.attendance_session_line_id.id)

    @api.constrains("date")
    def _check_date_not_in_future(self):
        # Both sides are naive UTC (how Odoo stores and returns Datetime), so no tz conversion.
        now = fields.Datetime.now()
        for strike in self:
            if strike.date > now:
                raise ValidationError(_("A strike can't be dated in the future."))

    @api.model_create_multi
    def create(self, vals_list):
        strikes = super().create(vals_list)
        for strike in strikes:
            strike.sudo().chatter(_("Strike issued by %(teacher)s: %(reason)s", teacher=strike.teacher_id.display_name, reason=strike.reason_id.name))
            strike._notify()
            strike._check_escalation()
        return strikes

    @api.model
    def get_duplicate_warning(self, student_id, teacher_id=False, line_id=False):
        """Issue #554: the same strike was sometimes sent twice a few seconds apart. Returns a
        warning if the teacher (the current user's employee by default) already issued a strike
        to this student, on the same roll-call line (or on none, for the New strike dialog),
        within the last strike_duplicate_window minutes, False otherwise. Both
        ways of issuing a strike ask for confirmation when there is one: the New strike dialog
        (duplicate_warning) and the roll-call view (attendance_session_view.js)."""
        window = self.env.company.strike_duplicate_window
        teacher_id = teacher_id or self.env.user.employee_id.id
        if window <= 0 or not student_id or not teacher_id:
            return False
        # create_date rather than date, which can be backdated; it is set from cr.now().
        latest = self.search([
            ("student_id", "=", student_id), ("teacher_id", "=", teacher_id),
            ("attendance_session_line_id", "=", line_id or False),
            ("create_date", ">=", self.env.cr.now() - timedelta(minutes=window)),
        ], order="create_date desc, id desc", limit=1)
        if not latest:
            return False
        local = self.env["ems.datetime_utils"].utc_datetime_to_local(latest.create_date.replace(tzinfo=timezone.utc))
        return _(
            "%(teacher)s already issued a strike to %(student)s at %(time)s (%(reason)s). Make sure this one is not a duplicate.",
            teacher=latest.teacher_id.display_name, student=latest.student_id.display_name,
            time=local.strftime("%H:%M:%S"), reason=latest.reason_id.name,
        )

    def _collect_recipients_by_kind(self):
        """Returns {"student": [(email, lang), ...], "family": [...], "tutor": [...]}
        following the same minor/auth_share family authorization rule as
        ems.attendance_issue_status, plus the group tutor. Split by kind (rather than a
        flat list) so _notify() can address each recipient with its own template.

        The family entry is additionally gated by strike_family_notification_mode
        (res.company): 'all' notifies the family on every strike (subject to the
        minor/auth_share rule above), 'kicked_out' only when this strike's kicked_out is
        True. The student and tutor notifications are never affected by this setting."""
        self.ensure_one()
        student = self.student_id
        by_kind = {"student": [], "family": [], "tutor": []}
        if student.student_email:
            by_kind["student"].append((student.student_email, student.lang))
        notify_family = self.kicked_out or self.env.company.strike_family_notification_mode == "all"
        if notify_family and (not student.is_adult or student.auth_share):
            for relation in student.relation_all_ids:
                partner = relation.other_partner_id
                if partner.contact_type == "family" and partner.email:
                    by_kind["family"].append((partner.email, partner.lang))
        if student.tutor_id and student.tutor_id.email:
            tutor_lang = student.tutor_id.user_id.lang if student.tutor_id.user_id else False
            by_kind["tutor"].append((student.tutor_id.email, tutor_lang))
        return by_kind

    def _send_per_recipient(self, template, recipients):
        self.ensure_one()
        for email, lang in recipients:
            tmpl = template.with_context(lang=lang).sudo() if lang else template.sudo()
            tmpl.send_mail(self.id, force_send=True, email_values={"email_to": email})

    def _notify(self):
        self.ensure_one()
        by_kind = self._collect_recipients_by_kind()
        all_recipients = [recipient for recipients in by_kind.values() for recipient in recipients]
        self.sudo().write({"send_to": "; ".join(email for email, _lang in all_recipients)})
        templates = {
            "student": self.env.ref("ems.mail_strike_notification_student", raise_if_not_found=True),
            "family": self.env.ref("ems.mail_strike_notification_family", raise_if_not_found=True),
            "tutor": self.env.ref("ems.mail_strike_notification_tutor", raise_if_not_found=True),
        }
        for kind, recipients in by_kind.items():
            if recipients:
                self._send_per_recipient(templates[kind], recipients)

    def _matching_coexistence_coordinators(self):
        """Coexistence coordinators sharing the issuing teacher's ascendant Head of
        Studies / Deputy Head of Studies (hr.employee.find_head_of_studies())."""
        self.ensure_one()
        role = self.env.ref("ems.role_coexistence", raise_if_not_found=False)
        if not role:
            return self.env["hr.employee"]
        teacher_hos = self.teacher_id.find_head_of_studies()
        Employee = self.env["hr.employee"]
        coordinators = Employee
        for public_employee in role.employee_ids:
            employee = Employee.sudo().search([("id", "=", public_employee.id)], limit=1)
            if employee and employee.find_head_of_studies() == teacher_hos:
                coordinators |= employee
        return coordinators

    def _check_escalation(self):
        self.ensure_one()
        threshold = self.env.company.strike_escalation_threshold
        if threshold <= 0 or self.strike_count % threshold != 0:
            return
        coordinators = self._matching_coexistence_coordinators()
        if not coordinators:
            return
        template = self.env.ref("ems.mail_strike_escalation", raise_if_not_found=True)
        recipients = [
            (employee.email, employee.user_id.lang if employee.user_id else False)
            for employee in coordinators if employee.email
        ]
        self._send_per_recipient(template, recipients)
