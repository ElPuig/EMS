from datetime import date

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase

from .common import (create_level_study, create_role_employee, create_role_user, mock_outgoing_email,
                     next_student_id, shift_ems_clock)


class TestAttendanceNotExpected(TransactionCase):
    """Expected withdrawal (issue #644, models/contacts/withdrawal_expected.py): while it lasts the
    student starts off every roll-call ("not required to attend", an archived line with its reason);
    reverting it turns those sessions into absences without notifying the family. See
    docs/en/developers/contacts/withdrawal_expected.md."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.now = shift_ems_clock(cls)  # 10:00 of the company's day
        cls.today = cls.now.date()
        cls.mail_transport = mock_outgoing_email(cls)

        cls.level, cls.study = create_level_study(cls, 'TANE', study={
            'name': 'Test Study (Not Expected)', 'date': cls.today,
        }, level={'name': 'Test Level (Not Expected)'})
        cls.subject = cls.env['ems.subject'].create({
            'code': 'TANE001', 'acronym': 'TANE', 'name': 'Test Subject (Not Expected)',
            'study_ids': [(6, 0, [cls.study.id])],
        })
        cls.space = cls.env['ems.space'].create({
            'code': 'TANE-A', 'name': 'Test Space (Not Expected)',
            'space_type_id': cls.env.ref('ems.space_type_classroom').id,
            'work_location_id': cls.env.ref('ems.work_location_main').id,
        })
        cls.tutor_user = create_role_user(cls, 'tutor', 'not_expected_tutor', email='ne.tutor@example.com')
        cls.tutor = create_role_employee(cls, cls.tutor_user)
        cls.teacher_user = create_role_user(cls, 'teacher', 'not_expected_teacher', email='ne.teacher@example.com')
        cls.teacher = create_role_employee(cls, cls.teacher_user)
        cls.group = cls.env['ems.group'].create({
            'course': 1, 'acronym': 'TANE', 'level_id': cls.level.id, 'study_id': cls.study.id,
            'tutor_id': cls.tutor.id,
        })
        cls.env['ems.teaching'].create({'teacher_id': cls.teacher.id, 'group_id': cls.group.id, 'subject_id': cls.subject.id})
        cls.student = cls.env['res.partner'].create({
            'name': 'Not Expected Student', 'contact_type': 'student', 'student_id': next_student_id(),
            'main_group_id': cls.group.id, 'student_email': 'ne.student@example.com',
        })
        cls.classmate = cls.env['res.partner'].create({
            'name': 'Not Expected Classmate', 'contact_type': 'student', 'student_id': next_student_id(),
            'main_group_id': cls.group.id,
        })
        cls.env['ems.enrollment'].create({'student_id': cls.student.id, 'group_id': cls.group.id, 'subject_id': cls.subject.id})
        cls.template = cls.env['ems.attendance_template'].create({
            'teacher_ids': [(6, 0, [cls.teacher.id])], 'study_ids': [(6, 0, [cls.study.id])],
            'subject_id': cls.subject.id, 'group_ids': [(6, 0, [cls.group.id])],
            'start_date': date(2020, 1, 1), 'end_date': date(2035, 12, 31),
        })
        cls.miss = cls.env.ref('ems.attendance_status_miss')
        cls.attended = cls.env.ref('ems.attendance_status_attended')

    def _session(self, start, end, day=None):
        schedule = self.env['ems.attendance_schedule'].create({
            'attendance_template_id': self.template.id, 'weekday': str((day or self.today).weekday()),
            'start_time': start, 'end_time': end, 'space_id': self.space.id,
            'student_ids': [(6, 0, [self.student.id, self.classmate.id])],
        }) if (start, end) not in self._schedules else self._schedules[(start, end)]
        self._schedules[(start, end)] = schedule
        return self.env['ems.attendance_session_header'].create({
            'attendance_schedule_id': schedule.id, 'date': day or self.today,
            'mode': 'scheduled', 'session_teacher_id': self.teacher.id,
        })

    def setUp(self):
        super().setUp()
        self._schedules = {}

    def _line(self, session, student=None):
        return session.with_context(active_test=False).all_attendance_session_line_ids.filtered(
            lambda line: line.student_id == (student or self.student))

    def _mark(self, user=None, note=False):
        self.student.with_user(user or self.tutor_user)._ems_mark_withdrawal_expected(note)

    def _notices(self, user):
        return self.env['ems.info_notice'].search([('user_id', '=', user.id), ('res_id', '=', self.student.id),
                                                   ('res_model', '=', 'res.partner')])

    # --- marking -----------------------------------------------------------------------------

    def test_roll_calls_after_the_mark_leave_the_student_off(self):
        self._mark(note='Moving abroad')
        self.assertTrue(self.student.withdrawal_expected)
        self.assertEqual(self.student.withdrawal_expected_by_id, self.tutor_user)
        self.assertEqual(self.student.withdrawal_expected_note, 'Moving abroad')
        session = self._session(11.0, 12.0)
        line = self._line(session)
        self.assertFalse(line.active)
        self.assertEqual(line.not_expected_reason, 'withdrawal')
        self.assertIn('expected withdrawal', line.roll_call_label)
        self.assertTrue(self._line(session, self.classmate).active, "Only the student")

    def test_classes_before_the_mark_keep_the_student(self):
        """A roll-call taken late for a class that started before the mark: the student was still expected."""
        self._mark()
        self.assertTrue(self._line(self._session(8.0, 9.0)).active)

    def test_mark_takes_off_the_sessions_already_taken_later_today(self):
        later = self._session(11.0, 12.0)
        delayed = self._session(12.0, 13.0)
        self._line(delayed).status_id = self.env.ref('ems.attendance_status_delayed')
        earlier = self._session(8.0, 9.0)
        self._mark()
        self.assertFalse(self._line(later).active)
        self.assertEqual(self._line(later).not_expected_reason, 'withdrawal')
        self.assertTrue(self._line(delayed).active, "A status set on purpose is left alone")
        self.assertTrue(self._line(earlier).active, "Before the mark")

    def test_mark_queues_a_notice_for_teachers_and_tutor(self):
        self.mail_transport.reset_mock()
        self._mark()
        self.mail_transport.assert_not_called()
        self.assertEqual(len(self._notices(self.teacher_user)), 1)
        self.assertEqual(len(self._notices(self.tutor_user)), 1)
        self.assertIn('Not Expected Student', self._notices(self.teacher_user).body)

    def test_notices_only_reach_teachers_of_the_student(self):
        other_teacher = create_role_user(self, 'teacher', 'not_expected_other_teacher', name='Not Expected Other Teacher')
        other_subject = self.env['ems.subject'].create({
            'code': 'TANE002', 'acronym': 'TAN2', 'name': 'Other Subject (Not Expected)',
            'study_ids': [(6, 0, [self.study.id])]})
        self.env['ems.teaching'].create({'teacher_id': create_role_employee(self, other_teacher).id,
                                         'group_id': self.group.id, 'subject_id': other_subject.id})
        self._mark()
        self.assertFalse(self._notices(other_teacher), "Teaches the group, not this student")

    def test_ribbon_and_schedule(self):
        self._mark()
        self.assertEqual(self.student.archived_reason_label, 'Expected withdrawal')
        self.assertEqual(self.student.not_expected_subject_ids, self.subject)
        self.assertTrue(self.student.not_expected_legend)
        self.assertFalse(self.classmate.archived_reason_label)
        self.assertFalse(self.classmate.not_expected_subject_ids)

    # --- reverting -----------------------------------------------------------------------------

    def test_revert_turns_the_sessions_into_absences(self):
        self._mark()
        first, second = self._session(11.0, 12.0), self._session(12.0, 13.0)
        self.student.with_user(self.tutor_user).action_revert_withdrawal_expected()
        self.assertFalse(self.student.withdrawal_expected)
        self.assertFalse(self.student.archived_reason_label)
        for session in (first, second):
            line = self._line(session)
            self.assertTrue(line.active)
            self.assertEqual(line.status_id, self.miss)
            self.assertFalse(line.not_expected_reason)
        self.assertTrue(self._line(self._session(13.0, 14.0)).active, "Expected again from now on")

    def test_revert_does_not_notify_the_family_but_the_tutor(self):
        self._mark()
        session = self._session(11.0, 12.0)
        self.student.with_user(self.tutor_user).action_revert_withdrawal_expected()
        status = self.env['ems.attendance_issue_status'].search([('attendance_session_line_id', '=', self._line(session).id)])
        self.assertTrue(status, "The tutor gets the absence in their daily summary")
        self.assertFalse(status.notification_id, "No email to the family")
        self.assertFalse(status.tutor_notified)
        self.assertTrue(self.tutor_user.ems_digest_next)
        self.assertEqual(len(self._notices(self.teacher_user)), 2, "Marked, then reverted")

    def test_revert_keeps_a_justified_session_justified(self):
        self._mark()
        self.env['ems.attendance_justification'].with_user(self.tutor_user).create({
            'student_id': self.student.id, 'teacher_id': self.tutor.id,
            'start_date': self.env['ems.datetime_utils'].datetime_to_odoo(
                self.env['ems.datetime_utils'].time_float_to_utc_datetime(self.today, 10.5)),
            'end_date': self.env['ems.datetime_utils'].datetime_to_odoo(
                self.env['ems.datetime_utils'].time_float_to_utc_datetime(self.today, 13.5)),
        })
        line = self._line(self._session(11.0, 12.0))
        self.assertTrue(line.attendance_prevision_id)
        self.student.with_user(self.tutor_user).action_revert_withdrawal_expected()
        self.assertTrue(line.active)
        self.assertEqual(line.status_id, self.env.ref('ems.attendance_status_justified'))

    def test_revert_leaves_removals_by_hand_alone(self):
        session = self._session(11.0, 12.0)
        self._line(session, self.classmate).active = False
        self._mark()
        self.student.with_user(self.tutor_user).action_revert_withdrawal_expected()
        self.assertFalse(self._line(session, self.classmate).active)

    def test_teacher_putting_the_student_back_clears_the_reason(self):
        self._mark()
        line = self._line(self._session(11.0, 12.0))
        line.with_user(self.teacher_user).write({'active': True, 'status_id': self.attended.id})
        self.assertFalse(line.not_expected_reason)
        self.student.with_user(self.tutor_user).action_revert_withdrawal_expected()
        self.assertEqual(line.status_id, self.attended, "They came: not turned into an absence")

    def test_next_period_reevaluates_the_reason(self):
        """Consecutive periods of the same class carry the previous line over: a removal by hand
        carries, one made for a reason only while it still applies."""
        self._mark()
        first = self._session(11.0, 12.0)
        self._line(first, self.classmate).active = False
        self.student.sudo().write({'withdrawal_expected': False})  # reason gone, lines untouched
        second = self._session(12.0, 13.0)
        self.assertTrue(self._line(second).active)
        self.assertFalse(self._line(second).not_expected_reason)
        self.assertFalse(self._line(second, self.classmate).active)

    # --- leaving ---------------------------------------------------------------------------

    def test_registering_the_exit_clears_the_mark_and_keeps_the_lines(self):
        self._mark()
        line = self._line(self._session(11.0, 12.0))
        self.student._ems_clear_withdrawal_expected()
        self.assertFalse(self.student.withdrawal_expected)
        self.assertFalse(line.active)
        self.assertEqual(line.not_expected_reason, 'withdrawal')

    # --- who --------------------------------------------------------------------------------

    def test_who_can_mark(self):
        self.assertTrue(self.student.with_user(self.tutor_user).can_mark_withdrawal_expected)
        self.assertFalse(self.student.with_user(self.teacher_user).can_mark_withdrawal_expected)
        with self.assertRaises(UserError):
            self._mark(self.teacher_user)
        for role in ('secretary', 'academic_admin', 'settings_admin'):
            user = create_role_user(self, role, f'not_expected_{role}')
            self.assertTrue(self.student.with_user(user).can_mark_withdrawal_expected, role)
        other_chief = create_role_user(self, 'department_chief', 'not_expected_other_chief')
        create_role_employee(self, other_chief)
        self.assertFalse(self.student.with_user(other_chief).can_mark_withdrawal_expected,
                         "A Department Chief of another branch is not above this tutor")

    def test_chief_above_the_tutor_can_mark(self):
        chief = create_role_user(self, 'department_chief', 'not_expected_chief')
        self.tutor.parent_id = create_role_employee(self, chief)
        self.assertTrue(self.student.with_user(chief).can_mark_withdrawal_expected)

    def test_wizard(self):
        action = self.student.with_user(self.tutor_user).action_withdrawal_expected_wizard()
        wizard = self.env['ems.withdrawal_expected_wizard'].with_user(self.tutor_user).with_context(
            action['context']).create({'note': 'Wizard note'})
        wizard.action_confirm()
        self.assertTrue(self.student.withdrawal_expected)
        self.assertEqual(self.student.withdrawal_expected_note, 'Wizard note')
