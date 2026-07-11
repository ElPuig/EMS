# -*- coding: utf-8 -*-

from odoo import _, api, fields, models


class ems_strike(models.Model):
    _name = "ems.strike"
    _description = "Strike: a disciplinary notice issued by a teacher against a student."
    _inherit = ["ems.base"]
    _order = "date desc, id desc"

    student_id = fields.Many2one(string="Student", comodel_name="res.partner", domain="[('contact_type', '=', 'student')]", required=True, ondelete="cascade")
    teacher_id = fields.Many2one(string="Teacher", comodel_name="hr.employee", required=True, default=lambda self: self.env.user.employee_id)
    attendance_session_line_id = fields.Many2one(string="Session line", comodel_name="ems.attendance_session_line", ondelete="set null", index=True)
    reason_id = fields.Many2one(string="Reason", comodel_name="ems.strike.reason", required=True, default=lambda self: self.env.ref("ems.strike_reason_other", raise_if_not_found=False))
    date = fields.Datetime(string="Date and time", default=fields.Datetime.now, required=True)
    notes = fields.Text(string="Details")
    send_to = fields.Char(string="Sent to", readonly=True, copy=False)
    strike_count_at_creation = fields.Integer(string="Strike count", readonly=True, copy=False)

    @api.depends("student_id", "date", "reason_id")
    def _compute_display_name(self):
        for strike in self:
            strike.display_name = f"{strike.student_id.display_name} | {strike.date} | {strike.reason_id.name}"

    @api.model_create_multi
    def create(self, vals_list):
        strikes = super().create(vals_list)
        for strike in strikes:
            # sudo(): bookkeeping computed by the system, not a user-editable field —
            # a teacher may only create strikes (no write access), see security/rules/coexistence.xml.
            strike.sudo().write({"strike_count_at_creation": self.search_count([
                ("student_id", "=", strike.student_id.id), ("id", "<=", strike.id),
            ])})
            strike.sudo().chatter(_("Strike issued by %(teacher)s: %(reason)s", teacher=strike.teacher_id.display_name, reason=strike.reason_id.name))
            strike._notify()
            strike._check_escalation()
        return strikes

    def _collect_recipients_by_kind(self):
        """Returns {"student": [(email, lang), ...], "family": [...], "tutor": [...]}
        following the same minor/auth_share family authorization rule as
        ems.attendance_issue_status, plus the group tutor. Split by kind (rather than a
        flat list) so _notify() can address each recipient with its own template."""
        self.ensure_one()
        student = self.student_id
        by_kind = {"student": [], "family": [], "tutor": []}
        if student.student_email:
            by_kind["student"].append((student.student_email, student.lang))
        if not student.is_adult or student.auth_share:
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
        if threshold <= 0 or self.strike_count_at_creation % threshold != 0:
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
