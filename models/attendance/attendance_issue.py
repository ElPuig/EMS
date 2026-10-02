# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

from .attendance_report_schedule import PENDING_JOB_STATES

class EmsAttendanceIssueTutor(models.Model):
    _name = "ems.attendance_issue_tutor"
    _description = "Attendance issue (tutor): contains the data about isues that can be reviewed by the student's tutor."
    _inherit = ['ems.base']

    attendance_issue_student_ids = fields.One2many(string="Students", comodel_name="ems.attendance_issue_student", inverse_name="attendance_issue_tutor_id")
    notification_id = fields.Many2one(string="Notification", comodel_name="queue.job")
    tutor_id = fields.Many2one(string="Tutor", comodel_name="hr.employee")
    issue_date = fields.Date(string="Date")
    schedule_date = fields.Datetime(string="Scheduled on", related="notification_id.eta")
    status = fields.Selection(string="Status", related="notification_id.state")
    exception = fields.Text(string="Exception", related="notification_id.exc_info")

    def _compute_display_name(self):
        for issue_tutor in self:
            issue_tutor.display_name = "%s: %s" % (issue_tutor.issue_date, issue_tutor.tutor_id.display_name)

    def send_notification(self):
        """The tutor's report, with every issue of theirs not reported yet (not only this day's).
        Kept for the jobs queued before the report became one per tutor."""
        self.ensure_one()
        return self._send_tutor_report(self.tutor_id.id)

    def _schedule_tutor_report(self):
        """Attaches each day to its tutor's pending report job, or queues a new one at the moment
        the tutor chose (res.users.ems_attendance_report_moment): one job per tutor, so a report
        covering several days (sent the next morning, at a fixed time...) is a single email, and an
        issue recorded after a report was sent goes in the next one instead of being lost."""
        IssueTutor = self.sudo()
        for issue_tutor in IssueTutor.browse(self.ids):
            if issue_tutor.notification_id.state in PENDING_JOB_STATES:
                continue
            tutor = issue_tutor.tutor_id
            if not tutor:
                continue  # A student without tutor: nobody to report to.
            job = IssueTutor.search([('tutor_id', '=', tutor.id), ('notification_id.state', 'in', PENDING_JOB_STATES)], limit=1).notification_id
            if not job:
                delayed = IssueTutor.browse().with_delay(
                    eta=tutor._ems_attendance_report_eta(issue_tutor.issue_date),
                    description=f"Tutor's attendance report: {tutor.name}",
                )._send_tutor_report(tutor.id)
                job = self.env['queue.job'].sudo().search([('uuid', '=', delayed.uuid)])
            issue_tutor.notification_id = job

    @api.model
    def _send_tutor_report(self, tutor_id):
        """Sends the tutor's report, if anything is left to report, and marks it as reported."""
        statuses = self._tutor_report_pending_statuses(tutor_id)
        if not statuses:
            return True
        # Rendered on the latest day; the template lists every pending day (_tutor_report_days).
        issue_tutor = statuses.attendance_issue_student_id.attendance_issue_tutor_id.sorted('issue_date')[-1]
        template = self.env.ref('ems.mail_attendance_issue_tutor', raise_if_not_found=True)
        template.sudo().send_mail(issue_tutor.id, force_send=True)
        statuses.tutor_notified = True
        return True

    @api.model
    def _tutor_report_pending_statuses(self, tutor_id):
        return self.env['ems.attendance_issue_status'].sudo().search([
            ('attendance_issue_student_id.attendance_issue_tutor_id.tutor_id', '=', tutor_id),
            ('tutor_notified', '=', False),
        ])

    def _tutor_report_days(self):
        """The tutor's issues not reported yet, for the report's template: one dict per day,
        oldest first, with 'issue' (this model's record of that day) and 'students' (a list of
        dicts with 'student' and its pending 'statuses')."""
        self.ensure_one()
        statuses = self._tutor_report_pending_statuses(self.tutor_id.id)
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
            job = self.notification_id
            self.unlink()
            # The job is the tutor's, shared with their other pending days: cancelled only once
            # no day uses it any more.
            if job and not self.sudo().search_count([('notification_id', '=', job.id)]):
                job.button_cancelled()

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
    # The tutor's report, unlike the family's notification above, is one job per tutor for
    # several days (ems.attendance_issue_tutor._schedule_tutor_report), so each issue records itself
    # whether it has already been reported.
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
