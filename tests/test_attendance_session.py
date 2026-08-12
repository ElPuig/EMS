from datetime import date, datetime

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase

from .common import create_level_study, mock_outgoing_email


class TestAttendanceSessionHeader(TransactionCase):
    """models/attendance/attendance_session.py — EmsAttendanceSessionHeader.
    Zero test coverage existed before this pass. Covers computed fields
    (all derived from attendance_schedule_id -> attendance_template_id),
    the duplicate-session sql constraint, _auto_populate_lines' two
    branches (fresh session vs. same-day continuation), copy()/unlink(),
    and the guard-mode RPC endpoints. The email-sending notification
    pipeline's own models (ems.attendance_issue_tutor/_student/_status,
    models/attendance/attendance_issue.py) get their own DTON pass and
    tests — this file only verifies that pipeline's *data* gets created
    correctly (a queue.job gets queued), never lets send_notification()
    actually run (no queue_job__no_delay context is used anywhere here),
    so no real email is ever at risk of being sent."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.level, cls.study = create_level_study(cls, 'TAS', level={'name': 'Test Level (Attendance Session)'}, study={
            'code': 'TAS001', 'name': 'Test Study (Attendance Session)', 'date': date.today(),
        })
        cls.subject = cls.env['ems.subject'].create({
            'code': 'TAS001', 'acronym': 'TAS', 'name': 'Test Subject (Attendance Session)',
            'study_ids': [(6, 0, [cls.study.id])],
        })
        cls.group = cls.env['ems.group'].create({
            'course': 1, 'acronym': 'TAS', 'level_id': cls.level.id, 'study_id': cls.study.id,
        })
        cls.space = cls.env['ems.space'].create({
            'code': 'TAS-A', 'name': 'Test Space (Attendance Session)',
            'space_type_id': cls.env.ref('ems.space_type_classroom').id,
            'work_location_id': cls.env.ref('ems.work_location_main').id,
        })
        cls.teacher_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Teacher User (Attendance Session)', 'login': 'test_teacher_tas',
            'groups_id': [(4, cls.env.ref('ems.group_teacher').id), (4, cls.env.ref('base.group_user').id)],
        })
        cls.teacher = cls.env['hr.employee'].create({
            'name': 'Test Teacher (Attendance Session)', 'employee_type': 'teacher',
            'user_id': cls.teacher_user.id,
        })
        cls.student1 = cls.env['res.partner'].create({'name': 'Session Student 1', 'contact_type': 'student'})
        cls.student2 = cls.env['res.partner'].create({'name': 'Session Student 2', 'contact_type': 'student'})
        cls.template = cls.env['ems.attendance_template'].create({
            'teacher_ids': [(6, 0, [cls.teacher.id])], 'study_ids': [(6, 0, [cls.study.id])],
            'subject_id': cls.subject.id, 'group_ids': [(6, 0, [cls.group.id])],
            'start_date': date(2020, 1, 1), 'end_date': date(2030, 12, 31),
        })
        # student_ids lives on the schedule line, not the template (see
        # plans/calendar_driven_attendance_templates.md, point 1).
        cls.schedule = cls.env['ems.attendance_schedule'].create({
            'attendance_template_id': cls.template.id, 'weekday': str(date.today().weekday()),
            'start_time': 8.0, 'end_time': 9.0, 'space_id': cls.space.id,
            'student_ids': [(6, 0, [cls.student1.id, cls.student2.id])],
        })
        cls.schedule2 = cls.env['ems.attendance_schedule'].create({
            'attendance_template_id': cls.template.id, 'weekday': str(date.today().weekday()),
            'start_time': 9.0, 'end_time': 10.0, 'space_id': cls.space.id,
            'student_ids': [(6, 0, [cls.student1.id, cls.student2.id])],
        })

    # --- computed fields ---------------------------------------------------------------

    def test_computed_fields_derive_from_schedule_and_template(self):
        session = self.env['ems.attendance_session_header'].create({
            'attendance_schedule_id': self.schedule.id, 'date': date.today(),
            'mode': 'scheduled', 'session_teacher_id': self.teacher.id,
        })
        self.assertEqual(session.weekday, self.schedule.weekday)
        self.assertEqual(session.start_time, 8.0)
        self.assertEqual(session.end_time, 9.0)
        self.assertEqual(session.time_range, self.schedule.time_range)
        self.assertEqual(session.level_id, self.level)
        self.assertEqual(session.study_ids, self.study)
        self.assertEqual(session.group_ids, self.group)
        self.assertEqual(session.subject_id, self.subject)
        self.assertEqual(session.space_id, self.space)
        self.assertEqual(session.template_teacher_ids, self.teacher)

    def test_space_id_comes_from_schedule_line_not_template(self):
        # Regression guard for the 2026-08-01 room-granularity change: a schedule line's own room
        # can diverge from another line's own room on the same template (e.g. a one-off room
        # reassignment) - the session must reflect THIS line's actual room. 'ems.attendance_
        # template' has no 'space_id' of its own at all any more (removed 2026-08-11, room is
        # exclusively a schedule-line concept now - see docs/en/developers/attendance/
        # attendance_template.md), so there's no template-level room left to compare against;
        # 'schedule2' (same template, its own unrelated room) is the real differentiator now.
        other_space = self.env['ems.space'].create({
            'code': 'TAS-B', 'name': 'Test Space B (Attendance Session)',
            'space_type_id': self.env.ref('ems.space_type_classroom').id,
            'work_location_id': self.env.ref('ems.work_location_main').id,
        })
        # ems_bypass_template_lock: 'space_id' is otherwise locked on the schedule line (2026-08-11
        # refinement) - this test simulates what the sync pipeline would legitimately produce for a
        # one-off room reassignment, not a direct admin edit.
        self.schedule.with_context(ems_bypass_template_lock=True).write({'space_id': other_space.id})

        session = self.env['ems.attendance_session_header'].create({
            'attendance_schedule_id': self.schedule.id, 'date': date.today(),
            'mode': 'scheduled', 'session_teacher_id': self.teacher.id,
        })

        self.assertEqual(session.space_id, other_space)
        self.assertNotEqual(session.space_id, self.schedule2.space_id)

    # --- sql constraint ----------------------------------------------------------------

    def test_duplicate_session_same_schedule_and_date_raises(self):
        self.env['ems.attendance_session_header'].create({
            'attendance_schedule_id': self.schedule.id, 'date': date.today(),
            'mode': 'scheduled', 'session_teacher_id': self.teacher.id,
        })
        with self.assertRaises(ValidationError):
            self.env['ems.attendance_session_header'].create({
                'attendance_schedule_id': self.schedule.id, 'date': date.today(),
                'mode': 'scheduled', 'session_teacher_id': self.teacher.id,
            })

    # --- _auto_populate_lines -----------------------------------------------------------

    def test_fresh_session_populates_one_line_per_template_student(self):
        session = self.env['ems.attendance_session_header'].create({
            'attendance_schedule_id': self.schedule.id, 'date': date.today(),
            'mode': 'scheduled', 'session_teacher_id': self.teacher.id,
        })
        self.assertEqual(len(session.attendance_session_line_ids), 2)
        self.assertEqual(
            set(session.attendance_session_line_ids.mapped('student_id')),
            {self.student1, self.student2},
        )
        self.assertTrue(all(session.attendance_session_line_ids.mapped('is_auto_generated')))

    def test_continuation_session_carries_over_previous_status(self):
        first = self.env['ems.attendance_session_header'].create({
            'attendance_schedule_id': self.schedule.id, 'date': date.today(),
            'mode': 'scheduled', 'session_teacher_id': self.teacher.id,
        })
        delayed = self.env.ref('ems.attendance_status_delayed')
        first_line = first.attendance_session_line_ids.filtered(lambda l: l.student_id == self.student1)
        first_line.status_id = delayed

        second = self.env['ems.attendance_session_header'].create({
            'attendance_schedule_id': self.schedule2.id, 'date': date.today(),
            'mode': 'scheduled', 'session_teacher_id': self.teacher.id,
        })
        second_line = second.attendance_session_line_ids.filtered(lambda l: l.student_id == self.student1)
        # delayed carries forward as attended (a delay only applies to the first period).
        self.assertEqual(second_line.status_id, self.env.ref('ems.attendance_status_attended'))

    def test_continuation_session_justified_becomes_miss(self):
        first = self.env['ems.attendance_session_header'].create({
            'attendance_schedule_id': self.schedule.id, 'date': date.today(),
            'mode': 'scheduled', 'session_teacher_id': self.teacher.id,
        })
        justified = self.env.ref('ems.attendance_status_justified')
        first_line = first.attendance_session_line_ids.filtered(lambda l: l.student_id == self.student1)
        first_line.status_id = justified

        second = self.env['ems.attendance_session_header'].create({
            'attendance_schedule_id': self.schedule2.id, 'date': date.today(),
            'mode': 'scheduled', 'session_teacher_id': self.teacher.id,
        })
        second_line = second.attendance_session_line_ids.filtered(lambda l: l.student_id == self.student1)
        self.assertEqual(second_line.status_id, self.env.ref('ems.attendance_status_miss'))

    # --- copy / unlink -------------------------------------------------------------------

    def test_copy_is_blocked(self):
        session = self.env['ems.attendance_session_header'].create({
            'attendance_schedule_id': self.schedule.id, 'date': date.today(),
            'mode': 'scheduled', 'session_teacher_id': self.teacher.id,
        })
        with self.assertRaises(UserError):
            session.copy()

    def test_unlink_without_issues_succeeds(self):
        session = self.env['ems.attendance_session_header'].create({
            'attendance_schedule_id': self.schedule.id, 'date': date.today(),
            'mode': 'scheduled', 'session_teacher_id': self.teacher.id,
        })
        session.unlink()
        self.assertFalse(session.exists())

    # --- guard mode ------------------------------------------------------------------------

    def test_guard_sessions_requires_teacher_access(self):
        portal_user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Non Teacher (Attendance Session)', 'login': 'test_non_teacher_tas',
            'groups_id': [(4, self.env.ref('base.group_user').id)],
        })
        with self.assertRaises(AccessError):
            self.env['ems.attendance_session_header'].with_user(portal_user).get_guard_sessions(
                date.today().isoformat())

    def test_guard_sessions_returns_other_teachers_sessions(self):
        other_teacher_user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Other Teacher User (Attendance Session)', 'login': 'test_other_teacher_tas',
            'groups_id': [(4, self.env.ref('ems.group_teacher').id), (4, self.env.ref('base.group_user').id)],
        })
        self.env['hr.employee'].create({
            'name': 'Other Teacher (Attendance Session)', 'employee_type': 'teacher',
            'user_id': other_teacher_user.id,
        })
        self.env['ems.attendance_session_header'].create({
            'attendance_schedule_id': self.schedule.id, 'date': date.today(),
            'mode': 'scheduled', 'session_teacher_id': self.teacher.id,
        })
        result = self.env['ems.attendance_session_header'].with_user(other_teacher_user).get_guard_sessions(
            date.today().isoformat())
        self.assertEqual(len(result), 1)

    def test_create_scheduled_session_marks_continuation(self):
        first = self.env['ems.attendance_session_header'].create({
            'attendance_schedule_id': self.schedule.id, 'date': date.today(),
            'mode': 'scheduled', 'session_teacher_id': self.teacher.id,
        })
        result = self.env['ems.attendance_session_header'].with_user(self.teacher_user).create_scheduled_session(
            date.today().isoformat(), self.schedule2.id)
        self.assertTrue(result['is_continuation'])


class TestAttendanceSessionLine(TransactionCase):
    """ems.attendance_session_line — the per-student status row.

    status_is_notificable() (already covered by test_attendance_status.py),
    absence_rate (test_attendance_reports.py), strike_count and
    action_view_strikes() (test_strike.py) are deliberately not re-tested
    here — found duplicated verbatim during the post-DTON test-redundancy
    audit and trimmed to the file that already owns each concern."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # send_mail(force_send=True) can fire from _update_notification's queued job
        # if a test ever runs with queue_job__no_delay — none do here, but mock
        # regardless per CLAUDE.md's email-safety rule (defense in depth).
        mock_outgoing_email(cls)

        cls.level, cls.study = create_level_study(cls, 'TASL2', level={'name': 'Test Level (Attendance Session Line)'}, study={
            'code': 'TASL2', 'name': 'Test Study (Attendance Session Line)', 'date': date.today(),
        })
        cls.subject = cls.env['ems.subject'].create({
            'code': 'TASL2', 'acronym': 'TASL2', 'name': 'Test Subject (Attendance Session Line)',
            'study_ids': [(6, 0, [cls.study.id])],
        })
        cls.group = cls.env['ems.group'].create({
            'course': 1, 'acronym': 'TASL2', 'level_id': cls.level.id, 'study_id': cls.study.id,
        })
        cls.space = cls.env['ems.space'].create({
            'code': 'TASL2-A', 'name': 'Test Space (Attendance Session Line)',
            'space_type_id': cls.env.ref('ems.space_type_classroom').id,
            'work_location_id': cls.env.ref('ems.work_location_main').id,
        })
        cls.teacher = cls.env['hr.employee'].create({
            'name': 'Test Teacher (Attendance Session Line)', 'employee_type': 'teacher',
        })
        cls.tutor_employee = cls.env['hr.employee'].create({
            'name': 'Test Tutor (Attendance Session Line)', 'employee_type': 'teacher',
        })
        cls.tutor_group = cls.env['ems.group'].create({
            'course': 1, 'acronym': 'TASL2T', 'level_id': cls.level.id, 'study_id': cls.study.id,
            'tutor_id': cls.tutor_employee.id,
        })
        cls.student = cls.env['res.partner'].create({
            'name': 'Session Line Student', 'contact_type': 'student', 'main_group_id': cls.tutor_group.id,
        })
        cls.template = cls.env['ems.attendance_template'].create({
            'teacher_ids': [(6, 0, [cls.teacher.id])], 'study_ids': [(6, 0, [cls.study.id])],
            'subject_id': cls.subject.id, 'group_ids': [(6, 0, [cls.group.id])],
            'start_date': date(2020, 1, 1), 'end_date': date(2030, 12, 31),
        })
        cls.schedule = cls.env['ems.attendance_schedule'].create({
            'attendance_template_id': cls.template.id, 'weekday': str(date.today().weekday()),
            'start_time': 8.0, 'end_time': 9.0, 'space_id': cls.space.id,
            'student_ids': [(6, 0, [cls.student.id])],
        })
        cls.session = cls.env['ems.attendance_session_header'].create({
            'attendance_schedule_id': cls.schedule.id, 'date': date.today(),
            'mode': 'scheduled', 'session_teacher_id': cls.teacher.id,
        })

    def _line(self):
        return self.session.attendance_session_line_ids.filtered(lambda l: l.student_id == self.student)

    def test_compute_display_name(self):
        line = self._line()
        self.assertIn(self.student.display_name, line.display_name)

    def test_inuse_student_ids_includes_all_session_students(self):
        line = self._line()
        self.assertIn(self.student, line.inuse_student_ids)

    def test_marking_miss_creates_issue_tracking_data_without_sending(self):
        """Verifies the notification *data* pipeline (issue_tutor/student/status
        creation) without ever letting send_notification() actually run — no test
        here uses queue_job__no_delay, so the queued job never executes within
        the test transaction; only its data-layer side effects are asserted."""
        line = self._line()
        line.status_id = self.env.ref('ems.attendance_status_miss')

        issue_tutor = self.env['ems.attendance_issue_tutor'].search([
            ('tutor_id', '=', self.tutor_employee.id), ('issue_date', '=', self.session.date),
        ])
        self.assertTrue(issue_tutor)
        issue_student = issue_tutor.attendance_issue_student_ids.filtered(
            lambda s: s.student_id == self.student)
        self.assertTrue(issue_student)
        self.assertTrue(issue_student.attendance_issue_status_ids)

    def test_marking_back_to_non_notifiable_removes_unnotified_issue(self):
        line = self._line()
        line.status_id = self.env.ref('ems.attendance_status_miss')
        line.status_id = self.env.ref('ems.attendance_status_attended')

        issue_tutor = self.env['ems.attendance_issue_tutor'].search([
            ('tutor_id', '=', self.tutor_employee.id), ('issue_date', '=', self.session.date),
        ])
        # The tutor entry is cleaned up once it has no more students attached
        # (see unlink()'s own remove_if_empty() cascade — mirrored here for a
        # plain status flip back to non-notifiable).
        if issue_tutor:
            self.assertFalse(issue_tutor.attendance_issue_student_ids)

