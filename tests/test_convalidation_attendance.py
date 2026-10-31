from datetime import date, timedelta

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase

from .common import create_role_employee, create_role_user, mock_outgoing_email, shift_ems_clock
from .test_convalidation import create_convalidation_fixtures


class TestConvalidationAttendance(TransactionCase):
    """Issue #644: a subject the applicant chose not to attend while the convalidation is resolved
    leaves the student off its roll-calls ("not required to attend: convalidation in process");
    refused or cancelled, those sessions become absences. See
    docs/en/developers/grades/convalidation.md."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.mail_transport = mock_outgoing_email(cls)
        create_convalidation_fixtures(cls)
        cls.today = shift_ems_clock(cls).date()
        cls.tutor = create_role_user(cls, 'tutor', 'test_convalidation_attendance_tutor', name='Convalidation Attendance Tutor')
        cls.group.tutor_id = create_role_employee(cls, cls.tutor)
        cls.teacher_employee = cls.teacher.employee_ids[:1]
        cls.space = cls.env['ems.space'].create({
            'code': 'TCVA-A', 'name': 'Test Space (Convalidation Attendance)',
            'space_type_id': cls.env.ref('ems.space_type_classroom').id,
            'work_location_id': cls.env.ref('ems.work_location_main').id,
        })
        cls.templates = {}
        for subject in (cls.subject, cls.other_subject):
            cls.env['ems.enrollment'].create({'student_id': cls.student.id, 'group_id': cls.group.id, 'subject_id': subject.id})
            cls.env['ems.teaching'].create({'teacher_id': cls.teacher_employee.id, 'group_id': cls.group.id, 'subject_id': subject.id})
            cls.templates[subject] = cls.env['ems.attendance_template'].create({
                'teacher_ids': [(6, 0, cls.teacher_employee.ids)], 'study_ids': [(6, 0, cls.study.ids)],
                'subject_id': subject.id, 'group_ids': [(6, 0, cls.group.ids)],
                'start_date': date(2020, 1, 1), 'end_date': date(2035, 12, 31),
            })
        cls.miss = cls.env.ref('ems.attendance_status_miss')

    def _request(self, not_attend=None, attend=None, **vals):
        """A request of `not_attend` subjects (won't attend meanwhile) and `attend` ones."""
        lines = [(0, 0, {'subject_id': subject.id, 'attendance_choice': 'not_attend'}) for subject in (not_attend or self.env['ems.subject'])]
        lines += [(0, 0, {'subject_id': subject.id, 'attendance_choice': 'attend'}) for subject in (attend or self.env['ems.subject'])]
        return self.env['ems.convalidation'].create({
            'student_id': self.student.id, 'study_id': self.study.id, 'course_id': self.course.id,
            'line_ids': lines, **vals})

    def _session(self, subject, day=None, start=None):
        """A session of `subject`; each subject at its own time (one teacher teaches both)."""
        day = day or self.today
        start = start or (11.0 if subject == self.subject else 13.0)
        schedule = self.env['ems.attendance_schedule'].create({
            'attendance_template_id': self.templates[subject].id, 'weekday': str(day.weekday()),
            'start_time': start, 'end_time': start + 1, 'space_id': self.space.id,
            'student_ids': [(6, 0, self.student.ids)],
        })
        return self.env['ems.attendance_session_header'].create({
            'attendance_schedule_id': schedule.id, 'date': day, 'mode': 'scheduled',
            'session_teacher_id': self.teacher_employee.id,
        })

    def _line(self, session):
        return session.with_context(active_test=False).all_attendance_session_line_ids.filtered(
            lambda line: line.student_id == self.student)

    def _notices(self, user):
        return self.env['ems.info_notice'].search([
            ('user_id', '=', user.id), ('res_model', '=', 'res.partner'), ('res_id', '=', self.student.id)])

    # --- while the request is open -----------------------------------------------------------

    def test_not_attended_subject_leaves_the_student_off(self):
        request = self._request(not_attend=self.subject, attend=self.other_subject)
        line = self._line(self._session(self.subject))
        self.assertFalse(line.active)
        self.assertEqual(line.not_expected_reason, 'convalidation')
        self.assertEqual(line.convalidation_line_id, request.line_ids.filtered(lambda l: l.subject_id == self.subject))
        self.assertIn('convalidation in process', line.roll_call_label)
        self.assertTrue(self._line(self._session(self.other_subject)).active, "A subject they attend")

    def test_classes_before_the_request_keep_the_student(self):
        self._request(not_attend=self.subject)
        self.assertTrue(self._line(self._session(self.subject, day=self.today - timedelta(days=7))).active)

    def test_teachers_and_tutor_are_told_in_their_summary(self):
        self.mail_transport.reset_mock()
        self._request(not_attend=self.subject, attend=self.other_subject)
        self.mail_transport.assert_not_called()
        for user in (self.teacher, self.tutor):
            notice = self._notices(user)
            self.assertEqual(len(notice), 1)
            self.assertIn(self.subject.display_name, notice.body)
            self.assertNotIn(self.other_subject.display_name, notice.body)

    def test_nobody_is_told_when_every_subject_is_attended(self):
        self._request(attend=self.subject)
        self.assertFalse(self._notices(self.teacher))

    def test_schedule_draws_the_subject_dashed(self):
        self._request(not_attend=self.subject, attend=self.other_subject)
        self.student.invalidate_recordset(['not_expected_subject_ids', 'not_expected_legend'])
        self.assertEqual(self.student.not_expected_subject_ids, self.subject)
        self.assertTrue(self.student.not_expected_legend)

    def test_expected_withdrawal_comes_first(self):
        self._request(not_attend=self.subject)
        self.student.with_user(self.tutor)._ems_mark_withdrawal_expected()
        line = self._line(self._session(self.subject))
        self.assertEqual(line.not_expected_reason, 'withdrawal')
        self.assertFalse(line.convalidation_line_id)

    def test_choice_cannot_change_after_filing(self):
        request = self._request(not_attend=self.subject)
        with self.assertRaises(UserError):
            request.line_ids.with_user(self.head_of_studies).write({'attendance_choice': 'attend'})

    # --- when it ends ---------------------------------------------------------------------

    def test_cancelled_request_turns_the_sessions_into_absences(self):
        request = self._request(not_attend=self.subject)
        session = self._session(self.subject)
        request.with_user(self.head_of_studies)._ems_cancel("Withdrawn")
        line = self._line(session)
        self.assertTrue(line.active)
        self.assertEqual(line.status_id, self.miss)
        self.assertFalse(line.not_expected_reason)
        status = self.env['ems.attendance_issue_status'].search([('attendance_session_line_id', '=', line.id)])
        self.assertFalse(status.notification_id, "No email to the family")
        self.assertEqual(len(self._notices(self.teacher)), 2, "Filed, then cancelled")
        self.assertTrue(self._line(self._session(self.subject, start=15.0)).active, "Expected again")

    def test_refused_subject_back_granted_one_stays_off(self):
        request = self._request(not_attend=self.subject | self.other_subject)
        refused_session, granted_session = self._session(self.other_subject), self._session(self.subject)
        hos_lines = request.line_ids.with_user(self.head_of_studies)
        hos_lines.filtered(lambda l: l.subject_id == self.subject).action_grant()
        refused = hos_lines.filtered(lambda l: l.subject_id == self.other_subject)
        refused.write({'rejection_reason': "Not equivalent"})
        refused.action_reject()
        self.assertFalse(self._line(refused_session).active, "Only once the resolution is final")
        request.with_user(self.head_of_studies).action_propose()
        request.with_user(self.director).action_resolve()
        request.with_user(self.secretary).action_complete()
        self.assertTrue(self._line(refused_session).active)
        self.assertEqual(self._line(refused_session).status_id, self.miss)
        self.assertFalse(self._line(granted_session).active, "Convalidated: never required to attend it")

    def test_subject_removed_from_the_request_goes_back(self):
        request = self._request(not_attend=self.subject | self.other_subject)
        session = self._session(self.other_subject)
        request.line_ids.filtered(lambda l: l.subject_id == self.other_subject).unlink()
        self.assertTrue(self._line(session).active)
        self.assertEqual(self._line(session).status_id, self.miss)

    def test_changing_the_subject_puts_the_old_one_back(self):
        request = self._request(not_attend=self.other_subject)
        session = self._session(self.other_subject)
        request.line_ids.with_user(self.head_of_studies).write({'subject_id': self.subject.id})
        self.assertTrue(self._line(session).active)
        self.assertEqual(self._line(session).status_id, self.miss)

    def test_reopened_request_takes_the_student_off_again(self):
        request = self._request(not_attend=self.subject)
        request.with_user(self.head_of_studies)._ems_cancel()
        request.with_user(self.head_of_studies).action_reopen()
        self.assertFalse(self._line(self._session(self.subject)).active)

    # --- notice text ------------------------------------------------------------------------

    def test_attendance_notice_standard_or_own(self):
        company = self.env.company
        company.convalidation_attendance_notice = False
        self.assertIn('NOFC', company._ems_convalidation_attendance_notice())
        company.convalidation_attendance_notice = '<p>Our own rules</p>'
        self.assertIn('Our own rules', company._ems_convalidation_attendance_notice())
