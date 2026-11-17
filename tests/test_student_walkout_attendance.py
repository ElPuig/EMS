from datetime import date, timedelta

from odoo.tests.common import TransactionCase, tagged

from .common import create_role_employee, create_role_user, mock_outgoing_email
from .test_student_walkout import create_walkout_fixtures, end_phase, open_walkout, ratify, reject_walkout


@tagged('post_install', '-at_install')
class TestStudentWalkoutAttendance(TransactionCase):
    """Issue #844: every student who joins a student walkout is off the roll-calls of its day ("not
    required to attend: student walkout", an archived line with its reason), from when joining closes
    with the group's support: neither an absence nor a presence. Nothing is justified. The family of a
    minor who joins without its ratification is told of each class, for information only. Not
    validating the walkout turns those classes into regular absences. See
    docs/en/developers/attendance/student_walkout.md."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        create_walkout_fixtures(cls, 'WLA')
        cls.subject = cls.env['ems.subject'].create({
            'code': 'WLA001', 'acronym': 'WLA', 'name': 'Test Subject (Walkout attendance)',
            'study_ids': [(6, 0, [cls.study.id])],
        })
        cls.space = cls.env['ems.space'].create({
            'code': 'WLA-A', 'name': 'Test Space (Walkout attendance)',
            'space_type_id': cls.env.ref('ems.space_type_classroom').id,
            'work_location_id': cls.env.ref('ems.work_location_main').id,
        })
        cls.teacher_user = create_role_user(cls, 'teacher', 'test_walkout_attendance_teacher',
                                            email='teacher.wla@example.com')
        cls.teacher = create_role_employee(cls, cls.teacher_user)
        cls.env['ems.teaching'].create({'teacher_id': cls.teacher.id, 'group_id': cls.group.id,
                                        'subject_id': cls.subject.id})
        cls.students = cls.delegate | cls.subdelegate | cls.classmate | cls.offline
        cls.template = cls.env['ems.attendance_template'].create({
            'teacher_ids': [(6, 0, [cls.teacher.id])], 'study_ids': [(6, 0, [cls.study.id])],
            'subject_id': cls.subject.id, 'group_ids': [(6, 0, [cls.group.id])],
            'start_date': date(2020, 1, 1), 'end_date': date(2035, 12, 31),
        })
        cls.miss = cls.env.ref('ems.attendance_status_miss')

    def setUp(self):
        super().setUp()
        self._schedules = {}

    def _session(self, day, start=11.0, end=12.0):
        key = (day.weekday(), start, end)
        if key not in self._schedules:
            self._schedules[key] = self.env['ems.attendance_schedule'].create({
                'attendance_template_id': self.template.id, 'weekday': str(day.weekday()),
                'start_time': start, 'end_time': end, 'space_id': self.space.id,
                'student_ids': [(6, 0, self.students.ids)],
            })
        return self.env['ems.attendance_session_header'].create({
            'attendance_schedule_id': self._schedules[key].id, 'date': day, 'mode': 'scheduled',
            'session_teacher_id': self.teacher.id,
        })

    def _line(self, session, student):
        return session.with_context(active_test=False).all_attendance_session_line_ids.filtered(
            lambda line: line.student_id == student)

    def _notices(self, line):
        return self.env['ems.attendance_issue_status'].sudo().search([('attendance_session_line_id', '=', line.id)])

    def _closed(self, ratifies=None):
        """A walkout the group supports, joined by the delegate (an adult), the sub-delegate and the
        classmate (minors); the sub-delegate's family ratifies it (or answers `ratifies`), the
        classmate's has not answered. Joining is closed."""
        walkout = open_walkout(self)
        walkout._ems_portal_vote(self.delegate, 'yes')
        walkout._ems_portal_vote(self.subdelegate, 'yes')
        for student in (self.delegate, self.subdelegate, self.classmate):
            walkout._ems_portal_join(student, True)
        ratify(walkout, self.family, self.subdelegate, True if ratifies is None else ratifies)
        end_phase(walkout)
        self.assertEqual(walkout.state, 'closed')
        return walkout

    # Off the roll-call

    def test_every_student_who_joins_is_off_the_roll_calls_of_the_day(self):
        walkout = self._closed()
        session = self._session(walkout.walkout_date)
        for student in (self.delegate, self.subdelegate, self.classmate):
            line = self._line(session, student)
            self.assertFalse(line.active, student.name)
            self.assertEqual(line.not_expected_reason, 'walkout', student.name)
            self.assertIn('student walkout', line.roll_call_label)
        self.assertTrue(self._line(session, self.offline).active, "Who does not join is expected in class.")
        self.assertFalse(walkout.line_ids.filtered('joins').mapped('student_id').filtered(
            lambda student: self.env['ems.attendance_justification'].search_count([('student_ids', 'in', student.ids)])),
            "Nothing is justified.")

    def test_the_label_says_when_the_family_will_be_told(self):
        walkout = self._closed()
        session = self._session(walkout.walkout_date)
        self.assertIn('not ratified', self._line(session, self.classmate).roll_call_label)
        self.assertNotIn('not ratified', self._line(session, self.subdelegate).roll_call_label)
        self.assertNotIn('not ratified', self._line(session, self.delegate).roll_call_label)

    def test_other_days_are_not_touched(self):
        walkout = self._closed()
        session = self._session(walkout.walkout_date - timedelta(days=7))
        self.assertTrue(self._line(session, self.delegate).active)

    def test_roll_calls_taken_before_closing_are_updated(self):
        walkout = open_walkout(self)
        walkout._ems_portal_vote(self.delegate, 'yes')
        walkout._ems_portal_vote(self.subdelegate, 'yes')
        walkout._ems_portal_join(self.delegate, True)
        session = self._session(walkout.walkout_date)
        self.assertTrue(self._line(session, self.delegate).active, "Joining is still open.")
        end_phase(walkout)
        line = self._line(session, self.delegate)
        self.assertEqual((line.active, line.not_expected_reason), (False, 'walkout'))
        self.assertTrue(self._line(session, self.classmate).active)

    def test_a_group_that_does_not_support_it_keeps_its_roll_calls(self):
        walkout = open_walkout(self)
        walkout._ems_portal_vote(self.delegate, 'yes')
        walkout._ems_portal_vote(self.subdelegate, 'no')
        end_phase(walkout)
        self.assertEqual(walkout.state, 'closed')
        self.assertTrue(self._line(self._session(walkout.walkout_date), self.delegate).active)

    def test_the_teacher_puts_back_who_came_and_can_undo_it(self):
        walkout = self._closed()
        line = self._line(self._session(walkout.walkout_date), self.delegate)
        line.with_user(self.teacher_user).write({'active': True})
        self.assertEqual((line.active, line.not_expected_reason), (True, False), "They came after all.")
        line.with_user(self.teacher_user).write({'active': False})
        self.assertEqual(line.not_expected_reason, 'walkout', "Removed again: the walkout still applies.")

    def test_removing_again_gets_back_any_reason_that_still_applies(self):
        """Not only the walkout: an expected withdrawal is recovered the same way."""
        self.offline.sudo()._ems_mark_withdrawal_expected()
        line = self._line(self._session(self.today + timedelta(days=7)), self.offline)
        self.assertEqual(line.not_expected_reason, 'withdrawal')
        line.write({'active': True})
        line.write({'active': False})
        self.assertEqual(line.not_expected_reason, 'withdrawal')
        other = self._line(line.attendance_session_id, self.delegate)
        other.write({'active': False})
        self.assertFalse(other.not_expected_reason, "Removed by hand with no reason: none.")

    # Validating or not

    def test_validating_creates_no_justification(self):
        walkout = self._closed()
        walkout.with_user(self.head_of_studies).action_validate()
        self.assertEqual(walkout.state, 'validated')
        self.assertFalse(self.env['ems.attendance_justification'].search([
            ('reason_id', '=', self.env.ref('ems.attendance_justification_reason_walkout').id),
            ('student_ids', 'in', self.delegate.ids)]))
        self.assertFalse(self._line(self._session(walkout.walkout_date), self.delegate).active)

    def test_not_validated_turns_the_classes_into_absences(self):
        for undo in (False, True):
            with self.subTest(undo=undo):
                walkout = self._closed()
                session = self._session(walkout.walkout_date, 8.0 + undo, 9.0 + undo)
                if undo:
                    walkout.with_user(self.head_of_studies).action_validate()
                reject_walkout(walkout, self.head_of_studies, 'ems.student_walkout_rejection_level')
                for student in (self.delegate, self.subdelegate, self.classmate):
                    line = self._line(session, student)
                    self.assertEqual((line.active, line.not_expected_reason, line.status_id),
                                     (True, False, self.miss), student.name)

    # Telling the family of an unratified minor

    def test_the_family_of_an_unratified_minor_is_told_for_information(self):
        walkout = self._closed()
        session = self._session(walkout.walkout_date)
        notice = self._notices(self._line(session, self.classmate))
        self.assertEqual(len(notice), 1, "Pending ratification: the family is told.")
        self.assertEqual(notice.not_expected_reason, 'walkout')
        self.assertIn(self.family.email, notice.send_to)
        self.assertFalse(self._notices(self._line(session, self.subdelegate)), "Ratified: nothing to tell.")
        self.assertFalse(self._notices(self._line(session, self.delegate)), "An adult: nothing to tell.")

    def test_a_refusal_is_told_too(self):
        walkout = self._closed(ratifies=False)
        self.assertTrue(self._notices(self._line(self._session(walkout.walkout_date), self.subdelegate)))

    def test_the_notice_says_it_is_only_informative(self):
        walkout = self._closed()
        notice = self._notices(self._line(self._session(walkout.walkout_date), self.classmate))
        for xmlid in ('ems.mail_attendance_issue_status_family', 'ems.mail_attendance_issue_status_student'):
            body = self.env.ref(xmlid)._render_field('body_html', notice.ids)[notice.id]
            self.assertIn('collective decision not to attend class', body, xmlid)
            self.assertIn('only for your information', body, xmlid)
            self.assertNotIn('right', body, xmlid)

    def test_putting_back_who_came_cancels_the_notice(self):
        walkout = self._closed()
        line = self._line(self._session(walkout.walkout_date), self.classmate)
        self.assertTrue(self._notices(line))
        line.with_user(self.teacher_user).write({'active': True})
        self.assertFalse(self._notices(line), "Not sent yet: withdrawn.")
        line.with_user(self.teacher_user).write({'active': False})
        self.assertEqual(len(self._notices(line)), 1, "Removed again: told again.")

    def test_a_ratification_marked_by_hand_later_withdraws_the_notice(self):
        """Issue #840's manual ratification is open until the Head of Studies validates: marked once the
        roll-calls of the day exist, the notice to the family no longer applies."""
        walkout = self._closed()
        line = self._line(self._session(walkout.walkout_date), self.classmate)
        self.assertTrue(self._notices(line))
        walkout_line = walkout.line_ids.filtered(lambda line: line.student_id == self.classmate)
        walkout_line.with_user(self.tutor).action_ratify_manually()
        self.assertFalse(self._notices(line), "Not sent yet: withdrawn.")
        self.assertNotIn('not ratified', line.roll_call_label)

    def test_who_no_longer_joins_after_an_extension_is_back_on_the_roll_call(self):
        """Issue #838: a closed call reopens for one phase more; whoever then withdraws is expected again
        when it closes."""
        walkout = self._closed()
        session = self._session(walkout.walkout_date)
        walkout.with_user(self.tutor).action_extend_joining()
        self.assertEqual(walkout.state, 'joining')
        walkout._ems_portal_join(self.delegate, False)
        end_phase(walkout)
        self.assertTrue(self._line(session, self.delegate).active)
        self.assertFalse(self._line(session, self.subdelegate).active)
