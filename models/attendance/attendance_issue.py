# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class EmsAttendanceIssueTutor(models.Model):
    _name = "ems.attendance_issue_tutor"
    _description = "Attendance issue (tutor): contains the data about isues that can be reviewed by the student's tutor."
    _inherit = ['ems.base']

    attendance_issue_student_ids = fields.One2many(string="Students", comodel_name="ems.attendance_issue_student", inverse_name="attendance_issue_tutor_id")
    tutor_id = fields.Many2one(string="Tutor", comodel_name="hr.employee")
    issue_date = fields.Date(string="Date")
    # The tutor gets these issues in their daily summary (res.users._ems_send_daily_summary),
    # at the moment chosen in their profile: the last summary that reported this day, and when
    # the next one is due while some issue of the day is still waiting for it.
    summary_message_id = fields.Many2one(string="Daily summary", comodel_name="mail.message", readonly=True, copy=False)
    sent_date = fields.Datetime(string="Sent on", related="summary_message_id.date")
    schedule_date = fields.Datetime(string="Scheduled on", compute="_compute_summary_state")
    status = fields.Selection(string="Status", compute="_compute_summary_state", selection=[
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
    ])
    exception = fields.Text(string="Exception", compute="_compute_summary_state")

    def _compute_display_name(self):
        for issue_tutor in self:
            issue_tutor.display_name = "%s: %s" % (issue_tutor.issue_date, issue_tutor.tutor_id.display_name)

    @api.depends('summary_message_id', 'attendance_issue_student_ids.attendance_issue_status_ids.tutor_notified')
    def _compute_summary_state(self):
        for issue_tutor in self:
            statuses = issue_tutor.sudo().attendance_issue_student_ids.attendance_issue_status_ids
            failures = issue_tutor.sudo().summary_message_id.notification_ids.filtered(
                lambda notification: notification.notification_status in ('exception', 'bounce'))
            if not statuses or statuses.filtered(lambda status: not status.tutor_notified):
                issue_tutor.status = 'pending'
                issue_tutor.schedule_date = issue_tutor.sudo().tutor_id.user_id.ems_digest_next
            else:
                issue_tutor.status = 'failed' if failures else 'sent'
                issue_tutor.schedule_date = False
            issue_tutor.exception = "\n".join(failure.failure_reason or failure.failure_type or '' for failure in failures) or False

    def _schedule_tutor_report(self):
        """The tutor's daily summary is due no later than the moment they chose for each day
        (res.users.ems_digest_moment): every issue not reported yet goes in the next one, so a
        report covering several days is a single message, and an issue recorded after a summary
        was sent goes in the next one instead of being lost."""
        for issue_tutor in self.sudo():
            user = issue_tutor.tutor_id.user_id
            if user:  # A student without tutor, or a tutor without user: nobody to report to.
                user._ems_digest_schedule_for(issue_tutor.issue_date)

    @api.model
    def _ems_pending_tutors(self, tutors=None):
        """The tutors (hr.employee) with issues not reported yet, among `tutors` if given."""
        domain = [('tutor_notified', '=', False)]
        if tutors is not None:
            domain.append(('attendance_issue_student_id.attendance_issue_tutor_id.tutor_id', 'in', tutors.ids))
        groups = self.env['ems.attendance_issue_status'].sudo()._read_group(
            domain, ['attendance_issue_student_id'])
        issue_students = self.env['ems.attendance_issue_student'].browse([issue_student.id for issue_student, in groups])
        return issue_students.attendance_issue_tutor_id.tutor_id

    @api.model
    def _tutor_report_pending_statuses(self, tutor_ids):
        return self.env['ems.attendance_issue_status'].sudo().search([
            ('attendance_issue_student_id.attendance_issue_tutor_id.tutor_id', 'in', tutor_ids),
            ('tutor_notified', '=', False),
        ])

    @api.model
    def _tutor_report_days(self, statuses):
        """The issues `statuses` (not reported yet), for the daily summary: one dict per day,
        oldest first, with 'issue' (this model's record of that day) and 'students' (a list of
        dicts with 'student' and its pending 'statuses')."""
        days = []
        for issue_tutor in statuses.attendance_issue_student_id.attendance_issue_tutor_id.sorted('issue_date'):
            students = [
                {'student': issue_student.student_id, 'statuses': issue_student.attendance_issue_status_ids & statuses}
                for issue_student in issue_tutor.attendance_issue_student_ids
                if issue_student.attendance_issue_status_ids & statuses
            ]
            days.append({'issue': issue_tutor, 'students': students})
        return days

    def remove_if_empty(self):
        for issue_student in self.attendance_issue_student_ids:
            if len(issue_student.attendance_issue_status_ids) == 0: issue_student.unlink()

        if len(self.attendance_issue_student_ids) == 0:
            self.unlink()

class EmsAttendanceIssueStudent(models.Model):
    _name = "ems.attendance_issue_student"
    _description = "Attendance issue (student): groups the attendance's issues by student."
    _inherit = ['ems.base']

    attendance_issue_tutor_id = fields.Many2one(string="Tutor notification data", comodel_name="ems.attendance_issue_tutor", ondelete='cascade')
    attendance_issue_status_ids = fields.One2many(string="Sessions", comodel_name="ems.attendance_issue_status", inverse_name="attendance_issue_student_id")
    student_id = fields.Many2one(string="Student", comodel_name="res.partner", domain="[('contact_type', '=', 'student')]", ondelete='cascade')
    date = fields.Date(string="Date", related="attendance_issue_tutor_id.issue_date")

    @api.depends('attendance_issue_tutor_id')
    def _compute_display_name(self):
        for issue_student in self:
            issue_student.display_name = "%s | %s" % (issue_student.student_id.display_name, issue_student.date)

