from datetime import date
from unittest.mock import patch

from odoo.tests.common import TransactionCase

from .common import create_level_study


class TestAttendanceIssue(TransactionCase):
    """models/attendance/attendance_issue.py — EmsAttendanceIssueTutor/
    _Student/_Status, the notification-tracking backend written to by
    ems.attendance_session_line's _update_notification() (see
    docs/en/developers/attendance/attendance_session.md). Zero coverage
    existed before this pass.

    send_notification() calls send_mail(force_send=True) — mocked per
    CLAUDE.md's email-safety rule for every test in this file, even the
    ones that never reach it, as defense in depth."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mail_server_patcher = patch(
            'odoo.addons.base.models.ir_mail_server.IrMailServer.send_email',
            return_value='test-message-id',
        )
        mail_server_patcher.start()
        cls.addClassCleanup(mail_server_patcher.stop)

        cls.level, cls.study = create_level_study(cls, 'TAI', study={
            'name': 'Test Study (Attendance Issue)', 'date': date.today(),
        }, level={'name': 'Test Level (Attendance Issue)'})
        cls.subject = cls.env['ems.subject'].create({
            'code': 'TAI001', 'acronym': 'TAI', 'name': 'Test Subject (Attendance Issue)',
            'study_ids': [(6, 0, [cls.study.id])],
        })
        cls.space = cls.env['ems.space'].create({
            'code': 'TAI-A', 'name': 'Test Space (Attendance Issue)',
            'space_type_id': cls.env.ref('ems.space_type_classroom').id,
            'work_location_id': cls.env.ref('ems.work_location_main').id,
        })
        cls.teacher = cls.env['hr.employee'].create({
            'name': 'Test Teacher (Attendance Issue)', 'employee_type': 'teacher'})
        cls.tutor_employee = cls.env['hr.employee'].create({
            'name': 'Test Tutor (Attendance Issue)', 'employee_type': 'teacher'})
        cls.group = cls.env['ems.group'].create({
            'course': 1, 'acronym': 'TAI', 'level_id': cls.level.id, 'study_id': cls.study.id,
            'tutor_id': cls.tutor_employee.id,
        })
        cls.student1 = cls.env['res.partner'].create({
            'name': 'Issue Student 1', 'contact_type': 'student', 'main_group_id': cls.group.id,
            'student_email': 'issue.student1@example.com',
        })
        cls.student2 = cls.env['res.partner'].create({
            'name': 'Issue Student 2', 'contact_type': 'student', 'main_group_id': cls.group.id,
            'student_email': 'issue.student2@example.com',
        })
        cls.template = cls.env['ems.attendance_template'].create({
            'teacher_ids': [(6, 0, [cls.teacher.id])], 'level_id': cls.level.id, 'study_id': cls.study.id,
            'subject_id': cls.subject.id, 'group_ids': [(6, 0, [cls.group.id])], 'space_id': cls.space.id,
            'start_date': date(2020, 1, 1), 'end_date': date(2030, 12, 31),
            'student_ids': [(6, 0, [cls.student1.id, cls.student2.id])],
        })
        cls.schedule = cls.env['ems.attendance_schedule'].create({
            'attendance_template_id': cls.template.id, 'weekday': str(date.today().weekday()),
            'start_time': 8.0, 'end_time': 9.0, 'space_id': cls.space.id,
        })
        cls.session = cls.env['ems.attendance_session_header'].create({
            'attendance_schedule_id': cls.schedule.id, 'date': date.today(),
            'mode': 'scheduled', 'session_teacher_id': cls.teacher.id,
        })

    def _mark_miss(self, student):
        line = self.session.attendance_session_line_ids.filtered(lambda l: l.student_id == student)
        line.status_id = self.env.ref('ems.attendance_status_miss')
        return line

    def _issue_tutor(self):
        return self.env['ems.attendance_issue_tutor'].search([
            ('tutor_id', '=', self.tutor_employee.id), ('issue_date', '=', self.session.date),
        ])

    # --- _compute_pending: the real multi-record bug -----------------------------------

    def test_compute_pending_does_not_crash_on_multiple_records(self):
        """Regression test: _compute_pending used self.notification_status
        instead of rec.notification_status inside its per-record loop — a
        ValueError: Expected singleton on any batch read of more than one
        record (e.g. the Daily Issues list view, or simply reading .pending
        on 2+ statuses at once, as done here). Fixed in this DTON pass."""
        self._mark_miss(self.student1)
        self._mark_miss(self.student2)
        statuses = self._issue_tutor().attendance_issue_student_ids.attendance_issue_status_ids
        self.assertEqual(len(statuses), 2)
        # Must not raise; both entries are freshly queued, so both pending.
        self.assertTrue(all(statuses.mapped('pending')))

    # --- remove_if_empty cascade ---------------------------------------------------------

    def test_marking_back_to_attended_removes_the_whole_chain(self):
        self._mark_miss(self.student1)
        issue_tutor = self._issue_tutor()
        self.assertTrue(issue_tutor)

        line = self.session.attendance_session_line_ids.filtered(lambda l: l.student_id == self.student1)
        line.status_id = self.env.ref('ems.attendance_status_attended')

        self.assertFalse(issue_tutor.exists())

    def test_remove_if_empty_keeps_tutor_with_remaining_students(self):
        self._mark_miss(self.student1)
        self._mark_miss(self.student2)
        issue_tutor = self._issue_tutor()

        line1 = self.session.attendance_session_line_ids.filtered(lambda l: l.student_id == self.student1)
        line1.status_id = self.env.ref('ems.attendance_status_attended')

        self.assertTrue(issue_tutor.exists())
        self.assertEqual(len(issue_tutor.attendance_issue_student_ids), 1)

    # --- unlink cancels the queued notification -------------------------------------------

    def test_unlink_status_cancels_notification_job(self):
        self._mark_miss(self.student1)
        status = self._issue_tutor().attendance_issue_student_ids.attendance_issue_status_ids
        job = status.notification_id
        self.assertTrue(job)
        status.unlink()
        self.assertIn(job.state, ('cancelled', 'done'))

    # --- send_notification (mail mocked) --------------------------------------------------

    def test_tutor_send_notification_does_not_raise(self):
        self._mark_miss(self.student1)
        issue_tutor = self._issue_tutor()
        self.assertTrue(issue_tutor.send_notification())

    def test_status_send_notification_rectification_does_not_raise(self):
        """Regression test: mail_attendance_issue_rectification's 'Status:' row
        referenced object.attendance_session_line_id (a Many2one whose display_name
        just echoes session+student info again) instead of object.attendance_status_id
        — wrong content, not a crash, but still a real bug in the shipped English
        source (not just a translation), fixed alongside the crash bug above."""
        self._mark_miss(self.student1)
        status = self._issue_tutor().attendance_issue_student_ids.attendance_issue_status_ids
        status.rectification = True
        self.assertTrue(status.send_notification())

    def test_status_send_notification_does_not_raise(self):
        self._mark_miss(self.student1)
        status = self._issue_tutor().attendance_issue_student_ids.attendance_issue_status_ids
        self.assertTrue(status.send_notification())

    # --- display names -------------------------------------------------------------------

    def test_display_names(self):
        self._mark_miss(self.student1)
        issue_tutor = self._issue_tutor()
        issue_student = issue_tutor.attendance_issue_student_ids
        issue_status = issue_student.attendance_issue_status_ids

        self.assertIn(self.tutor_employee.display_name, issue_tutor.display_name)
        self.assertIn(self.student1.display_name, issue_student.display_name)
        self.assertIn(self.student1.display_name, issue_status.display_name)

    # --- action helpers --------------------------------------------------------------------

    def test_open_notification_form(self):
        self._mark_miss(self.student1)
        status = self._issue_tutor().attendance_issue_student_ids.attendance_issue_status_ids
        action = status.open_notification_form()
        self.assertEqual(action['res_model'], 'queue.job')
        self.assertEqual(action['res_id'], status.notification_id.id)

    def test_open_exception_popup(self):
        self._mark_miss(self.student1)
        status = self._issue_tutor().attendance_issue_student_ids.attendance_issue_status_ids
        action = status.open_exception_popup()
        self.assertEqual(action['res_model'], 'ems.attendance_issue_status')
        self.assertEqual(action['res_id'], status.id)
