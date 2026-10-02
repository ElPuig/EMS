from datetime import date, timedelta

from odoo.tests.common import TransactionCase

from .common import create_level_study, mock_outgoing_email, next_student_id


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
        cls.mail_transport = mock_outgoing_email(cls)

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
            'name': 'Test Tutor (Attendance Issue)', 'employee_type': 'teacher',
            'work_email': 'issue.tutor@example.com'})
        cls.group = cls.env['ems.group'].create({
            'course': 1, 'acronym': 'TAI', 'level_id': cls.level.id, 'study_id': cls.study.id,
            'tutor_id': cls.tutor_employee.id,
        })
        cls.student1 = cls.env['res.partner'].create({
            'name': 'Issue Student 1', 'contact_type': 'student', 'student_id': next_student_id(), 'main_group_id': cls.group.id,
            'student_email': 'issue.student1@example.com',
        })
        cls.student2 = cls.env['res.partner'].create({
            'name': 'Issue Student 2', 'contact_type': 'student', 'student_id': next_student_id(), 'main_group_id': cls.group.id,
            'student_email': 'issue.student2@example.com',
        })
        cls.template = cls.env['ems.attendance_template'].create({
            'teacher_ids': [(6, 0, [cls.teacher.id])], 'study_ids': [(6, 0, [cls.study.id])],
            'subject_id': cls.subject.id, 'group_ids': [(6, 0, [cls.group.id])],
            'start_date': date(2020, 1, 1), 'end_date': date(2030, 12, 31),
        })
        cls.schedule = cls.env['ems.attendance_schedule'].create({
            'attendance_template_id': cls.template.id, 'weekday': str(date.today().weekday()),
            'start_time': 8.0, 'end_time': 9.0, 'space_id': cls.space.id,
            'student_ids': [(6, 0, [cls.student1.id, cls.student2.id])],
        })
        cls.session = cls.env['ems.attendance_session_header'].create({
            'attendance_schedule_id': cls.schedule.id, 'date': date.today(),
            'mode': 'scheduled', 'session_teacher_id': cls.teacher.id,
        })

    def _mark_miss(self, student):
        line = self.session.attendance_session_line_ids.filtered(lambda l: l.student_id == student)
        line.status_id = self.env.ref('ems.attendance_status_miss')
        return line

    def _issue_tutor(self, session=None):
        return self.env['ems.attendance_issue_tutor'].search([
            ('tutor_id', '=', self.tutor_employee.id), ('issue_date', '=', (session or self.session).date),
        ])

    def _mark_miss_on(self, session, student):
        line = session.attendance_session_line_ids.filtered(lambda l: l.student_id == student)
        line.status_id = self.env.ref('ems.attendance_status_miss')
        return line

    def _last_week_session(self):
        """Same class a week earlier: another day of issues for the same tutor."""
        return self.env['ems.attendance_session_header'].create({
            'attendance_schedule_id': self.schedule.id, 'date': date.today() - timedelta(days=7),
            'mode': 'scheduled', 'session_teacher_id': self.teacher.id,
        })

    def _tutor_reports(self):
        """Bodies (decoded html) of the emails actually handed to the (mocked) mail server for the tutor."""
        bodies = []
        for call in self.mail_transport.call_args_list:
            message = call.args[0] if call.args else call.kwargs['message']
            if self.tutor_employee.work_email in message['To']:
                bodies.append(''.join(
                    part.get_payload(decode=True).decode() for part in message.walk()
                    if part.get_content_type() == 'text/html'))
        return bodies

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

    # --- one report per tutor, with everything not reported yet --------------------------

    def test_several_days_share_the_tutor_pending_report(self):
        self._mark_miss(self.student1)
        earlier = self._last_week_session()
        self._mark_miss_on(earlier, self.student2)
        job = self._issue_tutor().notification_id
        self.assertTrue(job)
        self.assertEqual(self._issue_tutor(earlier).notification_id, job)
        self.assertEqual(self.env['queue.job'].search_count([
            ('model_name', '=', 'ems.attendance_issue_tutor'), ('state', '=', 'pending'),
            ('id', 'in', (self._issue_tutor() | self._issue_tutor(earlier)).notification_id.ids),
        ]), 1)

    def test_report_lists_every_pending_day_once(self):
        self.mail_transport.reset_mock()
        self._mark_miss(self.student1)
        earlier = self._last_week_session()
        self._mark_miss_on(earlier, self.student2)
        self._issue_tutor().send_notification()

        reports = self._tutor_reports()
        self.assertEqual(len(reports), 1)
        self.assertIn(self.student1.display_name, reports[0])
        self.assertIn(self.student2.display_name, reports[0])
        statuses = (self._issue_tutor() | self._issue_tutor(earlier)).attendance_issue_student_ids.attendance_issue_status_ids
        self.assertTrue(all(statuses.mapped('tutor_notified')))

        self._issue_tutor().send_notification()
        self.assertEqual(len(self._tutor_reports()), 1, "Nothing left to report: no second email")

    def test_issue_recorded_after_the_report_goes_in_the_next_one(self):
        """Used to be lost: the day's job was already done, so nothing was scheduled again."""
        self._mark_miss(self.student1)
        issue_tutor = self._issue_tutor()
        issue_tutor.send_notification()
        issue_tutor.notification_id.state = 'done'

        self._mark_miss(self.student2)
        self.assertEqual(issue_tutor.notification_id.state, 'pending', "No new report scheduled")
        status1 = issue_tutor.attendance_issue_student_ids.filtered(lambda s: s.student_id == self.student1).attendance_issue_status_ids
        status2 = issue_tutor.attendance_issue_student_ids.filtered(lambda s: s.student_id == self.student2).attendance_issue_status_ids
        self.assertEqual(issue_tutor._tutor_report_days()[0]['students'][0]['statuses'], status2)
        self.assertTrue(status1.tutor_notified)
        self.assertFalse(status2.tutor_notified)

    def test_removing_a_day_keeps_the_report_of_the_others(self):
        self._mark_miss(self.student1)
        earlier = self._last_week_session()
        self._mark_miss_on(earlier, self.student2)
        job = self._issue_tutor().notification_id

        line = earlier.attendance_session_line_ids.filtered(lambda l: l.student_id == self.student2)
        line.status_id = self.env.ref('ems.attendance_status_attended')
        self.assertFalse(self._issue_tutor(earlier))
        self.assertEqual(job.state, 'pending')

        line = self.session.attendance_session_line_ids.filtered(lambda l: l.student_id == self.student1)
        line.status_id = self.env.ref('ems.attendance_status_attended')
        self.assertEqual(job.state, 'cancelled', "No day left to report: the job goes")

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
