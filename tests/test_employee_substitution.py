from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import tagged

from .common import create_role_employee, create_role_user, next_student_id
from .test_guard_duty_board import GuardDutyBoardCase


@tagged('post_install', '-at_install')
class TestEmployeeSubstitution(GuardDutyBoardCase):
    """Issue #748: a teacher substituting another one (hr.employee.substitute_of_id) - the copied
    schedule, the guard duty board, and acting as the replaced teacher."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.titular_user = create_role_user(cls, 'teacher', 'test_titular_substitution', name='TSUB Titular')
        cls.titular = create_role_employee(cls, cls.titular_user)
        cls.substitute_user = create_role_user(cls, 'teacher', 'test_substitute_substitution', name='TSUB Substitute')
        cls.substitute = create_role_employee(cls, cls.substitute_user)
        cls.group_a.tutor_id = cls.titular
        cls.student = cls.env['res.partner'].create({
            'name': 'TSUB Student', 'contact_type': 'student', 'student_id': next_student_id(),
            'main_group_id': cls.group_a.id,
        })

    def _titular_week(self):
        """The titular's Monday: a class of group_a 9-10 and a WC guard 10-11."""
        calendar = self._new_calendar(self.titular, 'TSUB Titular Calendar')
        calendar.apply_schedule_changes([
            {'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
             'subject_id': self.subject.id, 'group_ids': [self.group_a.id], 'name': 'TGDBA: TGDB'},
            {'dayofweek': '0', 'hour_from': 10, 'hour_to': 11, 'day_period': 'morning',
             'non_teaching': self.non_teaching_guard_wc.id, 'name': 'Guard (WC)'},
        ])
        return calendar

    def _substitute(self):
        self._titular_week()
        self.substitute.substitute_of_id = self.titular

    @staticmethod
    def _week(calendar):
        return sorted((block.dayofweek, block.hour_from, block.hour_to, block.subject_id, block.group_ids,
                       block.non_teaching) for block in calendar.attendance_ids)

    # The schedule

    def test_setting_it_copies_the_schedule(self):
        self._substitute()

        self.assertEqual(self._week(self.substitute.resource_calendar_id), self._week(self.titular.resource_calendar_id))
        self.assertIn(self.group_a, self.substitute.teaching_ids.group_id)
        self.assertEqual(self.substitute.substitution_label, 'Substitute')
        self.assertEqual(self.titular.substitution_label, 'Substituted')

    def test_clearing_it_by_hand_only_corrects_it(self):
        """Chosen the wrong titular, say: the substitution is undone, the schedule stays as it is."""
        self._substitute()
        copied_week = self._week(self.substitute.resource_calendar_id)

        self.substitute.substitute_of_id = False

        self.assertEqual(self._week(self.substitute.resource_calendar_id), copied_week)
        self.assertFalse(self.titular.substitution_label)
        self.assertEqual(self.titular.acting_user_ids, self.titular_user)

    def test_a_teacher_cannot_substitute_themselves_even_through_a_chain(self):
        with self.assertRaises(ValidationError):
            self.titular.substitute_of_id = self.titular
        self.substitute.substitute_of_id = self.titular
        with self.assertRaises(ValidationError):
            self.titular.substitute_of_id = self.substitute

    # The guard duty board

    def test_the_titular_leaves_the_board_and_the_substitute_takes_their_place(self):
        self._substitute()
        monday = self._monday()
        self._absence(self.titular, monday)

        blocks = self.env['ems.course']._get_guard_duty_board_attendance_ids([('dayofweek', '=', '0')])
        self.assertNotIn(self.titular, blocks.employee_id)
        self.assertIn(self.substitute, blocks.employee_id)
        for hour_from, hour_to in ((9, 10), (10, 11)):
            line = self._teaching_line(monday, hour_from, hour_to)
            self.assertNotIn(self.titular, [row['teacher'] for row in line['absences']])

    def test_without_a_substitute_the_absent_wc_guard_still_needs_covering(self):
        """The control of the test above: the same week, nobody substituting."""
        self._titular_week()
        monday = self._monday()
        self._absence(self.titular, monday)

        rows = self._teaching_line(monday, 10, 11)['absences']

        self.assertIn(self.titular, [row['teacher'] for row in rows])

    # Acting as the titular

    def test_the_substitute_acts_as_the_titular_through_the_chain(self):
        self._substitute()
        second_user = create_role_user(self, 'teacher', 'test_second_substitution', name='TSUB Second')
        second = create_role_employee(self, second_user, substitute_of_id=self.substitute.id)
        Employee = self.env['hr.employee']

        self.assertEqual(self.titular.acting_user_ids, self.titular_user | self.substitute_user | second_user)
        self.assertIn(second_user, self.titular.tutor_scope_user_ids)
        self.assertEqual(Employee.search([('acting_user_ids', '=', second_user.id)]), self.titular | self.substitute | second)
        self.assertIn(self.titular, Employee.search([('tutor_scope_user_ids', '=', second_user.id)]))
        self.assertEqual(Employee.search([('acting_user_ids', '=', self.titular_user.id)]), self.titular)
        self.assertEqual(self.titular._ems_acting_teacher(), second)
        self.assertEqual(self.group_a.tutor_id._ems_acting_teacher().user_id, second_user)

    def test_the_substitute_reads_the_titulars_tutoring_and_grades_while_it_lasts(self):
        issue = self.env['ems.attendance_issue_tutor'].create({'tutor_id': self.titular.id, 'issue_date': self._monday()})
        grade_session = self.env['ems.grade_session'].create({
            'group_id': self.group_c.id, 'subject_id': self.subject2.id, 'teacher_id': self.titular.id})
        for record in (issue, grade_session):
            with self.assertRaises(AccessError):
                record.with_user(self.substitute_user).check_access('read')

        self.substitute.substitute_of_id = self.titular
        for record in (issue, grade_session):
            record.with_user(self.substitute_user).check_access('read')
        self.assertTrue(self.env['ems.base'].with_user(self.substitute_user).user_acts_as_tutor(self.titular))

        self.substitute.substitute_of_id = False
        for record in (issue, grade_session):
            with self.assertRaises(AccessError):
                record.with_user(self.substitute_user).check_access('read')

    def test_archiving_the_substitute_ends_the_substitution(self):
        """The usual end: the titular is back and the substitute leaves the centre. Their user may
        still be active for a while (the Google account is suspended separately)."""
        self._substitute()
        issue = self.env['ems.attendance_issue_tutor'].create({'tutor_id': self.titular.id, 'issue_date': self._monday()})
        calendar = self.substitute.resource_calendar_id

        self.substitute.action_archive()

        self.assertFalse(calendar.active)
        blocks = self.env['ems.course']._get_guard_duty_board_attendance_ids([('dayofweek', '=', '0')])
        self.assertIn(self.titular, blocks.employee_id)
        self.assertNotIn(self.substitute, blocks.employee_id)
        self.assertEqual(self.titular.acting_user_ids, self.titular_user)
        self.assertEqual(self.titular._ems_acting_teacher(), self.titular)
        self.assertFalse(self.titular.substitution_label)
        # Not even from a screen that lists archived records (active_test=False in the context).
        unfiltered = self.titular.with_context(active_test=False)
        unfiltered.invalidate_recordset()
        self.assertEqual(unfiltered.acting_user_ids, self.titular_user)
        self.assertEqual(unfiltered._ems_acting_teacher(), self.titular)
        self.assertFalse(unfiltered.substitution_label)
        self.assertIn(self.titular, self.env['ems.course'].with_context(active_test=False)
                      ._get_guard_duty_board_attendance_ids([('dayofweek', '=', '0')]).employee_id)
        self.assertNotIn(self.titular, self.env['hr.employee'].search([('acting_user_ids', '=', self.substitute_user.id)]))
        with self.assertRaises(AccessError):
            issue.with_user(self.substitute_user).check_access('read')

    def test_unarchiving_the_substitute_does_not_take_up_the_old_substitution(self):
        self._substitute()
        self.substitute.action_archive()

        self.substitute.action_unarchive()

        self.assertFalse(self.substitute.substitute_of_id)
        self.assertTrue(self.substitute.resource_calendar_id.active)
        self.assertFalse(self.substitute.resource_calendar_id.attendance_ids.filtered(
            lambda block: block.dayofweek in ('0', '1', '2', '3', '4')))
        blocks = self.env['ems.course']._get_guard_duty_board_attendance_ids([('dayofweek', '=', '0')])
        self.assertIn(self.titular, blocks.employee_id)

    def test_the_titulars_own_absences_stay_private(self):
        self.substitute.substitute_of_id = self.titular
        leave = self._absence(self.titular, self._monday(), approve=False)

        with self.assertRaises(AccessError):
            leave.with_user(self.substitute_user).check_access('read')

    def test_a_substitute_does_not_take_the_titulars_chief_rung(self):
        """A role is personal: substituting a Department Chief does not give their department."""
        chief_user = create_role_user(self, 'department_chief', 'test_chief_substitution', name='TSUB Chief')
        chief = create_role_employee(self, chief_user)
        self.titular.parent_id = chief
        self.substitute.substitute_of_id = chief

        self.assertNotIn(self.titular, self.env['hr.employee'].search([('tutor_scope_user_ids', '=', self.substitute_user.id)]))
        self.assertNotIn(self.substitute_user, self.titular.tutor_scope_user_ids)