class EmsAttendanceIssueStatus(models.Model):
    _name = "ems.attendance_issue_status"
    _description = "Attendance issue (status): contains the data about an attendance issue."
    _inherit = ['ems.base']

    attendance_issue_student_id = fields.Many2one(string="Student notification data", comodel_name="ems.attendance_issue_student", ondelete='cascade')
    attendance_session_line_id = fields.Many2one(string="Status data", comodel_name="ems.attendance_session_line", required=True, ondelete='cascade')
    attendance_session_id = fields.Many2one(string="Session", related="attendance_session_line_id.attendance_session_id", store=False)

    notification_id = fields.Many2one(string="Notification", comodel_name="queue.job")
    # The tutor's daily summary, unlike the family's notification above, reports several days at
    # once (res.users._ems_send_daily_summary), so each issue records itself whether it has
    # already been reported.
    tutor_notified = fields.Boolean(string="Reported to the tutor", default=False, copy=False, readonly=True)
    notification_status = fields.Selection(string="Notification status", related="notification_id.state")
    exception = fields.Text(string="Exception", related="notification_id.exc_info")

    send_to = fields.Char(string="Send to", required=True)
    schedule_date = fields.Datetime(string="Scheduled on", related="notification_id.eta")
    subject_id = fields.Many2one(string="Subject", related="attendance_session_id.subject_id")
    group_ids = fields.Many2many(string="Groups", related="attendance_session_id.group_ids")
    space_id = fields.Many2one(string="Space", related="attendance_session_id.space_id")
    teacher_id = fields.Many2one(string="Teacher", related="attendance_session_id.session_teacher_id")
    time_range = fields.Char(string="Time range", related="attendance_session_id.time_range")
    pending = fields.Boolean(string="Pending", compute="_compute_pending", store=False)
    rectified_by = fields.Many2one(string="Rectified by", comodel_name="ems.attendance_issue_status", ondelete='cascade')
    rectification = fields.Boolean(string="Rectification", default=False)

    # NOTE: tutor needed for permission purposes
    tutor_id = fields.Many2one(string='Tutor (sent to)', related="attendance_issue_student_id.student_id.tutor_id")

    # NOTE: We want a copy of the original status, because a miss can be justified later, but we want to keep the original notification status.
    attendance_status_id = fields.Many2one(string="Attendance status", comodel_name="ems.attendance_status")
    notes = fields.Text(string="Notes")

    @api.depends('attendance_session_line_id')
    def _compute_display_name(self):
        for issue_status in self:
            issue_status.display_name = "%s | %s (%s)" % (issue_status.attendance_session_id.display_name, issue_status.attendance_issue_student_id.student_id.display_name, issue_status.attendance_status_id.name)

    @api.depends('notification_status')
    def _compute_pending(self):
        for issue_status in self:
            issue_status.pending = issue_status.notification_status is False or issue_status.notification_status in ["pending", "enqueued"]

    def unlink(self):
        # NOTE: button_cancel source: https://github.com/OCA/queue/blob/18.0/queue_job/models/queue_job.py
        self.notification_id.button_cancelled()
        return super().unlink()

    def send_notification(self):
        self.ensure_one()
        separator = "; "

        # The student and the family get the same underlying notification, but worded for
        # their own audience (mails/attendance/attendance_issue_status.xml has both). A
        # rectification keeps using the same template for everyone, as before.
        family_template = self.env.ref('ems.mail_attendance_issue_rectification' if self.rectification else 'ems.mail_attendance_issue_status_family', raise_if_not_found=True)
        student_template = family_template if self.rectification else self.env.ref('ems.mail_attendance_issue_status_student', raise_if_not_found=True)

        # Build email -> lang/kind maps so each recipient gets the mail in their own language
        # and with the wording that matches who they are.
        student = self.attendance_issue_student_id.student_id
        lang_by_email = {}
        kind_by_email = {}
        if student.student_email:
            lang_by_email[student.student_email] = student.lang
            kind_by_email[student.student_email] = 'student'

        for relation in student.relation_all_ids:
            partner = relation.other_partner_id
            if partner.contact_type == 'family' and partner.email:
                lang_by_email[partner.email] = partner.lang
                kind_by_email[partner.email] = 'family'

        # NOTE: there's no BBC field within the email template, and we want to protect personal addresses
        # when sending to multiple destinations. So, it will be send one by one setting up here the address.
        for to in self.send_to.split(separator):
            to = to.strip()
            lang = lang_by_email.get(to)
            template = student_template if kind_by_email.get(to) == 'student' else family_template
            tmpl = template.with_context(lang=lang).sudo() if lang else template.sudo()
            tmpl.send_mail(self.id, force_send=True, email_values={'email_to': to})

        return True

    def open_notification_form(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'queue.job',
            'res_id': self.notification_id.id,
            'view_id': self.env.ref('queue_job.view_queue_job_form').id,
            'view_mode': 'form',
            'target': 'new'
        }

    def open_exception_popup(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Error details'),
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref('ems.view_attendance_issue_status_exception_popup').id,
            'target': 'new',
            'flags': {'mode': 'readonly'}
        }
