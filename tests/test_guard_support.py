from datetime import timedelta

from odoo.exceptions import AccessError, UserError

from .test_absence_coverage import AbsenceCoverageCase


class TestGuardSupport(AbsenceCoverageCase):
    """Sending a guard on duty to support a teacher who is in class (issue #725), from the guard's
    badge on the guard duty board's absences table."""

    def _options(self, user=None, guard=None, hour_from=8, hour_to=9):
        return self.Cover.with_user(user or self.department_chief).get_support_options(
            str(self.day), hour_from, hour_to, (guard or self.teacher_guard).id)

    def _support(self, user=None, guard=None, teacher=None, hour_from=8, hour_to=9, message='Group 3 is restless'):
        return self.Cover.with_user(user or self.department_chief).board_support(
            str(self.day), hour_from, hour_to, (guard or self.teacher_guard).id,
            (teacher or self.teacher_a).id, self.group_a.id, message)

    def _board_line(self, user=None, hour_from=8):
        data = self.env.company.current_course_id.with_user(user or self.department_chief).get_guard_duty_board_data(
            '0', 'morning', day=str(self.day))
        return next(line for line in data['lines'] if line['hour_from'] == hour_from)

    @staticmethod
    def _guard(line, guard):
        return next(badge for badge in line['guards'] if badge['id'] == guard.id)

    def test_the_department_chief_sends_a_guard_as_support_and_both_are_notified(self):
        self._morning()
        self.assertEqual([(option['teacher_id'], option['group_id'], option['time']) for option in self._options()['options']],
                         [(self.teacher_a.id, self.group_a.id, '08:00-09:00')])

        cover = self.Cover.browse(self._support())

        self.assertEqual((cover.cover_type, cover.guard_employee_id, cover.absent_employee_id), (
            'support', self.teacher_guard, self.teacher_a))
        self.assertEqual((cover.hour_from, cover.hour_to, cover.subject_id), (8, 9, self.subject))
        for teacher in (self.teacher_guard, self.teacher_a):
            messages = self._guard_messages(teacher)
            self.assertEqual(len(messages), 1, teacher.name)
            self.assertIn('Group 3 is restless', messages.body)
            self.assertIn(self.group_a.name, messages.subject)

    def test_a_guard_on_support_is_busy_shown_in_the_class_and_counted(self):
        self._morning()
        self._support()

        line = self._board_line()
        badge = self._guard(line, self.teacher_guard)
        self.assertIn(self.teacher_a.name, badge['busy'])
        self.assertTrue(badge['support_cover_id'])
        self.assertEqual(badge['cover_count'], 1)
        self.assertFalse(badge['available'])
        # Busy: nobody can send them to cover an absence then, and they cannot take one themselves.
        self.assertNotIn(self.teacher_guard.id, [candidate['id'] for candidate in line['guard_candidates']])
        cell = next(cell for cell in line['cells'] if cell['group_id'] == self.group_a.id)
        self.assertEqual(cell['supports'], [self.teacher_guard.name])
        # No second support for the same guard then; the dialog shows the current one instead.
        options = self._options()
        self.assertEqual(options['options'], [])
        self.assertTrue(options['current'][0]['can_release'])
        with self.assertRaises(UserError):
            self._support()

    def test_only_whoever_manages_the_teachers_absences_sends_a_support(self):
        self._morning()

        self.assertTrue(self._options(user=self.head_of_studies)['options'])
        self.assertTrue(self._guard(self._board_line(), self.teacher_guard)['can_support'])
        for outsider in (self.other_department_chief, self.other_head_of_studies, self.guard_user):
            with self.subTest(user=outsider.name):
                self.assertEqual(self._options(user=outsider)['options'], [])
                self.assertFalse(self._guard(self._board_line(user=outsider), self.teacher_guard)['can_support'])
                with self.assertRaises(AccessError):
                    self._support(user=outsider)

    def test_also_managed_by_decides_who_sends_and_which_guard(self):
        """The same rules as sending a guard to cover (issues #622, #721): a teacher also managed by
        another area's department can be supported by that area's chiefs, who only send their own
        area's guards."""
        self._two_areas()
        self._morning()
        self.teacher_guard.department_id = self.department  # VET; teacher_guard_2 is ESO

        self.assertEqual(self._options(user=self.eso_chief)['options'], [])
        with self.assertRaises(AccessError):
            self._support(user=self.eso_chief, guard=self.teacher_guard_2)
        with self.assertRaises(UserError):
            self._support(guard=self.teacher_guard_2)

        self.teacher_a.managing_department_ids = self.eso_department
        self.assertEqual([option['teacher_id'] for option in self._options(user=self.eso_chief, guard=self.teacher_guard_2)['options']],
                         [self.teacher_a.id])
        self.assertTrue(self._support(user=self.eso_chief, guard=self.teacher_guard_2))
        with self.assertRaises(UserError):
            self._support(user=self.eso_chief, hour_from=9, hour_to=10)

    def test_only_a_guard_who_cannot_cover_looks_disabled(self):
        """A badge looks disabled only when the guard cannot cover anything then (away, not checked
        in, busy): a free guard is available to everybody, though only whoever manages a class may
        send them as support, and only the user themselves takes a class from their own badge."""
        self._morning()

        line = self._board_line(user=self.guard_user)
        guards = self.teacher_guard | self.teacher_guard_2
        self.assertEqual({badge['id']: (badge['available'], badge['can_support'], badge['is_me_free'])
                          for badge in line['guards'] if badge['id'] in guards.ids},
                         {self.teacher_guard.id: (True, False, True), self.teacher_guard_2.id: (True, False, False)})
        self._absence(self.teacher_guard, self.day)
        badge = self._guard(self._board_line(user=self.guard_user), self.teacher_guard)
        self.assertEqual((badge['available'], badge['is_me_free']), (False, False))
        # Whoever manages the classes may send the free one as support.
        line = self._board_line()
        self.assertTrue(self._guard(line, self.teacher_guard_2)['can_support'])
        self.assertFalse(self._guard(line, self.teacher_guard_2)['is_me_free'])

    def test_only_a_class_whose_teacher_is_in_can_be_supported(self):
        self._morning()
        self._absence(self.teacher_a, self.day, 8, 9)

        self.assertEqual(self._options()['options'], [])
        with self.assertRaises(UserError):
            self._support()

    def test_only_a_free_regular_guard_can_be_sent(self):
        self._morning()
        self._guards(self.teacher_guard_wc, non_teaching=self.non_teaching_guard_wc)
        self._absence(self.teacher_guard_2, self.day)

        for guard in (self.teacher_guard_wc, self.teacher_guard_2, self.teacher_b):
            with self.subTest(guard=guard.name), self.assertRaises(UserError):
                self._support(guard=guard)

    def test_a_past_day_cannot_be_supported(self):
        self._morning()
        self.day = self.day - timedelta(days=14)

        with self.assertRaises(UserError):
            self._support()

    def test_removing_a_support_tells_both_and_frees_the_guard(self):
        self._morning()
        cover = self.Cover.browse(self._support())

        self.Cover.with_user(self.department_chief).board_release(cover.id)

        self.assertEqual(cover.state, 'released')
        self.assertEqual(len(self._guard_messages(self.teacher_guard)), 2)
        self.assertEqual(len(self._guard_messages(self.teacher_a)), 2)
        line = self._board_line()
        self.assertFalse(self._guard(line, self.teacher_guard)['busy'])
        self.assertIn(self.teacher_guard.id, [candidate['id'] for candidate in line['guard_candidates']])

    def test_a_support_resolves_no_absence(self):
        """The supported teacher falls ill afterwards: the class is still to cover, and the support
        is neither its guard nor something to release."""
        self._morning()
        self._support()
        self._absence(self.teacher_a, self.day, 8, 9)

        row = self._row()
        self.assertFalse(row['covers'])
        self.assertFalse(row['arrangement'])
        self.assertFalse([action for action in self._actions() if action['type'] == 'obsolete_cover'])
        # The other guard can still be sent to cover it.
        self._assign(guard=self.teacher_guard_2)
