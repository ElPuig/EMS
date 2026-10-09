from datetime import timedelta
from unittest.mock import patch

from odoo.addons.ems.models.shared.datetime_utils import EmsDatetimeUtils
from odoo.exceptions import AccessError, UserError, ValidationError

from .common import create_head_of_studies_branch, create_role_employee, create_role_user, next_student_id
from .test_guard_duty_board import GuardDutyBoardCase


class TestAbsenceCoverage(GuardDutyBoardCase):
    """Managing absences from the guard duty board's absences table (issues #539, #571, #581):
    sending a guard to a class, proposing the timetable change an absence allows, and spotting
    what an absence that changed afterwards has made unnecessary or wrong."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # teacher_a hangs below a Department Chief, below a Head of Studies (see
        # create_head_of_studies_branch for the people deliberately left outside that branch).
        create_head_of_studies_branch(cls, 'TABC', cls.teacher_a)
        # A real department headed by that Department Chief, as in production: it is what limits
        # the chief's notices to the groups their department teaches.
        chief, head = cls.teacher_a.parent_id, cls.teacher_a.parent_id.parent_id
        cls.department = cls.env['hr.department'].create({'name': 'TABC Department', 'manager_id': chief.id})
        (cls.teacher_a | cls.teacher_b).department_id = cls.department
        (cls.teacher_a | cls.teacher_b).parent_id = chief
        chief.parent_id = head
        cls.teacher_a_user = create_role_user(cls, 'teacher', 'test_teacher_a_tabc', name='TABC Teacher A')
        cls.teacher_a.user_id = cls.teacher_a_user
        cls.guard_user = create_role_user(cls, 'teacher', 'test_guard_tabc', name='TABC Guard')
        cls.teacher_guard.user_id = cls.guard_user
        cls.teacher_guard_2 = create_role_employee(cls, create_role_user(cls, 'teacher', 'test_guard_2_tabc'),
                                                   name='TABC Second Guard')
        cls.teacher_guard_wc = cls.env['hr.employee'].create({'name': 'TABC WC Guard', 'employee_type': 'teacher'})
        cls.Cover = cls.env['ems.absence_cover']
        cls.Notice = cls.env['ems.notice']

    def setUp(self):
        super().setUp()
        self.day = self._next_monday()

    def _next_monday(self):
        """Absences are managed from today on (a past day is over), so these fixtures need a real
        upcoming Monday rather than _monday()'s one inside the course."""
        day = self.env['ems.datetime_utils'].get_local_today() + timedelta(days=1)
        while day.weekday() != 0:
            day += timedelta(days=1)
        return day

    def _guards(self, *guards, periods=((8, 9), (9, 10), (10, 11)), non_teaching=None):
        for guard in guards:
            calendar = self._new_calendar(guard, f'TABC Guard Calendar {guard.name}')
            calendar.apply_schedule_changes([{
                'dayofweek': '0', 'hour_from': hour_from, 'hour_to': hour_to, 'day_period': 'morning',
                'non_teaching': (non_teaching or self.non_teaching_guard).id, 'name': 'Guard',
            } for hour_from, hour_to in periods])

    def _morning(self):
        """group_a's Monday: teacher_a 8-11, teacher_b 11-12, guards on duty 8-11."""
        self._schedule_class(self.teacher_a, self.group_a, 'TABC Calendar A', periods=((8, 9), (9, 10), (10, 11)))
        self._schedule_class(self.teacher_b, self.group_a, 'TABC Calendar B', periods=((11, 12),))
        self._guards(self.teacher_guard, self.teacher_guard_2)

    def _assign(self, guard=None, hour_from=8, hour_to=9, user=None, message='Exercises on page 12'):
        return self.Cover.with_user(user or self.department_chief).board_assign(
            str(self.day), hour_from, hour_to, self.teacher_a.id, self.group_a.id,
            (guard or self.teacher_guard).id, message)

    def _row(self, hour_from=8, hour_to=9, teacher=None):
        return self._absence_row(self._teaching_line(self.day, hour_from, hour_to), teacher or self.teacher_a)

    def _states(self):
        return self.env['ems.course']._get_absence_change_states(self.day, self.group_a)[self.group_a.id]

    def _actions(self):
        return self.env.company.current_course_id.get_guard_duty_board_lines('0', 'morning', day=self.day)['actions']

    def _guard_messages(self, guard):
        partner = guard.user_id.partner_id or guard.work_contact_id
        return self.env['mail.message'].search([
            ('model', '=', 'ems.absence_cover'), ('partner_ids', 'in', partner.ids)])

    # Guard assignment (issue #571)

    def test_the_department_chief_sends_a_guard_who_is_notified(self):
        self._morning()
        self._absence(self.teacher_a, self.day)

        cover = self.Cover.browse(self._assign())

        self.assertEqual(cover.guard_employee_id, self.teacher_guard)
        self.assertEqual((cover.hour_from, cover.hour_to), (8, 9))
        self.assertEqual(cover.subject_id, self.subject)
        messages = self._guard_messages(self.teacher_guard)
        self.assertEqual(len(messages), 1)
        self.assertIn('Exercises on page 12', messages.body)
        self.assertIn(self.group_a.name, messages.subject)

    def test_the_row_shows_its_guard_in_the_guard_colour(self):
        self._morning()
        self._absence(self.teacher_a, self.day)
        self._assign()

        line = self._teaching_line(self.day, 8, 9)
        row = self._absence_row(line, self.teacher_a)

        self.assertEqual(row['cover'].guard_employee_id, self.teacher_guard)
        self.assertEqual(line['guard_colors'], {self.teacher_guard.id: 0})

    def test_the_pdf_prints_the_guard_colour_and_strike(self):
        self._morning()
        self._absence(self.teacher_a, self.day)
        self._assign()

        html, _content_type = self.env['ir.actions.report'].with_context(
            guard_duty_weekday='0', guard_duty_date=str(self.day), guard_duty_view='table').\
            _render_qweb_html('ems.report_guard_duty_board', [self.env.company.current_course_id.id])

        self.assertIn(b'gdb-absence-row gdb-absence-covered gdb-cover-0', html)
        self.assertIn(b'gdb-guard-badge gdb-cover-0', html)

    def test_two_guards_covering_at_once_get_different_colours(self):
        self._morning()
        self._schedule_class(self.teacher_b, self.group_b, 'TABC Calendar B (group B)', periods=((8, 9), (11, 12)))
        self._absence(self.teacher_a, self.day)
        self._absence(self.teacher_b, self.day)
        self._assign()
        self.Cover.with_user(self.department_chief).board_assign(
            str(self.day), 8, 9, self.teacher_b.id, self.group_b.id, self.teacher_guard_2.id)

        colors = self._teaching_line(self.day, 8, 9)['guard_colors']

        self.assertEqual(set(colors), {self.teacher_guard.id, self.teacher_guard_2.id})
        self.assertNotEqual(colors[self.teacher_guard.id], colors[self.teacher_guard_2.id])

    def test_assigning_someone_else_releases_and_tells_the_previous_guard(self):
        self._morning()
        self._absence(self.teacher_a, self.day)
        first = self.Cover.browse(self._assign())

        second = self.Cover.browse(self._assign(guard=self.teacher_guard_2))

        self.assertEqual(first.state, 'released')
        self.assertEqual(second.guard_employee_id, self.teacher_guard_2)
        self.assertEqual(len(self._guard_messages(self.teacher_guard)), 2)
        self.assertEqual(len(self._guard_messages(self.teacher_guard_2)), 1)

    def test_assigning_the_same_guard_again_updates_the_message(self):
        self._morning()
        self._absence(self.teacher_a, self.day)
        first = self._assign()

        second = self._assign(message='Bring the books')

        self.assertEqual(first, second)
        self.assertEqual(self.Cover.browse(first).message, 'Bring the books')
        self.assertEqual(len(self._guard_messages(self.teacher_guard)), 2)

    def test_releasing_tells_the_guard(self):
        self._morning()
        self._absence(self.teacher_a, self.day)
        cover = self.Cover.browse(self._assign())

        self.Cover.with_user(self.department_chief).board_release(cover.id)

        self.assertEqual(cover.state, 'released')
        self.assertFalse(self._row()['cover'])
        self.assertEqual(len(self._guard_messages(self.teacher_guard)), 2)

    def test_only_the_absent_teachers_chain_of_command_can_assign(self):
        self._morning()
        self._absence(self.teacher_a, self.day)

        self._assign(user=self.head_of_studies)
        for outsider in (self.other_department_chief, self.other_head_of_studies, self.teacher_a_user, self.guard_user):
            with self.subTest(user=outsider.name), self.assertRaises(AccessError):
                self._assign(user=outsider)

    def test_the_administrator_manages_any_absence(self):
        """Above Direction, although not a teacher and so nowhere in the hierarchy."""
        self._morning()
        self._absence(self.teacher_a, self.day)

        self.assertTrue(self._assign(user=self.env.ref('base.user_admin')))

    def test_only_managers_receive_the_pending_actions(self):
        self._morning()
        self._absence(self.teacher_a, self.day, hour_from=8, hour_to=10)
        course = self.env.company.current_course_id

        def actions(user):
            data = course.with_user(user).get_guard_duty_board_data('0', 'morning', day=str(self.day))
            return [action for action in data['actions'] if action['group_id'] == self.group_a.id]

        managed = actions(self.department_chief)
        self.assertEqual([option['hour'] for option in managed[0]['options']], [9, 10])
        self.assertEqual(managed[0]['default'], 1, "the largest change is proposed by default")
        self.assertEqual(actions(self.guard_user), [])

    def test_the_row_says_who_can_manage_it(self):
        self._morning()
        self._absence(self.teacher_a, self.day)
        course = self.env.company.current_course_id

        def can_manage(user):
            data = course.with_user(user).get_guard_duty_board_data('0', 'morning', day=str(self.day))
            line = next(line for line in data['lines'] if line['time_label'] == '08:00-09:00')
            return next(row for row in line['absences'] if row['teacher_id'] == self.teacher_a.id)['can_manage']

        self.assertTrue(can_manage(self.department_chief))
        self.assertFalse(can_manage(self.other_department_chief))
        self.assertFalse(can_manage(self.guard_user))

    def test_only_a_guard_on_duty_can_be_sent(self):
        self._morning()
        self._guards(self.teacher_guard_wc, non_teaching=self.non_teaching_guard_wc)
        self._absence(self.teacher_a, self.day)

        for guard in (self.teacher_guard_wc, self.teacher_b):
            with self.subTest(guard=guard.name), self.assertRaises(UserError):
                self._assign(guard=guard)
        line = self.env['ems.course'].get_guard_duty_board_data('0', 'morning', day=str(self.day))['lines'][0]
        self.assertNotIn(self.teacher_guard_wc.id, [candidate['id'] for candidate in line['guard_candidates']])

    def test_the_board_counts_the_classes_each_guard_has_covered_this_course(self):
        """Issue #600: every guard on the board, and every candidate of the guard dialog, carries
        how many classes they have been sent to cover this course - assigned covers only, a
        planned one for a coming day included, nothing from another course."""
        self._morning()
        self._absence(self.teacher_a, self.day)
        self._assign()
        start = self.env.company.current_course_id.date_range()[0]

        def cover(guard, day, state='assigned'):
            self.Cover.create({
                'date': day, 'hour_from': 8, 'hour_to': 9, 'absent_employee_id': self.teacher_b.id,
                'group_id': self.group_a.id, 'guard_employee_id': guard.id, 'state': state})

        cover(self.teacher_guard, start)
        cover(self.teacher_guard, start - timedelta(days=1))
        cover(self.teacher_guard_2, start, state='released')

        # Any teacher reads the board, so any teacher reads the counts too.
        line = self.env['ems.course'].with_user(self.guard_user).get_guard_duty_board_data(
            '0', 'morning', day=str(self.day))['lines'][0]
        expected = {self.teacher_guard.id: 2, self.teacher_guard_2.id: 0}
        for key in ('guards', 'guard_candidates'):
            counts = {guard['id']: guard['cover_count'] for guard in line[key] if guard['id'] in expected}
            self.assertEqual(counts, expected, key)

    def test_an_absent_guard_cannot_be_sent(self):
        self._morning()
        self._absence(self.teacher_a, self.day)
        self._absence(self.teacher_guard, self.day)

        with self.assertRaises(UserError):
            self._assign()

    def test_a_past_day_cannot_be_managed(self):
        self._morning()
        self.day = self.day - timedelta(days=14)
        self._absence(self.teacher_a, self.day)

        with self.assertRaises(UserError):
            self._assign()

    def test_a_class_can_only_have_one_guard(self):
        self._morning()
        self._absence(self.teacher_a, self.day)
        cover = self.Cover.browse(self._assign())

        with self.assertRaises(ValidationError):
            cover.copy()

    def test_an_assignment_made_on_an_expected_absence_survives_the_real_request(self):
        """The Head of Studies' expected absence and the teacher's own request are the same
        absence: what was already organised stays, and only what the request adds comes up new."""
        self._morning()
        expected = self.env['ems.absence_pending'].create({
            'employee_id': self.teacher_a.id,
            **dict(zip(('date_from', 'date_to'), self.env['ems.absence_pending']._utc_bounds(self.day, 8, 10))),
        })
        self._assign()

        self._absence(self.teacher_a, self.day)

        self.assertEqual(expected.state, 'linked')
        self.assertEqual(self._row(8, 9)['cover'].guard_employee_id, self.teacher_guard)
        self.assertFalse(self._row(10, 11)['cover'], "the hour the request adds is new, to be decided")
        self.assertNotIn('obsolete_cover', [action['type'] for action in self._actions()])

    def test_a_guard_no_longer_needed_is_offered_for_release(self):
        self._morning()
        leave = self._absence(self.teacher_a, self.day, approve=False)
        cover = self.Cover.browse(self._assign())

        leave.action_refuse()

        action = next(action for action in self._actions() if action['type'] == 'obsolete_cover')
        self.assertEqual(action['cover'], cover)
        self.assertTrue(action['can_manage'])
        self.assertEqual(cover.state, 'assigned', "nothing is released without the planner's say-so")

    # Covering a guard duty that is not regular (issue #606)

    def _wc_morning(self):
        """_morning() plus a WC guard on duty 8-11 under teacher_a's own chain of command, and
        away all day: their duty is what needs covering."""
        self._morning()
        self.teacher_guard_wc.parent_id = self.teacher_a.parent_id
        self._guards(self.teacher_guard_wc, non_teaching=self.non_teaching_guard_wc)
        self._absence(self.teacher_guard_wc, self.day)

    def _duty_row(self, hour_from=8, hour_to=9):
        return self._absence_row(self._teaching_line(self.day, hour_from, hour_to), self.teacher_guard_wc)

    def _assign_duty(self, guard=None, user=None, message='Stay by the toilets'):
        return self.Cover.with_user(user or self.department_chief).board_assign(
            str(self.day), 8, 9, self.teacher_guard_wc.id, False, (guard or self.teacher_guard).id, message,
            duty_id=self.non_teaching_guard_wc.id)

    def test_only_the_regular_guard_type_is_seeded_as_regular(self):
        self.assertTrue(self.non_teaching_guard.is_regular_guard)
        self.assertFalse(self.non_teaching_guard_wc.is_regular_guard)
        self.assertFalse(self.env.ref('ems.non_teaching_gb').is_regular_guard)

    def test_an_absent_wc_guard_is_a_row_to_cover(self):
        self._wc_morning()

        row = self._duty_row()

        self.assertEqual(row['duty'], self.non_teaching_guard_wc)
        self.assertFalse(row['group'])
        self.assertEqual(row['label'], self.non_teaching_guard_wc.name)
        payload = next(row for row in self._board_row_data(self.department_chief)['absences']
                       if row['teacher_id'] == self.teacher_guard_wc.id)
        self.assertEqual((payload['duty_id'], payload['group_id']), (self.non_teaching_guard_wc.id, False))
        self.assertEqual(payload['group'], self.non_teaching_guard_wc.name)
        self.assertTrue(payload['can_manage'])

    def test_an_absent_regular_guard_is_still_not_a_row_to_cover(self):
        self._morning()
        self._absence(self.teacher_guard, self.day)

        self.assertFalse([row for row in self._teaching_line(self.day, 8, 9)['absences']
                          if row['teacher'] == self.teacher_guard])

    def test_the_planner_sends_a_regular_guard_to_the_wc_duty_who_is_notified(self):
        self._wc_morning()

        cover = self.Cover.browse(self._assign_duty())

        self.assertEqual((cover.duty_id, cover.group_id), (self.non_teaching_guard_wc, self.env['ems.group']))
        self.assertEqual(cover.display_name, self.non_teaching_guard_wc.name)
        self.assertFalse(cover.subject_id or cover.space_id)
        self.assertEqual(self._duty_row()['cover'], cover)
        self.assertEqual(self._teaching_line(self.day, 8, 9)['guard_colors'], {self.teacher_guard.id: 0})
        messages = self._guard_messages(self.teacher_guard)
        self.assertEqual(len(messages), 1)
        self.assertIn(self.non_teaching_guard_wc.name, messages.subject)
        self.assertIn('guard duty', messages.body)
        self.assertIn('Stay by the toilets', messages.body)
        with self.assertRaises(ValidationError):
            cover.copy()

    def test_only_a_regular_guard_covers(self):
        """Neither a WC nor a break guard is ever sent anywhere: they are needed at their post."""
        self._morning()
        self._guards(self.teacher_guard_wc, non_teaching=self.non_teaching_guard_wc)
        break_guard = self.env['hr.employee'].create({'name': 'TABC Break Guard', 'employee_type': 'teacher'})
        self._guards(break_guard, non_teaching=self.env.ref('ems.non_teaching_gb'))
        self._absence(self.teacher_a, self.day)

        for guard in (self.teacher_guard_wc, break_guard):
            with self.subTest(guard=guard.name), self.assertRaises(UserError):
                self._assign(guard=guard)
        candidates = [candidate['id'] for candidate in self._board_row_data(self.department_chief)['guard_candidates']]
        self.assertLessEqual({self.teacher_guard.id, self.teacher_guard_2.id}, set(candidates))
        self.assertFalse({self.teacher_guard_wc.id, break_guard.id} & set(candidates))

    def test_a_present_wc_guard_needs_no_cover(self):
        self._morning()
        self._guards(self.teacher_guard_wc, non_teaching=self.non_teaching_guard_wc)
        self._absence(self.teacher_a, self.day)

        with self.assertRaises(UserError):
            self._assign_duty(user=self.env.ref('base.user_admin'))

    def test_a_guard_takes_the_wc_duty_themselves(self):
        self._wc_morning()
        row = next(row for row in self._board_row_data(self.guard_user)['absences']
                   if row['teacher_id'] == self.teacher_guard_wc.id)
        self.assertTrue(row['can_self_assign'])

        cover = self.Cover.browse(self.Cover.with_user(self.guard_user).board_self_assign(
            str(self.day), 8, 9, self.teacher_guard_wc.id, False, duty_id=self.non_teaching_guard_wc.id))

        self.assertTrue(cover.is_self_assigned)
        self.assertEqual(cover.duty_id, self.non_teaching_guard_wc)

    def test_a_wc_cover_no_longer_needed_is_offered_for_release(self):
        self._morning()
        self.teacher_guard_wc.parent_id = self.teacher_a.parent_id
        self._guards(self.teacher_guard_wc, non_teaching=self.non_teaching_guard_wc)
        leave = self._absence(self.teacher_guard_wc, self.day, approve=False)
        cover = self.Cover.browse(self._assign_duty())

        leave.action_refuse()

        action = next(action for action in self._actions() if action['type'] == 'obsolete_cover')
        self.assertEqual(action['cover'], cover)
        data = self.env['ems.course'].with_user(self.department_chief).get_guard_duty_board_data(
            '0', 'morning', day=str(self.day))
        label = next(action['label'] for action in data['actions'] if action['type'] == 'obsolete_cover')
        self.assertIn(self.non_teaching_guard_wc.name, label)

    def test_the_pdf_prints_a_covered_guard_duty(self):
        self._wc_morning()
        self._assign_duty()

        html, _content_type = self.env['ir.actions.report'].with_context(
            guard_duty_weekday='0', guard_duty_date=str(self.day), guard_duty_view='table').\
            _render_qweb_html('ems.report_guard_duty_board', [self.env.company.current_course_id.id])

        self.assertIn(self.non_teaching_guard_wc.name.encode(), html)
        self.assertIn(b'gdb-absence-row gdb-absence-covered gdb-cover-0', html)

    def _board_row_data(self, user, hour_from=8):
        data = self.env.company.current_course_id.with_user(user).get_guard_duty_board_data(
            '0', 'morning', day=str(self.day))
        return next(line for line in data['lines'] if line['hour_from'] == hour_from)

    # Self-assignment (issue #601)

    def _self_assign(self, user=None, hour_from=8, hour_to=9):
        return self.Cover.with_user(user or self.guard_user).board_self_assign(
            str(self.day), hour_from, hour_to, self.teacher_a.id, self.group_a.id)

    def _board_row(self, user, hour_from=8):
        data = self.env.company.current_course_id.with_user(user).get_guard_duty_board_data(
            '0', 'morning', day=str(self.day))
        line = next(line for line in data['lines'] if line['hour_from'] == hour_from)
        return next(row for row in line['absences'] if row['teacher_id'] == self.teacher_a.id)

    def test_a_guard_takes_a_free_class_without_anybody_being_notified(self):
        self._morning()
        self._absence(self.teacher_a, self.day)
        cover = self.Cover.browse(self._self_assign())

        self.assertEqual(cover.guard_employee_id, self.teacher_guard)
        self.assertEqual(cover.assigned_by_id, self.guard_user)
        self.assertTrue(cover.is_self_assigned)
        self.assertEqual(self._row()['cover'], cover)
        messages = self.env['mail.message'].search([('model', '=', 'ems.absence_cover'), ('res_id', '=', cover.id)])
        self.assertFalse(messages.partner_ids, "nobody is notified: the board already shows it")

    def test_the_board_offers_self_assignment_only_to_a_guard_on_duty(self):
        self._morning()
        self._absence(self.teacher_a, self.day)

        self.assertTrue(self._board_row(self.guard_user)['can_self_assign'])
        self.assertFalse(self._board_row(self.guard_user, hour_from=8)['can_self_release'])
        self.assertFalse(self._board_row(self.teacher_a_user)['can_self_assign'], "the absent teacher is not on guard")

    def test_only_a_guard_on_duty_can_take_a_class(self):
        self._morning()
        self._absence(self.teacher_a, self.day)

        with self.assertRaises(UserError):
            self._self_assign(user=self.teacher_a_user)
        with self.assertRaises(UserError):
            self._self_assign(hour_from=11, hour_to=12)

    def test_a_guard_cannot_take_a_class_already_covered(self):
        self._morning()
        self._absence(self.teacher_a, self.day)
        self._assign(guard=self.teacher_guard_2)

        self.assertFalse(self._board_row(self.guard_user)['can_self_assign'])
        with self.assertRaises(UserError):
            self._self_assign()

    def test_a_guard_cannot_take_a_class_on_a_past_day(self):
        self._morning()
        self.day = self.env['ems.datetime_utils'].get_local_today() - timedelta(days=7)
        while self.day.weekday() != 0:
            self.day -= timedelta(days=1)
        self._absence(self.teacher_a, self.day)

        with self.assertRaises(UserError):
            self._self_assign()

    def test_a_guard_leaves_a_class_they_took_themselves(self):
        self._morning()
        self._absence(self.teacher_a, self.day)
        cover = self.Cover.browse(self._self_assign())
        self.assertTrue(self._board_row(self.guard_user)['can_self_release'])

        self.Cover.with_user(self.guard_user).board_self_release(cover.id)

        self.assertEqual(cover.state, 'released')
        self.assertTrue(self._board_row(self.guard_user)['can_self_assign'])

    def test_a_guard_sent_by_the_planner_cannot_leave_on_their_own(self):
        self._morning()
        self._absence(self.teacher_a, self.day)
        cover = self.Cover.browse(self._assign())

        self.assertFalse(cover.is_self_assigned)
        self.assertFalse(self._board_row(self.guard_user)['can_self_release'])
        with self.assertRaises(AccessError):
            self.Cover.with_user(self.guard_user).board_self_release(cover.id)
        self.assertEqual(cover.state, 'assigned')

    def test_nobody_else_can_release_a_self_assignment_as_its_guard(self):
        self._morning()
        self._absence(self.teacher_a, self.day)
        cover = self.Cover.browse(self._self_assign())

        with self.assertRaises(AccessError):
            self.Cover.with_user(self.teacher_guard_2.user_id).board_self_release(cover.id)

    def test_the_planner_can_still_change_a_self_assignment(self):
        self._morning()
        self._absence(self.teacher_a, self.day)
        first = self.Cover.browse(self._self_assign())

        second = self.Cover.browse(self._assign(guard=self.teacher_guard_2))

        self.assertEqual(first.state, 'released')
        self.assertEqual(second.guard_employee_id, self.teacher_guard_2)

    # Timetable changes (issues #539 and #581)

    def test_first_lessons_without_teacher_allow_a_late_entry(self):
        self._morning()
        self._absence(self.teacher_a, self.day, hour_from=8, hour_to=10)

        states = self._states()

        self.assertEqual(states['entry']['expected'], ('late_entry', 10))
        self.assertEqual(states['entry']['status'], 'proposal')
        self.assertIsNone(states['leave']['expected'])
        self.assertEqual(self._row(8, 9)['proposed'], ('late_entry', 10))

    def test_last_lessons_without_teacher_allow_an_early_leave(self):
        self._morning()
        self._absence(self.teacher_b, self.day)

        self.assertEqual(self._states()['leave']['expected'], ('early_leave', 11))

    def test_a_day_with_every_lesson_empty_has_no_classes(self):
        self._morning()
        self._absence(self.teacher_a, self.day)
        self._absence(self.teacher_b, self.day)

        states = self._states()

        self.assertEqual(states['entry']['expected'], ('no_classes', 0.0))
        self.assertIsNone(states['leave']['expected'])

    def test_a_lesson_in_the_middle_allows_nothing(self):
        self._morning()
        self._absence(self.teacher_a, self.day, hour_from=9, hour_to=10)

        states = self._states()

        self.assertIsNone(states['entry']['expected'])
        self.assertIsNone(states['leave']['expected'])

    def test_a_class_with_somebody_in_it_stops_the_run(self):
        """The other half of a split group, a co-teacher or a guard already sent: the students
        are looked after then, so they must come in for it."""
        self._morning()
        self._absence(self.teacher_a, self.day)
        self._assign(hour_from=9, hour_to=10)

        self.assertEqual(self._states()['entry']['expected'], ('late_entry', 9))

    def test_proposing_opens_a_draft_notice_for_the_group_only(self):
        self._morning()
        self._absence(self.teacher_a, self.day, hour_from=8, hour_to=10)

        action = self.Notice.with_user(self.department_chief).board_propose_absence_change(
            str(self.day), self.group_a.id, 'late_entry', 10.0)

        notice = self.Notice.browse(action['res_id'])
        self.assertEqual(notice.state, 'draft')
        self.assertEqual(notice.group_ids, self.group_a)
        self.assertEqual((notice.absence_date, notice.absence_change_type, notice.absence_change_hour),
                         (self.day, 'late_entry', 10.0))
        self.assertIn('Due to the justified absence of the assigned teacher', notice.message)
        self.assertIn('10:00', notice.message)
        self.assertEqual(self._states()['entry']['draft'], notice)
        again = self.Notice.with_user(self.department_chief).board_propose_absence_change(
            str(self.day), self.group_a.id, 'late_entry', 10.0)
        self.assertEqual(again['res_id'], notice.id, "the existing draft is reopened, not duplicated")

    def test_a_timetable_change_notice_cannot_be_sent_to_other_groups(self):
        self._morning()
        self._absence(self.teacher_a, self.day, hour_from=8, hour_to=10)
        notice = self.Notice.browse(self.Notice.with_user(self.department_chief).board_propose_absence_change(
            str(self.day), self.group_a.id, 'late_entry', 10.0)['res_id'])

        with self.assertRaises(ValidationError):
            notice.with_user(self.department_chief).group_ids = self.group_a | self.group_b

    def test_the_department_chief_sends_the_notice_to_the_group(self):
        """Department chiefs had no notices before: sending one queues an email per recipient
        exactly like any other notice."""
        student = self.env['res.partner'].create({
            'name': 'TABC Student', 'contact_type': 'student', 'student_id': next_student_id(),
            'main_group_id': self.group_a.id, 'email': 'tabc.student@example.com'})
        # The notice's chatter entry needs a sender address, which every real user has.
        self.department_chief.email = 'tabc.chief@example.com'
        self._morning()
        self._absence(self.teacher_a, self.day, hour_from=8, hour_to=10)
        notice = self.Notice.with_user(self.department_chief).browse(
            self.Notice.with_user(self.department_chief).board_propose_absence_change(
                str(self.day), self.group_a.id, 'late_entry', 10.0)['res_id'])

        self.assertIn(student, notice.notice_line_ids.partner_id)
        notice.action_send()

        self.assertEqual(notice.state, 'scheduled')
        self.assertEqual(self._states()['entry']['status'], 'communicated')

    # Notices for department chiefs: the groups their department teaches

    def test_a_department_chief_writes_to_the_groups_their_department_teaches(self):
        self._morning()  # teacher_a and teacher_b, both of the department, teach group_a

        Notice = self.Notice.with_user(self.department_chief)
        notice = Notice.create({'subject': 'TABC plain notice', 'message': '<p>x</p>', 'group_ids': [(6, 0, self.group_a.ids)]})

        self.assertEqual(notice.available_group_ids, self.group_a)
        with self.assertRaises(ValidationError):
            Notice.create({'subject': 'TABC other group', 'message': '<p>x</p>', 'group_ids': [(6, 0, self.group_b.ids)]})
        with self.assertRaises(ValidationError):
            notice.group_ids = self.group_a | self.group_b

    def test_a_department_chief_reads_the_notices_of_their_groups_but_edits_only_their_own(self):
        self._morning()
        to_their_group = self.Notice.create({'subject': 'TABC to group A', 'message': '<p>x</p>', 'group_ids': [(6, 0, self.group_a.ids)]})
        unrelated = self.Notice.create({'subject': 'TABC to group B', 'message': '<p>x</p>', 'group_ids': [(6, 0, self.group_b.ids)]})

        visible = self.Notice.with_user(self.department_chief).search([('id', 'in', (to_their_group | unrelated).ids)])

        self.assertEqual(visible, to_their_group)
        with self.assertRaises(AccessError):
            to_their_group.with_user(self.department_chief).subject = 'Changed'
        self.assertFalse(self.Notice.with_user(self.other_department_chief).search([('id', '=', to_their_group.id)]),
                         "another department's chief does not see it")

    def test_head_of_studies_is_not_limited_to_a_department(self):
        notice = self.Notice.with_user(self.head_of_studies).create(
            {'subject': 'TABC HoS notice', 'message': '<p>x</p>', 'group_ids': [(6, 0, self.group_b.ids)]})

        self.assertIn(self.group_b, notice.available_group_ids)

    def test_proposing_needs_the_chain_of_command(self):
        self._morning()
        self._absence(self.teacher_a, self.day, hour_from=8, hour_to=10)

        with self.assertRaises(AccessError):
            self.Notice.with_user(self.other_department_chief).board_propose_absence_change(
                str(self.day), self.group_a.id, 'late_entry', 10.0)

    def test_proposing_something_the_absences_do_not_allow_is_refused(self):
        self._morning()
        self._absence(self.teacher_a, self.day, hour_from=8, hour_to=10)

        with self.assertRaises(UserError):
            self.Notice.with_user(self.department_chief).board_propose_absence_change(
                str(self.day), self.group_a.id, 'late_entry', 11.0)

    def _communicate(self, change_type, hour):
        notice = self.Notice.browse(self.Notice.with_user(self.department_chief).board_propose_absence_change(
            str(self.day), self.group_a.id, change_type, hour)['res_id'])
        # What action_send leaves behind; sending for real needs recipients this group has none of.
        notice.state = 'scheduled'
        return notice

    def test_a_communicated_late_entry_strikes_out_the_rows(self):
        self._morning()
        self._absence(self.teacher_a, self.day, hour_from=8, hour_to=10)
        self._communicate('late_entry', 10.0)

        self.assertEqual(self._states()['entry']['status'], 'communicated')
        self.assertEqual(self._row(8, 9)['authorized'], ('late_entry', 10))
        self.assertEqual(self._row(9, 10)['authorized'], ('late_entry', 10))
        self.assertFalse([action for action in self._actions() if action['group'] == self.group_a])

    def test_a_communicated_late_entry_makes_a_guard_unnecessary(self):
        self._morning()
        self._absence(self.teacher_a, self.day, hour_from=8, hour_to=9)
        self._communicate('late_entry', 9.0)
        # A guard assigned before the families were told (made directly: the board itself no
        # longer offers a class the students are not coming to).
        cover = self.Cover.create({
            'date': self.day, 'hour_from': 8, 'hour_to': 9, 'absent_employee_id': self.teacher_a.id,
            'group_id': self.group_a.id, 'guard_employee_id': self.teacher_guard.id})

        self.assertIn(cover, [action.get('cover') for action in self._actions()])
        with self.assertRaises(UserError):
            self._assign(guard=self.teacher_guard_2)

    def test_a_shorter_change_than_allowed_is_the_planners_decision(self):
        """Two empty first lessons, but the families are only told to come an hour later: the
        first lesson is struck out, the second still needs a guard, and nothing asks to correct
        the notice."""
        self._morning()
        self._absence(self.teacher_a, self.day, hour_from=8, hour_to=10)

        self.assertEqual(self._states()['entry']['options'], [('late_entry', 9), ('late_entry', 10)])
        self._communicate('late_entry', 9.0)

        self.assertEqual(self._states()['entry']['status'], 'communicated')
        self.assertEqual(self._row(8, 9)['authorized'], ('late_entry', 9))
        self.assertIsNone(self._row(9, 10)['authorized'])
        self.assertTrue(self._assign(hour_from=9, hour_to=10))

    def test_an_absence_that_grows_after_the_notice_keeps_the_notice(self):
        """The new empty lesson is one more to cover; what was told is still true."""
        self._morning()
        leave = self._absence(self.teacher_a, self.day, hour_from=8, hour_to=9, approve=False)
        self._communicate('late_entry', 9.0)

        leave.action_refuse()
        self._absence(self.teacher_a, self.day, hour_from=8, hour_to=10)

        self.assertEqual(self._states()['entry']['status'], 'communicated')
        self.assertIsNone(self._row(9, 10)['authorized'])

    def test_an_absence_that_shrinks_after_the_notice_asks_for_a_correction(self):
        self._morning()
        leave = self._absence(self.teacher_a, self.day, hour_from=8, hour_to=10, approve=False)
        self._communicate('late_entry', 10.0)

        leave.action_refuse()
        self._absence(self.teacher_a, self.day, hour_from=8, hour_to=9)

        state = self._states()['entry']
        self.assertEqual(state['status'], 'rectification')
        self.assertEqual(state['options'], [('late_entry', 9), ('normal_entry', 0.0)])
        self.assertEqual(state['target'], ('late_entry', 9))
        notice = self.Notice.browse(self.Notice.with_user(self.department_chief).board_propose_absence_change(
            str(self.day), self.group_a.id, 'late_entry', 9.0)['res_id'])
        self.assertTrue(notice.subject.startswith('Correction'))

    def test_a_cancelled_absence_after_the_notice_asks_to_go_back_to_normal(self):
        self._morning()
        leave = self._absence(self.teacher_a, self.day, hour_from=8, hour_to=10, approve=False)
        self._communicate('late_entry', 10.0)

        leave.action_refuse()

        state = self._states()['entry']
        self.assertEqual(state['status'], 'rectification')
        self.assertEqual(state['target'], ('normal_entry', 0.0))
        self._communicate('normal_entry', 0.0)
        self.assertIsNone(self._states()['entry']['status'], "once corrected, nothing is left to do")

    # Changes whose time has come (issue #599)

    def _at(self, hour):
        """The board read on self.day itself, at `hour` (company time)."""
        now = self.env['ems.datetime_utils'].time_float_to_local_datetime(self.day, hour)
        return patch.object(EmsDatetimeUtils, 'get_local_datetime', lambda utils: now)

    def test_a_late_entry_whose_time_has_come_is_no_longer_proposed(self):
        """At 9:30 the students can no longer be told to come in at 9:00, only at 10:00; from
        10:00 on there is nothing left to propose."""
        self._morning()
        self._absence(self.teacher_a, self.day, hour_from=8, hour_to=10)

        with self._at(9.5):
            state = self._states()['entry']
            self.assertEqual(state['options'], [('late_entry', 10)])
            self.assertEqual(state['expected'], ('late_entry', 10))
            self.assertEqual(self._row(8, 9)['proposed'], ('late_entry', 10))
            with self.assertRaises(UserError):
                self.Notice.with_user(self.department_chief).board_propose_absence_change(
                    str(self.day), self.group_a.id, 'late_entry', 9.0)
        with self._at(10):
            self.assertIsNone(self._states()['entry']['status'])
            self.assertIsNone(self._row(8, 9)['proposed'])
            self.assertFalse([action for action in self._actions() if action['type'] == 'proposal'])

    def test_an_early_leave_is_proposed_until_its_time(self):
        self._morning()
        self._absence(self.teacher_b, self.day)

        with self._at(10.5):
            self.assertEqual(self._states()['leave']['status'], 'proposal')
        with self._at(11):
            self.assertIsNone(self._states()['leave']['status'])

    def test_no_classes_is_no_longer_proposed_once_the_day_has_started(self):
        self._morning()
        self._absence(self.teacher_a, self.day)
        self._absence(self.teacher_b, self.day)

        with self._at(8):
            self.assertEqual(self._states()['entry']['options'],
                             [('late_entry', 9), ('late_entry', 10), ('late_entry', 11)])

    def test_a_longer_break_is_proposed_until_it_would_start(self):
        self._morning_with_break()
        self._absence(self.teacher_a, self.day, hour_from=9, hour_to=10)
        self._absence(self.teacher_b, self.day, hour_from=10.5, hour_to=11.5)

        with self._at(9.5):
            self.assertEqual(self._break_state()['options'], [('long_break', 10, 11.5)])

    def test_a_correction_is_offered_only_while_it_can_still_reach_the_families(self):
        """Told to come in at 10:00 and the absence cancelled: going back to the usual 8:00 start
        is only worth telling before 8:00, and once 10:00 has come what was told is settled."""
        self._morning()
        leave = self._absence(self.teacher_a, self.day, hour_from=8, hour_to=10, approve=False)
        self._communicate('late_entry', 10.0)
        leave.action_refuse()

        with self._at(7.5):
            self.assertEqual(self._states()['entry']['target'], ('normal_entry', 0.0))
        with self._at(8.5):
            self.assertIsNone(self._states()['entry']['status'])
        with self._at(10):
            self.assertEqual(self._states()['entry']['status'], 'communicated')

    def test_the_proposed_notice_and_the_guard_message_are_translated(self):
        """The code strings reach their readers in their own language: the draft notice in the
        planner's, the guard's message in the guard's."""
        if not self.env['res.lang'].search_count([('code', '=', 'ca_ES'), ('active', '=', True)]):
            self.skipTest("Catalan is not installed on this database")
        self.department_chief.lang = 'ca_ES'
        self.guard_user.lang = 'ca_ES'
        self._morning()
        self._absence(self.teacher_a, self.day, hour_from=8, hour_to=10)

        notice = self.Notice.browse(self.Notice.with_user(self.department_chief).with_context(lang='ca_ES')
                                    .board_propose_absence_change(str(self.day), self.group_a.id, 'late_entry', 10.0)['res_id'])
        self._assign()

        self.assertIn('del docent assignat', notice.message)
        self.assertIn('començarà les classes a les 10:00', notice.message)
        self.assertIn("podran entrar més tard", notice.subject)
        self.assertIn('Guàrdia: cobrir', self._guard_messages(self.teacher_guard).subject)

    # Longer breaks

    def _morning_with_break(self):
        """group_a's Monday: teacher_a 8-9 and 9-10, the level's break 10:00-10:30, teacher_b
        10:30-11:30 and 11:30-12:30."""
        framework = self.env['resource.calendar'].create({
            'name': 'TABC Framework (Break)', 'is_framework': True, 'level_id': self.level.id,
            'full_time_required_hours': 24})
        self.env['resource.calendar.attendance'].create({
            'calendar_id': framework.id, 'name': 'BR: Break', 'dayofweek': '0', 'hour_from': 10, 'hour_to': 10.5,
            'day_period': 'morning', 'non_teaching': self.non_teaching_break.id})
        self._schedule_class(self.teacher_a, self.group_a, 'TABC Calendar A (Break)', periods=((8, 9), (9, 10)))
        self._schedule_class(self.teacher_b, self.group_a, 'TABC Calendar B (Break)', periods=((10.5, 11.5), (11.5, 12.5)))
        self._guards(self.teacher_guard)

    def _break_state(self):
        return next(state for side, state in self._states().items() if side.startswith('break@'))

    def test_an_empty_lesson_next_to_the_break_allows_a_longer_break(self):
        self._morning_with_break()
        self._absence(self.teacher_a, self.day, hour_from=9, hour_to=10)
        self._absence(self.teacher_b, self.day, hour_from=10.5, hour_to=11.5)

        state = self._break_state()

        self.assertEqual(state['status'], 'proposal')
        self.assertEqual(state['options'], [('long_break', 10, 11.5), ('long_break', 9, 10.5), ('long_break', 9, 11.5)])
        self.assertEqual(state['target'], ('long_break', 9, 11.5))

    def test_empty_lessons_reaching_the_start_of_the_day_are_a_late_entry_not_a_longer_break(self):
        """They come in after the break (10:30), not have a longer one."""
        self._morning_with_break()
        self._absence(self.teacher_a, self.day, hour_from=8, hour_to=10)

        states = self._states()

        self.assertEqual(self._break_state()['options'], [])
        self.assertEqual(states['entry']['options'], [('late_entry', 9), ('late_entry', 10.5)])

    def test_empty_lessons_reaching_the_end_of_the_day_are_an_early_leave(self):
        self._morning_with_break()
        self._absence(self.teacher_b, self.day)

        self.assertEqual(self._break_state()['options'], [])
        self.assertEqual(self._states()['leave']['options'], [('early_leave', 11.5), ('early_leave', 10)])

    def test_a_communicated_longer_break_strikes_out_its_lessons(self):
        self._morning_with_break()
        self._absence(self.teacher_a, self.day, hour_from=9, hour_to=10)
        notice = self.Notice.browse(self.Notice.with_user(self.department_chief).board_propose_absence_change(
            str(self.day), self.group_a.id, 'long_break', 9.0, 10.5)['res_id'])

        self.assertEqual((notice.absence_change_type, notice.absence_change_hour, notice.absence_change_hour_to),
                         ('long_break', 9.0, 10.5))
        self.assertIn('09:00', notice.message)
        self.assertIn('10:30', notice.message)
        notice.state = 'scheduled'

        self.assertEqual(self._break_state()['status'], 'communicated')
        self.assertEqual(self._row(9, 10)['authorized'], ('long_break', 9, 10.5))
        with self.assertRaises(UserError):
            self._assign(hour_from=9, hour_to=10)

    def test_a_cancelled_absence_after_a_longer_break_asks_for_the_usual_break(self):
        self._morning_with_break()
        leave = self._absence(self.teacher_a, self.day, hour_from=9, hour_to=10, approve=False)
        self.Notice.browse(self.Notice.with_user(self.department_chief).board_propose_absence_change(
            str(self.day), self.group_a.id, 'long_break', 9.0, 10.5)['res_id']).state = 'scheduled'

        leave.action_refuse()

        state = self._break_state()
        self.assertEqual(state['status'], 'rectification')
        self.assertEqual(state['options'], [('normal_break', 10, 10.5)])
        notice = self.Notice.browse(self.Notice.with_user(self.department_chief).board_propose_absence_change(
            str(self.day), self.group_a.id, 'normal_break', 10.0, 10.5)['res_id'])
        self.assertTrue(notice.subject.startswith('Correction'))
