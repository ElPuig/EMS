from datetime import timedelta

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
        cls.teacher_b.parent_id = cls.teacher_a.parent_id
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

    def test_department_chiefs_only_reach_their_own_timetable_change_notices(self):
        other = self.Notice.create({'subject': 'TABC unrelated', 'message': '<p>x</p>'})
        self._morning()
        self._absence(self.teacher_a, self.day, hour_from=8, hour_to=10)
        own = self.Notice.browse(self.Notice.with_user(self.department_chief).board_propose_absence_change(
            str(self.day), self.group_a.id, 'late_entry', 10.0)['res_id'])

        visible = self.Notice.with_user(self.department_chief).search([('id', 'in', (own | other).ids)])

        self.assertEqual(visible, own)
        with self.assertRaises(AccessError):
            self.Notice.with_user(self.department_chief).create({'subject': 'TABC plain notice', 'message': '<p>x</p>'})

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

    def test_an_absence_that_grows_after_the_notice_asks_for_a_correction(self):
        self._morning()
        leave = self._absence(self.teacher_a, self.day, hour_from=8, hour_to=9, approve=False)
        self._communicate('late_entry', 9.0)

        leave.action_refuse()
        self._absence(self.teacher_a, self.day, hour_from=8, hour_to=10)

        state = self._states()['entry']
        self.assertEqual(state['status'], 'rectification')
        self.assertEqual(state['target'], ('late_entry', 10))
        notice = self.Notice.browse(self.Notice.with_user(self.department_chief).board_propose_absence_change(
            str(self.day), self.group_a.id, 'late_entry', 10.0)['res_id'])
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

        self.assertIn('començarà les classes a les 10:00', notice.message)
        self.assertIn("Canvi d'horari", notice.subject)
        self.assertIn('Guàrdia: cobrir', self._guard_messages(self.teacher_guard).subject)
