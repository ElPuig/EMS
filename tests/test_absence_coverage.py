from datetime import timedelta
from unittest.mock import patch

from odoo.addons.ems.models.shared.datetime_utils import EmsDatetimeUtils
from odoo.exceptions import AccessError, UserError, ValidationError

from .common import (
    create_head_of_studies_branch, create_level_study, create_role_employee, create_role_user, next_student_id)
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
        # Accepting an arrangement sends its notices (issue #652): never let one reach a real
        # mail server, whatever this box has configured.
        mail_patcher = patch('odoo.addons.base.models.ir_mail_server.IrMailServer.send_email', return_value='tabc@example.com')
        mail_patcher.start()
        cls.addClassCleanup(mail_patcher.stop)
        # The teachers are notified in their own language: these assertions read English.
        for employee in cls.teacher_a | cls.teacher_b | cls.teacher_c:
            (employee.user_id.partner_id or employee.work_contact_id).lang = 'en_US'

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
        self.department_chief.email = 'chief.tabc@example.com'

        cover = self.Cover.browse(self._assign())

        self.assertEqual(cover.guard_employee_id, self.teacher_guard)
        self.assertEqual((cover.hour_from, cover.hour_to), (8, 9))
        self.assertEqual(cover.subject_id, self.subject)
        messages = self._guard_messages(self.teacher_guard)
        self.assertEqual(len(messages), 1)
        self.assertIn('Exercises on page 12', messages.body)
        self.assertIn(self.group_a.name, messages.subject)
        # Answering the notice reaches whoever sent the guard, not the EMS mailbox (issue #607).
        self.assertIn('chief.tabc@example.com', messages.reply_to)

    def test_the_row_shows_its_guard_in_the_guard_colour(self):
        self._morning()
        self._absence(self.teacher_a, self.day)
        self._assign()

        line = self._teaching_line(self.day, 8, 9)
        row = self._absence_row(line, self.teacher_a)

        self.assertEqual(row['covers'].guard_employee_id, self.teacher_guard)
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

    def test_the_guard_badge_is_coloured_only_in_the_blocks_they_cover(self):
        """Issue #675: on guard 8-11 but sent only to the 8-9 class, their 9-10 and 10-11 badges
        stay plain, on screen and on the PDF."""
        self._morning()
        self._absence(self.teacher_a, self.day)
        self._assign()

        data = self.env.company.current_course_id.with_user(self.department_chief).get_guard_duty_board_data(
            '0', 'morning', day=str(self.day))
        badges = {line['time_label']: next(guard for guard in line['guards'] if guard['id'] == self.teacher_guard.id)
                  for line in data['lines'] if any(guard['id'] == self.teacher_guard.id for guard in line['guards'])}
        # `is not False`: colour 0 is a colour, and 0 == False.
        self.assertEqual({label: badge['color'] is not False for label, badge in badges.items()},
                         {'08:00-09:00': True, '09:00-10:00': False, '10:00-11:00': False})
        html, _content_type = self.env['ir.actions.report'].with_context(
            guard_duty_weekday='0', guard_duty_date=str(self.day), guard_duty_view='table').\
            _render_qweb_html('ems.report_guard_duty_board', [self.env.company.current_course_id.id])
        self.assertEqual(html.count(b'gdb-guard-badge gdb-cover-'), 1)

    def test_a_guard_block_with_nothing_covered_leaves_its_colour_free(self):
        """Issue #675: teacher_guard (on guard 8-11) only covers 8-9, so their 10-11 badge shows no
        colour and the 10-11 class can take the same one."""
        self._morning()
        self._absence(self.teacher_a, self.day)
        self._assign()
        self._assign(self.teacher_guard_2, 10, 11)

        colors = self._teaching_line(self.day, 10, 11)['cover_colors']

        self.assertEqual(colors[self.teacher_guard.id], colors[self.teacher_guard_2.id])

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
        self.assertFalse(self._row()['covers'])
        self.assertEqual(len(self._guard_messages(self.teacher_guard)), 2)

    def test_only_the_absent_teachers_chain_of_command_can_assign(self):
        self._morning()
        self._absence(self.teacher_a, self.day)

        self._assign(user=self.head_of_studies)
        for outsider in (self.other_department_chief, self.other_head_of_studies, self.teacher_a_user, self.guard_user):
            with self.subTest(user=outsider.name), self.assertRaises(AccessError):
                self._assign(user=outsider)

    def test_the_department_chief_manages_a_member_reporting_elsewhere(self):
        """Issue #604: a member of the management team (e.g. the Secretary) who teaches in the
        department reports to the Director, out of its chain of command: their department's
        Chief still organises their absences, a chief of another department doesn't."""
        secretary_user = create_role_user(self, 'teacher', 'test_secretary_tabc', name='TABC Secretary')
        secretary = create_role_employee(self, secretary_user, department_id=self.department.id)
        secretary.parent_id = self.other_head_of_studies.employee_ids
        self.assertNotIn(self.department_chief, secretary.tutor_scope_user_ids)
        Course = self.env['ems.course']

        self.assertTrue(Course.with_user(self.department_chief)._is_absence_manager(secretary))
        for outsider in (self.other_department_chief, secretary_user, self.guard_user):
            with self.subTest(user=outsider.name):
                self.assertFalse(Course.with_user(outsider)._is_absence_manager(secretary))

    def test_the_administrator_manages_any_absence(self):
        """Above Direction, although not a teacher and so nowhere in the hierarchy."""
        self._morning()
        self._absence(self.teacher_a, self.day)

        self.assertTrue(self._assign(user=self.env.ref('base.user_admin')))

    # Shared teachers (issue #622): whoever answers for the students who lose the class manages it
    # too, besides whoever answers for the absent teacher

    def _students_department(self):
        """The study of group_a and group_b belongs to another department than teacher_a's: its Department
        Chief is other_department_chief, it has a Seminar Chief of its own, and it hangs from an
        area managed by other_head_of_studies."""
        Department = self.env['hr.department']
        area = Department.create({
            'name': 'TABC Students Area', 'manager_id': self.other_head_of_studies.employee_ids.id})
        self.seminar_chief = create_role_user(
            self, 'department_chief', 'test_seminar_chief_tabc', name='TABC Students Seminar Chief')
        department = Department.create({
            'name': 'TABC Students Department', 'parent_id': area.id,
            'manager_id': self.other_department_chief.employee_ids.id,
            'seminar_chief_id': create_role_employee(self, self.seminar_chief).id,
        })
        self.study.managing_department_id = department
        return department

    def test_a_shared_teachers_class_is_managed_by_the_groups_department(self):
        self._morning()
        self._absence(self.teacher_a, self.day)
        self._students_department()
        director = create_role_user(self, 'director', 'test_director_tabc', name='TABC Director')
        self.env.company.director_id = create_role_employee(self, director)

        # The students' department and whoever is above it, and still the teacher's own chain.
        for manager in (self.other_department_chief, self.seminar_chief, self.other_head_of_studies, director,
                        self.env.ref('base.user_admin'), self.department_chief, self.head_of_studies):
            with self.subTest(user=manager.name):
                self.assertTrue(self._assign(user=manager))
        outsider_chief = create_role_user(self, 'department_chief', 'test_outsider_chief_tabc', name='TABC Outsider Chief')
        self.env['hr.department'].create({
            'name': 'TABC Outsider Department', 'manager_id': create_role_employee(self, outsider_chief).id})
        for outsider in (outsider_chief, self.teacher_a_user, self.guard_user):
            with self.subTest(user=outsider.name), self.assertRaises(AccessError):
                self._assign(user=outsider)

    def test_the_groups_department_only_manages_the_classes_of_its_own_groups(self):
        level, study = create_level_study(self, 'TABCU')
        unmanaged = self.env['ems.group'].create({
            'course': 1, 'acronym': 'TABCU', 'level_id': level.id, 'study_id': study.id, 'shift': 'morning'})
        self.subject.study_ids |= study
        calendar = self._new_calendar(self.teacher_a, 'TABC Calendar A (Two Groups)')
        calendar.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': hour_from, 'hour_to': hour_from + 1, 'day_period': 'morning',
            'subject_id': self.subject.id, 'group_ids': [group.id], 'name': f'{group.acronym}: TGDB',
        } for hour_from, group in ((8, self.group_a), (9, unmanaged))])
        self._guards(self.teacher_guard)
        self._absence(self.teacher_a, self.day)
        self._students_department()
        course = self.env.company.current_course_id

        def can_manage(user):
            data = course.with_user(user).get_guard_duty_board_data('0', 'morning', day=str(self.day))
            return {row['group_id']: row['can_manage'] for line in data['lines'] for row in line['absences']
                    if row['teacher_id'] == self.teacher_a.id}

        self.assertEqual(can_manage(self.other_department_chief), {self.group_a.id: True, unmanaged.id: False})
        self.assertEqual(can_manage(self.department_chief), {self.group_a.id: True, unmanaged.id: True})
        self.Cover.with_user(self.department_chief).board_assign(
            str(self.day), 9, 10, self.teacher_a.id, unmanaged.id, self.teacher_guard.id)
        with self.assertRaises(AccessError):
            self.Cover.with_user(self.other_department_chief).board_assign(
                str(self.day), 9, 10, self.teacher_a.id, unmanaged.id, self.teacher_guard.id)

    def test_a_reinforcement_group_is_managed_by_its_main_groups_departments(self):
        department = self._students_department()
        reinforcement = self.env['ems.group'].create({
            'group_type': 'reinforcement', 'name': 'TABC Reinforcement', 'parent_group_ids': [(6, 0, self.group_a.ids)]})
        alone = self.env['ems.group'].create({'group_type': 'reinforcement', 'name': 'TABC Reinforcement Alone'})
        Course = self.env['ems.course']

        self.assertEqual(reinforcement.managing_department_ids, department)
        self.assertTrue(Course.with_user(self.other_department_chief)._is_absence_manager(self.teacher_a, reinforcement))
        # No main group to go by: the teacher's own chain, as for any unmanaged group.
        self.assertFalse(alone.managing_department_ids)
        self.assertTrue(Course.with_user(self.department_chief)._is_absence_manager(self.teacher_a, alone))
        self.assertFalse(Course.with_user(self.other_department_chief)._is_absence_manager(self.teacher_a, alone))

    def test_the_groups_department_releases_arranges_and_proposes(self):
        self._morning()
        self._absence(self.teacher_a, self.day, hour_from=8, hour_to=10)
        cover_id = self._assign()
        self._students_department()

        self.Cover.with_user(self.seminar_chief).board_release(cover_id)
        self.assertIsInstance(self.env['ems.course'].with_user(self.seminar_chief).get_arrangement_candidates(
            str(self.day), 9, 10, self.teacher_a.id, self.group_a.id), list)
        self.assertTrue(self.Cover.with_user(self.seminar_chief).board_arrange(
            str(self.day), 9, 10, self.teacher_a.id, self.group_a.id, 'manual', note='Joined with another group')['cover_id'])
        # None of the department's own teachers teaches the group: managing it is enough to
        # write to its families.
        action = self.Notice.with_user(self.other_department_chief)._board_absence_change_draft(
            str(self.day), self.group_a.id, 'late_entry', 9.0)._absence_change_form_action()
        self.assertEqual(self.Notice.browse(action['res_id']).group_ids, self.group_a)

    def test_a_guard_duty_of_a_shared_teacher_is_managed_by_the_departments_named_on_them(self):
        """A guard duty has no students of its own: only the teacher to go by - their chain of
        command and the departments named on them as also managing them."""
        department = self._students_department()
        Course = self.env['ems.course']
        self.assertTrue(Course.with_user(self.department_chief)._is_absence_manager(self.teacher_a))
        self.assertFalse(Course.with_user(self.other_department_chief)._is_absence_manager(self.teacher_a))

        self.teacher_a.managing_department_ids = department.parent_id

        self.assertTrue(Course.with_user(self.other_head_of_studies)._is_absence_manager(self.teacher_a))
        self.assertFalse(Course.with_user(self.other_department_chief)._is_absence_manager(self.teacher_a),
                         "the area was named, not this department of it")
        self.teacher_a.managing_department_ids = department
        for manager in (self.other_department_chief, self.seminar_chief, self.other_head_of_studies,
                        self.department_chief):
            with self.subTest(user=manager.name):
                self.assertTrue(Course.with_user(manager)._is_absence_manager(self.teacher_a))
        self.assertFalse(Course.with_user(self.teacher_a_user)._is_absence_manager(self.teacher_a))

    def test_existing_studies_start_out_managed_by_the_department_giving_most_of_their_classes(self):
        self._morning()  # one teaching each: teacher_a (cls.department) and teacher_b
        other = self.env['hr.department'].create({'name': 'TABC Another Department'})
        self.teacher_b.department_id = other
        Teaching, Study = self.env['ems.teaching'], self.env['ems.study']
        self.assertEqual(Teaching.search([('group_id', '=', self.group_a.id)]).teacher_id, self.teacher_a | self.teacher_b)

        Study._backfill_managing_department()
        self.assertFalse(self.study.managing_department_id, "half of the classes is not most of them")

        self.teacher_c.department_id = self.department
        Teaching.create({'teacher_id': self.teacher_c.id, 'group_id': self.group_b.id, 'subject_id': self.subject.id})
        Study._backfill_managing_department()
        self.assertEqual(self.study.managing_department_id, self.department)

        self.study.managing_department_id = other
        Study._backfill_managing_department()
        self.assertEqual(self.study.managing_department_id, other, "one already chosen is never replaced")

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

        def cover(guard, day, state='assigned', group=None, absent=None, space=None, hour_from=8, hour_to=9):
            self.Cover.create({
                'date': day, 'hour_from': hour_from, 'hour_to': hour_to,
                'absent_employee_id': (absent or self.teacher_b).id,
                'group_id': (group or self.group_a).id, 'space_id': (space or self.space).id,
                'guard_employee_id': guard.id, 'state': state})

        cover(self.teacher_guard, start)
        cover(self.teacher_guard, start - timedelta(days=1))
        cover(self.teacher_guard_2, start, state='released')
        # Issue #629: two groups looked after together in one room in the same period are one
        # guard, not two; the next period with one of them is another one...
        cover(self.teacher_guard, start, group=self.group_b)
        cover(self.teacher_guard, start, group=self.group_b, hour_from=9, hour_to=10)
        # ...while two groups in two rooms at the same time are two.
        cover(self.teacher_guard_2, start, hour_from=10, hour_to=11)
        cover(self.teacher_guard_2, start, group=self.group_b, space=self.space_b, hour_from=10, hour_to=11)

        # Any teacher reads the board, so any teacher reads the counts too.
        line = self.env['ems.course'].with_user(self.guard_user).get_guard_duty_board_data(
            '0', 'morning', day=str(self.day))['lines'][0]
        expected = {self.teacher_guard.id: 3, self.teacher_guard_2.id: 2}
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
        self.assertEqual(self._row(8, 9)['covers'].guard_employee_id, self.teacher_guard)
        self.assertFalse(self._row(10, 11)['covers'], "the hour the request adds is new, to be decided")
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
        self.assertEqual(self._duty_row()['covers'], cover)
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
        # Several rows can start at hour_from: another level's break is a row of its own (issue #637).
        return next(row for line in data['lines'] if line['hour_from'] == hour_from
                    for row in line['absences'] if row['teacher_id'] == self.teacher_a.id)

    def test_a_guard_takes_a_free_class_without_anybody_being_notified(self):
        self._morning()
        self._absence(self.teacher_a, self.day)
        cover = self.Cover.browse(self._self_assign())

        self.assertEqual(cover.guard_employee_id, self.teacher_guard)
        self.assertEqual(cover.assigned_by_id, self.guard_user)
        self.assertTrue(cover.is_self_assigned)
        self.assertEqual(self._row()['covers'], cover)
        messages = self.env['mail.message'].search([('model', '=', 'ems.absence_cover'), ('res_id', '=', cover.id)])
        self.assertFalse(messages.partner_ids, "nobody is notified: the board already shows it")

    def test_the_board_offers_self_assignment_only_to_a_guard_on_duty(self):
        self._morning()
        self._absence(self.teacher_a, self.day)

        self.assertTrue(self._board_row(self.guard_user)['can_self_assign'])
        self.assertFalse(self._board_row(self.guard_user, hour_from=8)['self_cover_id'])
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
        self.assertTrue(self._board_row(self.guard_user)['self_cover_id'])

        self.Cover.with_user(self.guard_user).board_self_release(cover.id)

        self.assertEqual(cover.state, 'released')
        self.assertTrue(self._board_row(self.guard_user)['can_self_assign'])

    def test_a_guard_sent_by_the_planner_cannot_leave_on_their_own(self):
        self._morning()
        self._absence(self.teacher_a, self.day)
        cover = self.Cover.browse(self._assign())

        self.assertFalse(cover.is_self_assigned)
        self.assertFalse(self._board_row(self.guard_user)['self_cover_id'])
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

        action = self.Notice.with_user(self.department_chief)._board_absence_change_draft(
            str(self.day), self.group_a.id, 'late_entry', 10.0)._absence_change_form_action()

        notice = self.Notice.browse(action['res_id'])
        self.assertEqual(notice.state, 'draft')
        self.assertEqual(notice.group_ids, self.group_a)
        self.assertEqual((notice.absence_date, notice._absence_change_tuples()), (self.day, [('late_entry', 10.0)]))
        self.assertIn('Due to the justified absence of the assigned teacher', notice.message)
        self.assertIn('10:00', notice.message)
        self.assertEqual(self._states()['entry']['draft'], notice)
        again = self.Notice.with_user(self.department_chief)._board_absence_change_draft(
            str(self.day), self.group_a.id, 'late_entry', 10.0)._absence_change_form_action()
        self.assertEqual(again['res_id'], notice.id, "the existing draft is reopened, not duplicated")

    def test_a_timetable_change_notice_cannot_be_sent_to_other_groups(self):
        self._morning()
        self._absence(self.teacher_a, self.day, hour_from=8, hour_to=10)
        notice = self.Notice.browse(self.Notice.with_user(self.department_chief)._board_absence_change_draft(
            str(self.day), self.group_a.id, 'late_entry', 10.0)._absence_change_form_action()['res_id'])

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
            self.Notice.with_user(self.department_chief)._board_absence_change_draft(
                str(self.day), self.group_a.id, 'late_entry', 10.0)._absence_change_form_action()['res_id'])

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
            self.Notice.with_user(self.other_department_chief)._board_absence_change_draft(
                str(self.day), self.group_a.id, 'late_entry', 10.0)._absence_change_form_action()

    def test_proposing_something_the_absences_do_not_allow_is_refused(self):
        self._morning()
        self._absence(self.teacher_a, self.day, hour_from=8, hour_to=10)

        with self.assertRaises(UserError):
            self.Notice.with_user(self.department_chief)._board_absence_change_draft(
                str(self.day), self.group_a.id, 'late_entry', 11.0)._absence_change_form_action()

    def _communicate(self, change_type, hour):
        notice = self.Notice.browse(self.Notice.with_user(self.department_chief)._board_absence_change_draft(
            str(self.day), self.group_a.id, change_type, hour)._absence_change_form_action()['res_id'])
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
        notice = self.Notice.browse(self.Notice.with_user(self.department_chief)._board_absence_change_draft(
            str(self.day), self.group_a.id, 'late_entry', 9.0)._absence_change_form_action()['res_id'])
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
                self.Notice.with_user(self.department_chief)._board_absence_change_draft(
                    str(self.day), self.group_a.id, 'late_entry', 9.0)._absence_change_form_action()
        with self._at(10):
            self.assertIsNone(self._states()['entry']['status'])
            self.assertIsNone(self._row(8, 9)['proposed'])
            self.assertFalse([action for action in self._actions()
                              if action['type'] == 'proposal' and action['group'] == self.group_a])

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
                                    ._board_absence_change_draft(str(self.day), self.group_a.id, 'late_entry', 10.0)._absence_change_form_action()['res_id'])
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
        notice = self.Notice.browse(self.Notice.with_user(self.department_chief)._board_absence_change_draft(
            str(self.day), self.group_a.id, 'long_break', 9.0, 10.5)._absence_change_form_action()['res_id'])

        self.assertEqual(notice._absence_change_tuples(), [('long_break', 9.0, 10.5)])
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
        self.Notice.browse(self.Notice.with_user(self.department_chief)._board_absence_change_draft(
            str(self.day), self.group_a.id, 'long_break', 9.0, 10.5)._absence_change_form_action()['res_id']).state = 'scheduled'

        leave.action_refuse()

        state = self._break_state()
        self.assertEqual(state['status'], 'rectification')
        self.assertEqual(state['options'], [('normal_break', 10, 10.5)])
        notice = self.Notice.browse(self.Notice.with_user(self.department_chief)._board_absence_change_draft(
            str(self.day), self.group_a.id, 'normal_break', 10.0, 10.5)._absence_change_form_action()['res_id'])
        self.assertTrue(notice.subject.startswith('Correction'))

    # Internal arrangements (issues #605, #645): the board detects how the teachers of the group
    # could rearrange their lessons so that no guard is needed - swaps, and chains of moved lessons
    # ending in a timetable change for the families - the best first, as plans of steps the
    # planner applies whole or in part.

    def _options(self, hour_from=8, hour_to=9, absent=None):
        return self.env['ems.course']._get_arrangement_options(
            self.day, self.group_a, absent or self.teacher_a, hour_from, hour_to)

    def _summary(self, options):
        return [(option['type'], option['teacher'], option['hour_from']) for option in options]

    def _arrange(self, arrangement_type, teacher=None, hour_from=8, hour_to=9, absent=None, lesson=(0.0, 0.0),
                 note=False, user=None):
        result = self.Cover.with_user(user or self.department_chief).board_arrange(
            str(self.day), hour_from, hour_to, (absent or self.teacher_a).id, self.group_a.id, arrangement_type,
            teacher.id if teacher else False, note, *lesson)
        return self.Cover.browse(result['cover_id']), result['notice_action']

    def _messages(self, teacher, subject):
        return self._guard_messages(teacher).filtered(lambda message: subject in (message.subject or ''))

    def _plans(self, group=None):
        return self.env['ems.course']._get_arrangement_plans(self.day, group or self.group_a)

    @staticmethod
    def _plan_summary(plan):
        """Each step as `(kind, teacher, lesson start, gap start, groups)`, a notice (or a
        correction) as `('notice', change, groups)`."""
        return [(step['kind'], step['change'], step['groups']) if step['kind'] in ('notice', 'correction')
                else (step['kind'], step['teacher'], step['lesson'][0], step['target'][0], step['groups'])
                for step in plan['steps']]

    def _apply(self, plan, keep=None, user=None):
        """Applies `plan`, only the steps whose index is in `keep` when given."""
        data = self.env['ems.course']._arrangement_plan_data(plan)
        steps = [step['payload'] for index, step in enumerate(data['steps']) if keep is None or index in keep]
        result = self.Cover.with_user(user or self.department_chief).board_apply_plan(str(self.day), steps)
        return self.Cover.browse(result['cover_ids']), result['notice_action']

    def test_a_swap_and_a_moved_lesson_are_detected_swap_first(self):
        self._morning()
        self._absence(self.teacher_a, self.day, hour_from=8, hour_to=9)

        plans = [self._plan_summary(plan) for plan in self._plans()]

        self.assertEqual(plans[0], [('swap', self.teacher_b, 11, 8, self.group_a)], "the students lose no lesson")
        self.assertIn([('move', self.teacher_b, 11, 8, self.group_a), ('notice', ('early_leave', 11), self.group_a)], plans)

    def test_a_swap_needs_no_guard_and_shows_in_the_timetable(self):
        self._morning()
        self._absence(self.teacher_a, self.day, hour_from=8, hour_to=9)

        cover, notice_action = self._apply(self._plans()[0])

        notice = self.Notice.browse(notice_action['res_id'])
        self.assertFalse(notice.absence_changes, "a swap loses no lesson: there is nothing to tell the families")
        self.assertEqual(notice, cover.student_notice_id, "only its students, about the lessons swapped (issue #649)")
        self.assertEqual((cover.arrangement_type, cover.guard_employee_id), ('swap', self.teacher_b))
        self.assertTrue(cover.is_effective)
        self.assertEqual(self._row()['arrangement'], cover)
        self.assertFalse(self._row()['covers'], "an arrangement is no guard: no colour, no guard tag")
        self.assertIsNone(self._states()['entry']['status'], "somebody is with the group at 8")
        self.assertIsNone(self._states()['leave']['status'], "the absent teacher teaches at 11")
        cell = next(cell for cell in self._teaching_line(self.day, 11, 12)['cells'] if cell['group'] == self.group_a)
        self.assertEqual((cell['substitutes'], cell['moved']), (self.teacher_a, self.teacher_b))
        self.assertTrue(self._messages(self.teacher_a, 'Timetable arrangement'))
        message = self._messages(self.teacher_b, 'Timetable arrangement')
        self.assertIn('comes in at 08:00 instead of 11:00', message.body, "the change of entry time is spelt out")
        self.assertFalse(self._board_row(self.guard_user)['can_self_assign'])

    def test_a_guard_who_swaps_is_struck_out_of_the_guard_column(self):
        self._morning()
        calendar = self._new_calendar(self.teacher_guard, 'TABC Guard who teaches')
        calendar.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 8, 'hour_to': 9, 'day_period': 'morning',
            'non_teaching': self.non_teaching_guard.id, 'name': 'Guard',
        }, {
            'dayofweek': '0', 'hour_from': 11, 'hour_to': 12, 'day_period': 'morning', 'subject_id': self.subject.id,
            'group_ids': [self.group_a.id], 'name': 'TGDBA: TGDB',
        }])
        self._absence(self.teacher_a, self.day, hour_from=8, hour_to=9)
        # teacher_guard co-teaches teacher_b's 11:00 lesson: the swap takes both (issue #678).
        self.assertIn(('swap', self.teacher_b | self.teacher_guard, 11), self._summary(self._options()))

        cover, _notice_action = self._arrange('swap', self.teacher_guard, lesson=(11.0, 12.0))
        cover = cover._decision_pack().filtered(lambda other: other.guard_employee_id == self.teacher_guard)

        self.assertEqual(self._teaching_line(self.day, 8, 9)['guard_busy'][self.teacher_guard.id], cover)
        self.assertNotIn(self.teacher_guard, self.env['ems.course']._get_guard_candidates(self.day, 8, 9))
        data = self.env.company.current_course_id.with_user(self.department_chief).get_guard_duty_board_data(
            '0', 'morning', day=str(self.day))
        guard = next(guard for line in data['lines'] if line['hour_from'] == 8
                     for guard in line['guards'] if guard['id'] == self.teacher_guard.id)
        self.assertIn(self.group_a.name, guard['busy'])
        self.assertFalse(self._teaching_line(self.day, 9, 10)['guard_busy'], "only in that period")

    def _moved_lesson_plan(self):
        """teacher_a away 10-12: teacher_b's 11:00 lesson moved to 10, the group leaving at 11."""
        self._morning()
        self._absence(self.teacher_a, self.day, hour_from=10, hour_to=12)
        plan = self._plans()[0]
        self.assertEqual(self._plan_summary(plan), [
            ('move', self.teacher_b, 11, 10, self.group_a), ('notice', ('early_leave', 11), self.group_a)])
        return plan

    def test_a_moved_lesson_counts_once_its_notice_is_sent(self):
        """The group has no students: its notice cannot be sent when the plan is accepted (issue
        #652), so it stays a draft and the move waits for it."""
        cover, notice_action = self._apply(self._moved_lesson_plan())

        notice = self.Notice.browse(notice_action['res_id'])
        self.assertEqual((notice._absence_change_tuples(), notice.state), ([('early_leave', 11.0)], 'draft'))
        self.assertEqual(cover.notice_id, notice)
        self.assertFalse(cover.is_effective, "accepting it and telling the families go together")
        self.assertFalse(self._messages(self.teacher_b, 'Timetable arrangement'), "nobody is told before the notice")
        self.assertIn('pending_arrangement', [action['type'] for action in self._actions()])

        notice.state = 'scheduled'

        self.assertTrue(cover.is_effective)
        self.assertEqual(self._states()['leave']['communicated'], ('early_leave', 11))
        self.assertTrue(self._messages(self.teacher_b, 'Timetable arrangement'))
        self.assertNotIn('pending_arrangement', [action['type'] for action in self._actions()])

    def test_a_moved_lesson_shows_the_timetable_change_next_to_the_arrangement(self):
        """Issue #623: the class the lesson moved into says both who teaches it and that the
        group leaves earlier because of it, once the families have been told."""
        _cover, notice_action = self._apply(self._moved_lesson_plan())

        self.assertIsNone(self._row(10, 11)['arrangement_change'], "nothing changes before the notice is sent")
        self.assertFalse(self._board_row(self.department_chief, 10)['arrangement']['change'])

        self.Notice.browse(notice_action['res_id']).state = 'scheduled'

        row = self._row(10, 11)
        self.assertEqual(row['arrangement_change'], ('early_leave', 11))
        self.assertIsNone(row['authorized'], "the group is in class then: it is not a lesson the families were excused from")
        self.assertEqual(self._board_row(self.department_chief, 10)['arrangement']['change'], 'Leaves at 11:00')
        self.assertFalse(self._teaching_line(self.day, 11, 12)['absences'], "the lesson left free needs nobody")
        html, _content_type = self.env['ir.actions.report'].with_context(
            guard_duty_weekday='0', guard_duty_date=str(self.day), guard_duty_view='table').\
            _render_qweb_html('ems.report_guard_duty_board', [self.env.company.current_course_id.id])
        # Right after the arrangement's own tag, not only on the row of the lesson left free.
        self.assertIn(b'Leaves at 11:00', html.split(b'lesson to 10:00.')[1][:300])

    def test_a_swap_shows_no_timetable_change(self):
        self._morning()
        self._absence(self.teacher_a, self.day, hour_from=8, hour_to=9)
        self._arrange('swap', self.teacher_b, lesson=(11.0, 12.0))

        self.assertIsNone(self._row()['arrangement_change'])
        self.assertFalse(self._board_row(self.department_chief)['arrangement']['change'])

    def test_deleting_the_draft_notice_discards_the_moved_lesson(self):
        cover, notice_action = self._apply(self._moved_lesson_plan())
        students = cover.student_notice_id

        self.Notice.browse(notice_action['res_id']).unlink()

        self.assertFalse(cover.exists())
        self.assertFalse(students.exists(), "the students' draft about that move goes with it (issue #649)")
        self.assertTrue(self._plans(), "the class is offered again")

    def test_a_moved_lesson_without_its_notice_is_a_class_to_cover(self):
        """Issue #645: the planner keeps the move but not the notice. The move is in effect at
        once, and the lesson it left free is one more row of the table, covered like any other."""
        cover, notice_action = self._apply(self._moved_lesson_plan(), keep=[0])

        self.assertEqual(notice_action['res_id'], cover.student_notice_id.id, "only the students' notice (issue #649)")
        self.assertFalse(cover.notice_id)
        self.assertTrue(cover.is_effective)
        self.assertTrue(self._messages(self.teacher_b, 'Timetable arrangement'), "in effect: the teacher is told")
        self.assertEqual(self._row(10, 11)['arrangement'], cover)
        row = self._row(11, 12, teacher=self.teacher_b)
        self.assertEqual((row['state'], row['moved_cover']), ('moved', cover))
        self.assertTrue(row['can_manage'], "whoever organises the absence organises what it moved")
        data = self.env.company.current_course_id.with_user(self.department_chief).get_guard_duty_board_data(
            '0', 'morning', day=str(self.day))
        moved = next(absence for line in data['lines'] if line['time_label'] == '11:00-12:00'
                     for absence in line['absences'] if absence['teacher_id'] == self.teacher_b.id)
        self.assertEqual(moved['moved'], 'Lesson moved to 10:00')
        self.assertEqual(self._states()['leave']['status'], 'proposal', "the families can still be told")

        self._calendar_rows(self.teacher_guard, ((11, 12, 'guard'),))
        guard = self.Cover.browse(self.Cover.with_user(self.department_chief).board_assign(
            str(self.day), 11, 12, self.teacher_b.id, self.group_a.id, self.teacher_guard.id, 'Exercises'))

        self.assertEqual(self._row(11, 12, teacher=self.teacher_b)['covers'], guard)
        with self.assertRaises(AccessError):
            self.Cover.with_user(self.other_department_chief).board_assign(
                str(self.day), 11, 12, self.teacher_b.id, self.group_a.id, self.teacher_guard.id, 'Exercises')

    def test_a_lesson_its_teacher_could_not_give_is_taught_after_all(self):
        """Two absences: a swap teaches both classes, so it comes first; a move only one."""
        self._morning()
        self._absence(self.teacher_a, self.day, hour_from=8, hour_to=9)
        self._absence(self.teacher_b, self.day, hour_from=11, hour_to=12)

        plans = self._plans()

        # teacher_a teaches their 8:00 lesson at 11 and teacher_b the 11:00 one at 8: nobody loses
        # anything. Seen from either absence, it is one and the same plan.
        steps = plans[0]['steps']
        self.assertEqual([step['kind'] for step in steps], ['swap'])
        self.assertEqual(steps[0]['teacher'] | steps[0]['absent'], self.teacher_a | self.teacher_b)
        self.assertEqual(len([plan for plan in plans if [step['kind'] for step in plan['steps']] == ['swap']]), 1)

    def test_only_lessons_at_the_edges_of_the_day_are_moved(self):
        self._morning()
        self._absence(self.teacher_b, self.day, hour_from=11, hour_to=12)

        moves = [step[:4] for plan in self._plans() for step in self._plan_summary(plan) if step[0] == 'move']

        self.assertIn(('move', self.teacher_a, 8, 11), moves, "the first lesson: the group comes in later")
        self.assertNotIn(('move', self.teacher_a, 9, 11), moves, "the middle of the day is covered with a guard")

    def test_an_arrangement_never_lengthens_a_working_day(self):
        self._morning()
        self._absence(self.teacher_b, self.day, hour_from=11, hour_to=12)

        options = {(option['type'], option['hour_from']): option for option in self._options(11, 12, absent=self.teacher_b)}

        # teacher_a works 8-11. Swapping their 9:00 lesson for teacher_b's 11:00 one would keep
        # them until 12 without coming in later: not offered. Swapping the 8:00 one moves their
        # whole day an hour later and teacher_b's three hours earlier, each as long as before: offered,
        # saying so.
        self.assertNotIn(('swap', 9), options)
        self.assertEqual(set(options[('swap', 8)]['shifts']), {
            (self.teacher_a, 'entry', 8, 9), (self.teacher_a, 'exit', 11, 12),
            (self.teacher_b, 'entry', 11, 8), (self.teacher_b, 'exit', 12, 9),
        })

    def test_a_shared_lesson_moves_only_when_every_group_has_the_gap(self):
        self._calendar_rows(self.teacher_a, ((8, 9, self.group_a), (9, 10, self.group_a), (10, 11, self.group_a)))
        self._calendar_rows(self.teacher_b, ((11, 12, self.group_a | self.group_b),))
        self._calendar_rows(self.teacher_c, ((8, 9, self.group_b),))
        self._absence(self.teacher_a, self.day, hour_from=8, hour_to=9)

        self.assertFalse([step for plan in self._plans() for step in plan['steps'] if step['kind'] == 'move'],
                         "group_b has a lesson at 8: moving the shared one there would change its day")

        self._absence(self.teacher_c, self.day, hour_from=8, hour_to=9)

        # Both groups have the gap now. Best of all, the absent teachers, back at 11, teach their
        # own 8:00 lessons then.
        self.assertEqual(self._plan_summary(self._plans()[0]), [
            ('move', self.teacher_b, 11, 8, self.group_a | self.group_b),
            ('move', self.teacher_a, 8, 11, self.group_a),
            ('move', self.teacher_c, 8, 11, self.group_b),
        ])

    # Co-teaching (issue #678): the teachers who give a lesson together are a pack. Moving or
    # swapping it takes all of them; one who cannot follow it stays on guard while it is gone.

    def _co_taught_last_lesson(self, *rows):
        """_morning, with teacher_c co-teaching teacher_b's 11:00 lesson (same subject and room),
        plus `rows` of teacher_c's own (see _calendar_rows)."""
        self._morning()
        self._calendar_rows(self.teacher_c, ((11, 12, self.group_a), *rows))

    def _cell(self, hour_from, hour_to):
        return next(cell for cell in self._teaching_line(self.day, hour_from, hour_to)['cells'] if cell['group'] == self.group_a)

    def test_a_co_taught_lesson_moves_with_all_its_teachers(self):
        self._co_taught_last_lesson()
        self._absence(self.teacher_a, self.day, hour_from=10, hour_to=12)
        both = self.teacher_b | self.teacher_c

        plan = self._plans()[0]

        self.assertEqual(self._plan_summary(plan), [
            ('move', both, 11, 10, self.group_a), ('notice', ('early_leave', 11), self.group_a)])
        self.assertFalse(plan['steps'][0]['stays'])
        label = self.env['ems.course']._arrangement_plan_data(plan)['steps'][0]['label']
        self.assertEqual(label, f"{self.teacher_b.name} and {self.teacher_c.name} move their 11:00 lesson to 10:00 ({self.group_a.name}).")

        covers, notice_action = self._apply(plan)
        self.Notice.browse(notice_action['res_id']).state = 'scheduled'

        self.assertEqual(covers.guard_employee_id, both, "one cover per teacher who moves the lesson")
        message = str(covers.student_notice_id.message)
        self.assertEqual(message.count(f"{self.subject.name}: from 11:00-12:00 to 10:00-11:00"), 1,
                         "the students are told about the lesson once, not once per teacher")
        self.assertEqual(covers[0]._arrangement_label(),
                         f"{self.teacher_b.name} and {self.teacher_c.name} move their 11:00 lesson to 10:00.")
        self.assertEqual(self._cell(10, 11)['substitutes'], both)
        self.assertEqual(self._cell(11, 12)['moved'], both, "nobody stays behind at 11")
        self.assertFalse(self._teaching_line(self.day, 11, 12)['absences'], "the group has already left")
        for teacher in both:
            self.assertEqual(len(self._messages(teacher, 'Timetable arrangement')), 1)

        self.Cover.with_user(self.department_chief).board_release(covers[0].id)

        self.assertEqual(set(covers.mapped('state')), {'released'}, "the pack is one decision")

    def test_an_absent_co_teacher_does_not_hold_the_lesson_back(self):
        self._co_taught_last_lesson()
        self._absence(self.teacher_a, self.day, hour_from=10, hour_to=12)
        self._absence(self.teacher_c, self.day)

        plan = self._plans()[0]

        self.assertEqual(self._plan_summary(plan)[0], ('move', self.teacher_b, 11, 10, self.group_a))
        self.assertFalse(plan['steps'][0]['stays'], "away anyway: nobody is left on guard")

    def test_a_co_teacher_who_cannot_follow_the_lesson_stays_on_guard(self):
        # teacher_c teaches group_b at 10: they cannot bring the 11:00 lesson forward.
        self._co_taught_last_lesson((10, 11, self.group_b))
        self._absence(self.teacher_a, self.day, hour_from=10, hour_to=12)

        plan = self._plans()[0]

        self.assertEqual(self._plan_summary(plan)[0], ('move', self.teacher_b, 11, 10, self.group_a),
                         "better than losing the 10:00 lesson")
        self.assertEqual(plan['steps'][0]['stays'], self.teacher_c)
        self.assertEqual(self.env['ems.course']._arrangement_plan_data(plan)['steps'][0]['warnings'], [
            f"{self.teacher_c.name} cannot follow the lesson (busy then): on guard at 11:00 instead."])

        covers, _notice_action = self._apply(plan, keep=[0])

        self.assertEqual((covers.guard_employee_id, covers.stayed_employee_ids), (self.teacher_b, self.teacher_c))
        self.assertIn(f"On guard at 11:00 instead: {self.teacher_c.name}.", covers._arrangement_label())
        self.assertTrue(self._messages(self.teacher_c, 'Timetable arrangement'), "they are told too")
        self.assertEqual(self._cell(11, 12)['moved'], self.teacher_b | self.teacher_c)
        self.assertEqual(self._teaching_line(self.day, 11, 12)['stayed_guards'], self.teacher_c)
        data = self.env.company.current_course_id.with_user(self.department_chief).get_guard_duty_board_data(
            '0', 'morning', day=str(self.day))
        guard = next(guard for line in data['lines'] if line['hour_from'] == 11
                     for guard in line['guards'] if guard['id'] == self.teacher_c.id)
        self.assertEqual(guard['stayed'], 'lesson moved')
        self.assertIn(self.teacher_c, self.env['ems.course']._get_guard_candidates(self.day, 11, 12))
        self.assertNotIn(self.teacher_c, self.env['ems.course']._get_guard_candidates(self.day, 10, 11))

        # Without the notice the group is still in at 11, with nobody: teacher_c can stay with it.
        guard_cover = self.Cover.browse(self.Cover.with_user(self.department_chief).board_assign(
            str(self.day), 11, 12, self.teacher_b.id, self.group_a.id, self.teacher_c.id, 'Stay with them'))
        self.assertEqual(self._row(11, 12, teacher=self.teacher_b)['covers'], guard_cover)

        self.Cover.with_user(self.department_chief).board_release(covers.id)

        self.assertEqual(guard_cover.state, 'released', "back at their own lesson, which is there again")
        self.assertNotIn(self.teacher_c, self.env['ems.course']._get_guard_candidates(self.day, 11, 12))

    def test_a_whole_pack_comes_before_one_left_on_guard(self):
        """teacher_c is on guard at 10 (a regular guard does not hold anybody back): the whole pack
        can move, and that is the proposal, with nobody left behind."""
        self._co_taught_last_lesson((10, 11, 'guard'))
        self._absence(self.teacher_a, self.day, hour_from=10, hour_to=12)

        steps = self._plans()[0]['steps']

        self.assertEqual((steps[0]['teacher'], steps[0]['stays']), (self.teacher_b | self.teacher_c, self.env['hr.employee']))

    def test_a_co_taught_lesson_is_swapped_with_all_its_teachers(self):
        self._co_taught_last_lesson()
        self._absence(self.teacher_a, self.day, hour_from=8, hour_to=9)
        both = self.teacher_b | self.teacher_c

        plan = self._plans()[0]

        self.assertEqual(self._plan_summary(plan), [('swap', both, 11, 8, self.group_a)])
        covers, _notice_action = self._apply(plan)

        self.assertEqual(covers.guard_employee_id, both)
        self.assertIn(self._row()['arrangement'], covers)
        self.assertEqual((self._cell(11, 12)['substitutes'], self._cell(11, 12)['moved']), (self.teacher_a, both))
        self.assertEqual(self._cell(8, 9)['substitutes'], both)

        self.Cover.with_user(self.department_chief).board_release(covers[0].id)

        self.assertEqual(set(covers.mapped('state')), {'released'})

    def test_a_swap_needs_every_absent_teacher_at_the_other_lesson(self):
        """teacher_c co-teaches teacher_a's 8:00 lesson: both away then, both teach at 11 instead,
        and no swap once one of them cannot."""
        self._morning()
        self._calendar_rows(self.teacher_c, ((8, 9, self.group_a),))
        self._absence(self.teacher_a, self.day, hour_from=8, hour_to=9)
        self._absence(self.teacher_c, self.day, hour_from=8, hour_to=9)

        swaps = [step for plan in self._plans() for step in plan['steps'] if step['kind'] == 'swap']
        self.assertEqual(swaps[0]['absent'], self.teacher_a | self.teacher_c)

        self._absence(self.teacher_c, self.day, hour_from=11, hour_to=12)

        self.assertFalse([step for plan in self._plans() for step in plan['steps'] if step['kind'] == 'swap'])

    def test_only_a_detected_arrangement_can_be_applied(self):
        self._morning()
        self._absence(self.teacher_a, self.day, hour_from=8, hour_to=9)

        with self.assertRaises(UserError):
            self._arrange('swap', self.teacher_guard, lesson=(9.0, 10.0))
        with self.assertRaises(UserError):
            self._arrange('swap', self.teacher_b, lesson=(9.0, 10.0))
        with self.assertRaises(UserError):
            self._arrange('move', self.teacher_b, lesson=(11.0, 12.0))
        with self.assertRaises(AccessError):
            self._arrange('swap', self.teacher_b, lesson=(11.0, 12.0), user=self.other_department_chief)

    def test_a_manual_arrangement_is_on_record(self):
        self._morning()
        self._schedule_class(self.teacher_c, self.group_b, 'TABC Calendar C (group B)', periods=((8, 9),))
        self._absence(self.teacher_a, self.day, hour_from=8, hour_to=9)

        with self.assertRaises(UserError):
            self._arrange('manual', note='  ')
        candidates = self.env['ems.course'].with_user(self.department_chief).get_arrangement_candidates(
            str(self.day), 8, 9, self.teacher_a.id, self.group_a.id)
        self.assertIn(self.teacher_c.id, [candidate['id'] for candidate in candidates],
                      "a teacher with a class can still join both groups")
        cover, _notice_action = self._arrange('manual', self.teacher_c, note='Groups A and B joined')

        self.assertTrue(cover.is_effective)
        self.assertIn('Groups A and B joined', cover._arrangement_label())
        self.assertTrue(self._messages(self.teacher_c, 'Timetable arrangement'))
        self.assertFalse(self._row()['arrangement_plans'], "a resolved class offers nothing")

    def test_an_arrangement_replaces_a_guard_and_a_guard_replaces_it(self):
        self._morning()
        self._absence(self.teacher_a, self.day, hour_from=8, hour_to=9)
        guard_cover = self.Cover.browse(self._assign())

        arrangement, _notice_action = self._arrange('swap', self.teacher_b, lesson=(11.0, 12.0))

        self.assertEqual(guard_cover.state, 'released')
        self.assertIn('no longer need', self._guard_messages(self.teacher_guard)[0].body)
        self._assign(guard=self.teacher_guard_2)
        self.assertEqual(arrangement.state, 'released')
        self.assertTrue(self._messages(self.teacher_b, 'Arrangement cancelled'))
        self.assertEqual(self._row()['covers'].guard_employee_id, self.teacher_guard_2)

    def test_an_arrangement_no_longer_valid_is_offered_for_removal(self):
        self._morning()
        self._absence(self.teacher_a, self.day, hour_from=8, hour_to=9)
        cover, _notice_action = self._arrange('swap', self.teacher_b, lesson=(11.0, 12.0))

        # The absent teacher is now away at 11 too: they cannot take over that lesson.
        self._absence(self.teacher_a, self.day, hour_from=11, hour_to=12)

        self.assertIn(cover, [action['cover'] for action in self._actions() if action['type'] == 'obsolete_cover'])
        self.Cover.with_user(self.department_chief).board_release(cover.id)
        self.assertEqual(cover.state, 'released')

    def test_arrangements_are_offered_only_to_whoever_organises_the_absence(self):
        self._morning()
        self._absence(self.teacher_a, self.day, hour_from=8, hour_to=9)

        self.assertFalse(self._board_row(self.guard_user)['arrangement_plans'])
        plans = self._board_row(self.department_chief)['arrangement_plans']
        self.assertEqual(len(plans), 2, [[step['label'] for step in plan['steps']] for plan in plans])
        self.assertEqual(plans[0]['title'], 'Proposal 1:')
        self.assertIn(f'{self.teacher_b.name} comes in at 08:00 instead of 11:00.', plans[0]['steps'][0]['schedule_changes'])
        data = self.env.company.current_course_id.with_user(self.department_chief).get_guard_duty_board_data(
            '0', 'morning', day=str(self.day))
        actions = [action for action in data['actions'] if action['type'] == 'arrangement_plan']
        self.assertEqual([[step['kind'] for step in action['plan']['steps']] for action in actions],
                         [['swap'], ['move', 'notice']])

    def test_the_pdf_prints_the_arrangement_and_the_busy_teacher(self):
        self._morning()
        self._absence(self.teacher_a, self.day, hour_from=8, hour_to=9)
        self._arrange('swap', self.teacher_b, lesson=(11.0, 12.0))

        html, _content_type = self.env['ir.actions.report'].with_context(
            guard_duty_weekday='0', guard_duty_date=str(self.day), guard_duty_view='table').\
            _render_qweb_html('ems.report_guard_duty_board', [self.env.company.current_course_id.id])

        self.assertIn(b'gdb-absence-row gdb-absence-covered', html)
        self.assertIn(b'Swap:', html)

    # Chains of moved lessons (issue #645), the case that started it: the absent teacher teaches
    # two groups together at the start and near the end of their day; the best plan has the
    # teachers of each group bring their lessons forward and a shared lesson fill the gap they
    # leave, so the groups leave early instead of waiting for a guard in the middle of the day.

    def _calendar_rows(self, teacher, rows):
        """`rows`: (hour_from, hour_to, groups), or a guard duty ('guard', or 'wc' for one that is
        not regular) instead of the groups. A class of group_a (alone or with others) is in its
        room, any other in space_b, so that no two classes share a room at once."""
        duties = {'guard': self.non_teaching_guard, 'wc': self.env.ref('ems.non_teaching_gwc')}
        calendar = self._new_calendar(teacher, f'TABC 645 {teacher.name}')
        calendar.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': hour_from, 'hour_to': hour_to, 'day_period': 'morning',
            **({'non_teaching': duties[groups].id, 'name': 'Guard'} if isinstance(groups, str)
               else {'subject_id': self.subject.id, 'group_ids': groups.ids, 'name': 'TGDB',
                     'space_id': (self.space if self.group_a in groups else self.space_b).id}),
        } for hour_from, hour_to, groups in rows])

    def _two_groups_day(self):
        """group_a and group_b's Monday. teacher_a, away all day, teaches both together at 8 and 12;
        teacher_b (group_a) and teacher_c (group_b) are on guard at 8 and teach their group 9-11;
        teacher_guard_2 is on WC duty at 8 and teaches both at 11; teacher_guard is on WC duty at 8,
        on guard 10-11 and 12-13 and teaches both groups at 13. Without arrangements: they come in at 9, and a guard
        stays with each group at 12."""
        both = self.group_a | self.group_b
        self._calendar_rows(self.teacher_a, ((8, 9, both), (12, 13, both)))
        self._calendar_rows(self.teacher_b, ((8, 9, 'guard'), (9, 10, self.group_a), (10, 11, self.group_a)))
        self._calendar_rows(self.teacher_c, ((8, 9, 'guard'), (9, 10, self.group_b), (10, 11, self.group_b)))
        self._calendar_rows(self.teacher_guard_2, ((8, 9, 'wc'), (11, 12, both)))
        self._calendar_rows(self.teacher_guard, ((8, 9, 'wc'), (10, 11, 'guard'), (12, 13, 'guard'), (13, 14, both)))
        self._absence(self.teacher_a, self.day)
        return both

    def _split_groups_day(self, halves=True):
        """group_a and group_b as the two halves of a split group (issue #660). Monday: teacher_b
        teaches both the same subject, group_a at 9 and group_b at 12, its last lesson; teacher_a,
        away all day, has group_b at 9, in the middle of its day, and group_a at 12, its last one;
        teacher_c (group_b at 8, a WC duty at 9, group_a 10-12) and teacher_guard (group_b 10-12)
        fill the rest. Their forms say they are halves of the same group (issue #676); they also
        share a lesson on Tuesday, which alone does not make them halves.
        Without arrangements group_b needs a guard at 9; joining it to group_a's lesson with
        teacher_b frees its 12:00 lesson, and both halves leave at 12."""
        self._calendar_rows(self.teacher_a, ((9, 10, self.group_b), (12, 13, self.group_a)))
        self._calendar_rows(self.teacher_b, ((9, 10, self.group_a), (12, 13, self.group_b)))
        self._calendar_rows(self.teacher_c, ((8, 9, self.group_b), (9, 10, 'wc'), (10, 11, self.group_a), (11, 12, self.group_a)))
        self._calendar_rows(self.teacher_guard, ((10, 11, self.group_b), (11, 12, self.group_b)))
        self._new_calendar(self.teacher_guard_2, 'TABC 660 Tuesday').apply_schedule_changes([{
            'dayofweek': '1', 'hour_from': 8, 'hour_to': 9, 'day_period': 'morning', 'subject_id': self.subject.id,
            'group_ids': (self.group_a | self.group_b).ids, 'name': 'TGDB', 'space_id': self.space.id,
        }])
        if halves:
            self.group_a.joinable_group_ids = self.group_b
        self._absence(self.teacher_a, self.day)

    def _join_plan(self):
        self._split_groups_day()
        expected = [('join', self.teacher_b, 12, 9, self.group_b), ('notice', ('early_leave', 12), self.group_a | self.group_b)]
        plans = [plan for plan in self._plans(self.group_b) if self._plan_summary(plan) == expected]
        self.assertTrue(plans, "group_b joins group_a's lesson with teacher_b at 9, and both halves leave at 12")
        return plans[0]

    def test_the_two_halves_of_a_split_group_can_be_joined(self):
        plan = self._join_plan()

        self.assertEqual(plan['steps'][0]['joined'], self.group_a)
        self.assertEqual(plan['steps'][0]['shifts'], [(self.teacher_b, 'exit', 13, 10)], "teacher_b leaves at 10")
        self.assertEqual(self._plans(self.group_a), self._plans(self.group_b), "one set of plans for both halves")
        label = self.env['ems.course']._arrangement_plan_data(plan)['steps'][0]['label']
        self.assertIn(f"together with {self.group_a.name} at 09:00, instead of at 12:00", label)

    def test_groups_sharing_a_lesson_are_not_joined_unless_set_as_halves(self):
        """Issue #676: DAM2A and DAM2B share lessons without being halves of a split group."""
        self._split_groups_day(halves=False)

        self.assertFalse([step for plan in self._plans(self.group_b) for step in plan['steps']
                          if step['kind'] == 'join' and step['teacher'] == self.teacher_b])

    def test_only_the_same_subject_is_joined(self):
        other = self.env['ems.subject'].create({'code': 'TABC660', 'acronym': 'T660', 'name': 'TABC 660 Other subject',
                                                'study_ids': [(6, 0, [self.study.id])]})
        self._split_groups_day()
        self.env['resource.calendar.attendance'].search([
            ('calendar_id.employee_id', '=', self.teacher_b.id), ('hour_from', '=', 12)]).subject_id = other

        self.assertFalse([step for plan in self._plans(self.group_b) for step in plan['steps']
                          if step['kind'] == 'join' and step['teacher'] == self.teacher_b])

    def test_applying_a_join_needs_no_guard_and_tells_both_halves(self):
        covers, _notice_action = self._apply(self._join_plan())

        join = covers.filtered('joined_group_ids')
        self.assertEqual((join.group_id, join.absent_employee_id, join.guard_employee_id, join.hour_from, join.vacated_hour_from),
                         (self.group_b, self.teacher_a, self.teacher_b, 9, 12))
        self.assertEqual((join.arrangement_type, join.joined_group_ids, join.space_id), ('move', self.group_a, self.space),
                         "a move into group_a's lesson, in group_a's room")
        self.assertIn(f"together with {self.group_a.name} at 09:00, instead of at 12:00", join._arrangement_label())
        notices = self.Notice.search([('absence_group_id', 'in', (self.group_a | self.group_b).ids)])
        self.assertEqual({(notice.absence_group_id, tuple(notice._absence_change_tuples())) for notice in notices},
                         {(self.group_a, (('early_leave', 12.0),)), (self.group_b, (('early_leave', 12.0),))})
        self.assertEqual(join.notice_id.absence_group_id, self.group_b, "the join waits for group_b's notice")
        students = join.student_notice_id
        self.assertIn(f"together with {self.group_a.name} in {self.space.display_name}", students.message)

        notices.write({'state': 'scheduled'})

        self.assertTrue(join.is_effective)
        for group, other in ((self.group_a, self.group_b), (self.group_b, self.group_a)):
            cell = next(cell for cell in self._teaching_line(self.day, 9, 10)['cells'] if cell['group'] == group)
            self.assertEqual(cell['joined'], other, f"{group.name} at 9 shows it is taught with {other.name}")
        self.assertFalse([row for row in self._teaching_line(self.day, 9, 10)['absences'] if not (row['arrangement'] or row['authorized'])],
                         "nobody needs a guard at 9")
        message = self._messages(self.teacher_b, 'Timetable arrangement')
        self.assertIn(f"together with {self.group_a.name}", message.body)

    def test_a_join_is_withdrawn_like_a_moved_lesson(self):
        covers, _notice_action = self._apply(self._join_plan())
        join = covers.filtered('joined_group_ids')
        self.Notice.search([('absence_group_id', 'in', (self.group_a | self.group_b).ids)]).write({'state': 'scheduled'})

        self.Cover.with_user(self.department_chief).board_release(join.id)

        self.assertEqual(join.state, 'released')
        self.assertTrue(self._messages(self.teacher_b, 'Arrangement cancelled'))
        cell = next(cell for cell in self._teaching_line(self.day, 9, 10)['cells'] if cell['group'] == self.group_a)
        self.assertFalse(cell['joined'])

    def _co_taught_join_plan(self, with_other_half):
        """_split_groups_day, with teacher_guard_wc co-teaching group_b's 12:00 lesson with
        teacher_b (issue #678) and, `with_other_half`, group_a's 9:00 one too: the plan joining
        group_b to group_a at 9."""
        self._split_groups_day()
        self._calendar_rows(self.teacher_guard_wc, ((12, 13, self.group_b),) + (((9, 10, self.group_a),) if with_other_half else ()))
        return next(plan for plan in self._plans(self.group_b) if plan['steps'][0]['kind'] == 'join')

    def test_a_co_taught_lesson_joins_the_other_half_with_all_its_teachers(self):
        both = self.teacher_b | self.teacher_guard_wc
        plan = self._co_taught_join_plan(with_other_half=True)

        self.assertEqual(self._plan_summary(plan)[0], ('join', both, 12, 9, self.group_b))
        self.assertFalse(plan['steps'][0]['stays'])

        covers, _notice_action = self._apply(plan)

        join = covers.filtered('joined_group_ids')
        self.assertEqual(join.guard_employee_id, both, "one cover per teacher who brings the lesson")
        self.assertFalse(join.stayed_employee_ids)
        self.assertIn(f"teach the group together with {self.group_a.name} at 09:00, instead of at 12:00",
                      join[0]._arrangement_label())

    def test_a_co_teacher_not_with_the_other_half_stays_on_guard_in_a_join(self):
        plan = self._co_taught_join_plan(with_other_half=False)

        self.assertEqual(self._plan_summary(plan)[0], ('join', self.teacher_b, 12, 9, self.group_b))
        self.assertEqual(plan['steps'][0]['stays'], self.teacher_guard_wc)
        self.assertEqual(self.env['ems.course']._arrangement_plan_data(plan)['steps'][0]['warnings'], [
            f"{self.teacher_guard_wc.name} cannot follow the lesson (not with the other half then): on guard at 12:00 instead."])

        covers, _notice_action = self._apply(plan, keep=[0])

        self.assertEqual((covers.guard_employee_id, covers.stayed_employee_ids, covers.joined_group_ids),
                         (self.teacher_b, self.teacher_guard_wc, self.group_a))
        self.assertIn(f"On guard at 12:00 instead: {self.teacher_guard_wc.name}.", covers._arrangement_label())

    def test_a_chain_of_moved_lessons_frees_the_end_of_the_day(self):
        both = self._two_groups_day()

        plans = self._plans()

        self.assertEqual(self._plan_summary(plans[0]), [
            ('move', self.teacher_b, 10, 8, self.group_a),
            ('move', self.teacher_c, 10, 8, self.group_b),
            ('move', self.teacher_guard, 13, 10, both),
            ('notice', ('early_leave', 12), both),
        ], "two hours in a row of the same subject are kept together, and the groups leave at 12")
        self.assertEqual([step['depends'] for step in plans[0]['steps']], [[], [], [0, 1], [2]])
        self.assertEqual(plans[0]['steps'][2]['shifts'], [(self.teacher_guard, 'exit', 14, 13)])
        self.assertEqual(plans[0]['steps'][0]['shifts'], [(self.teacher_b, 'exit', 11, 10)])
        self.assertEqual(self._plans(self.group_b), plans, "one set of plans for both groups")

    def test_applying_the_whole_chain_needs_no_guard_and_one_notice_per_group(self):
        both = self._two_groups_day()

        covers, notice_action = self._apply(self._plans()[0])

        self.assertEqual(sorted((cover.group_id.name, cover.hour_from, cover.guard_employee_id.name, cover.absent_employee_id.name)
                                for cover in covers), sorted([
            (self.group_a.name, 8, self.teacher_b.name, self.teacher_a.name),
            (self.group_b.name, 8, self.teacher_c.name, self.teacher_a.name),
            (self.group_a.name, 10, self.teacher_guard.name, self.teacher_b.name),
            (self.group_b.name, 10, self.teacher_guard.name, self.teacher_c.name),
        ]))
        notices = covers.notice_id
        self.assertEqual(sorted(notices.absence_group_id.ids), sorted(both.ids))
        # No students in these groups: the notices cannot be sent (issue #652) and stay drafts.
        self.assertEqual({(tuple(notice._absence_change_tuples()), notice.state) for notice in notices},
                         {((('early_leave', 12.0),), 'draft')})
        self.assertIn(notice_action['res_id'], notices.ids)
        self.assertEqual(covers.filtered('notice_id').guard_employee_id, self.teacher_guard,
                         "only the move whose lesson the notice frees the groups from waits for it")
        self.assertFalse(self._messages(self.teacher_guard, 'Timetable arrangement'), "not before the notice")

        notices.write({'state': 'scheduled'})

        self.assertTrue(all(covers.mapped('is_effective')))
        for group in both:
            for hour_from in (8, 10, 12):
                line = self._teaching_line(self.day, hour_from, hour_from + 1)
                for row in line['absences']:
                    if row['group'] == group:
                        self.assertTrue(row['arrangement'] or row['authorized'], f"{group.name} at {hour_from} needs nobody")
            self.assertFalse([row for row in self._teaching_line(self.day, 13, 14)['absences'] if row['group'] == group])

    def test_all_but_the_notice_leaves_the_last_gap_as_a_row_and_a_proposal(self):
        self._two_groups_day()

        covers, notice_action = self._apply(self._plans()[0], keep=[0, 1, 2])

        self.assertFalse(self.Notice.browse(notice_action['res_id']).absence_changes, "only the students' notice")
        self.assertTrue(all(covers.mapped('is_effective')) and not covers.notice_id)
        self.assertEqual(len(self._messages(self.teacher_guard, 'Timetable arrangement')), 1,
                         "one message for a lesson moved for both groups")
        rows = [row for row in self._teaching_line(self.day, 13, 14)['absences'] if row['teacher'] == self.teacher_guard]
        self.assertEqual(sorted(row['group'].name for row in rows), sorted([self.group_a.name, self.group_b.name]))
        self.assertTrue(all(row['state'] == 'moved' and not row['covers'] for row in rows))
        proposals = [(action['group'], action['expected']) for action in self._actions() if action['type'] == 'proposal']
        self.assertIn((self.group_a, ('early_leave', 12)), proposals)
        self.assertIn((self.group_b, ('early_leave', 12)), proposals)

    def test_a_step_is_never_applied_without_those_it_needs(self):
        self._two_groups_day()
        plan = self._plans()[0]

        with self.assertRaises(UserError):
            self._apply(plan, keep=[2, 3])
        with self.assertRaises(UserError):
            self._apply(plan, keep=[0, 1, 3])

        covers, _notice_action = self._apply(plan, keep=[0])
        self.assertEqual(covers.guard_employee_id, self.teacher_b, "a step needed by nothing can be kept alone")

    def test_a_plan_no_longer_possible_is_refused(self):
        self._two_groups_day()
        plan = self._plans()[0]
        self._absence(self.teacher_guard, self.day, hour_from=10, hour_to=11)

        with self.assertRaises(UserError):
            self._apply(plan)
        self.assertFalse(self.Cover.search([('date', '=', self.day)]), "nothing is applied half way")

    def test_only_whoever_organises_the_absence_applies_a_plan(self):
        self._two_groups_day()

        with self.assertRaises(AccessError):
            self._apply(self._plans()[0], user=self.other_department_chief)

    def test_a_shared_lesson_moved_for_several_groups_is_withdrawn_from_all_of_them(self):
        self._two_groups_day()
        covers, _notice_action = self._apply(self._plans()[0], keep=[0, 1, 2])
        shared = covers.filtered(lambda cover: cover.guard_employee_id == self.teacher_guard)

        self.Cover.with_user(self.department_chief).board_release(shared[0].id)

        self.assertEqual(set(shared.mapped('state')), {'released'})
        self.assertEqual(set((covers - shared).mapped('state')), {'assigned'})
        obsolete = [action['cover'] for action in self._actions() if action['type'] == 'obsolete_cover']
        self.assertFalse(obsolete, "the gaps the other moves left are classes to cover again, not stale covers")
        self.assertEqual(self._row(10, 11, teacher=self.teacher_b)['state'], 'moved')

    def test_the_board_offers_a_chain_once_and_shows_it_on_every_row_it_solves(self):
        self._two_groups_day()

        data = self.env.company.current_course_id.with_user(self.department_chief).get_guard_duty_board_data(
            '0', 'morning', day=str(self.day))

        actions = [action for action in data['actions'] if action['type'] == 'arrangement_plan']
        self.assertEqual([action['plan']['title'] for action in actions][:2], ['Proposal 1:', 'Proposal 2:'])
        # One section for both groups: their plans and the change alone (coming in at 9) together.
        sections = {(action['type'], action['section_title']) for action in data['actions']}
        title = f"{self.group_a.name} and {self.group_b.name}"
        self.assertEqual(sections, {('arrangement_plan', title), ('proposal', title)})
        first = actions[0]['plan']
        self.assertEqual(first['steps'][3]['label'],
                         f"Notice to the families of {self.group_a.name} and {self.group_b.name}: Leaves at 12:00.")
        self.assertEqual(first['steps'][2]['schedule_changes'], [f'{self.teacher_guard.name} leaves at 13:00 instead of 14:00.'])
        for line in data['lines']:
            for absence in line['absences']:
                if absence['teacher_id'] == self.teacher_a.id:
                    self.assertIn(first['key'], [plan['key'] for plan in absence['arrangement_plans']])

    # The students' notice about the lessons an arrangement moves (issue #649): a draft per group
    # and day, students only, never waited for by the arrangement.

    def _student_and_family(self):
        """A student of group_a, with a family that the families' notices reach."""
        student = self.env['res.partner'].create({
            'name': 'TABC 649 Student', 'contact_type': 'student', 'student_id': next_student_id(),
            'main_group_id': self.group_a.id, 'email': 'tabc649.student@example.com'})
        family = self.env['res.partner'].create({
            'name': 'TABC 649 Family', 'contact_type': 'family', 'email': 'tabc649.family@example.com'})
        self.env['res.partner.relation'].create({
            'left_partner_id': family.id, 'type_id': self.env.ref('ems.relation_type_father').id,
            'right_partner_id': student.id})
        return student, family

    def _students_drafts(self, group=None):
        return self.Notice.search([('arrangement_group_id', '=', (group or self.group_a).id),
                                   ('arrangement_date', '=', self.day), ('state', '=', 'draft')])

    def test_a_swap_sends_a_notice_to_the_students_only(self):
        student, family = self._student_and_family()
        self.department_chief.email = 'tabc649.chief@example.com'
        self._morning()
        self._absence(self.teacher_a, self.day, hour_from=8, hour_to=9)

        cover, notice_action = self._apply(self._plans()[0])

        self.assertFalse(notice_action, "sent at once (issue #652): no draft to open")
        notice = cover.student_notice_id
        self.assertEqual(cover.arrangement_type, 'swap')
        self.assertEqual((notice.state, notice.recipient_type, notice.group_ids), ('scheduled', 'students', self.group_a))
        self.assertEqual((notice.arrangement_group_id, notice.arrangement_date), (self.group_a, self.day))
        self.assertEqual(notice.notice_line_ids.partner_id, student)
        self.assertNotIn(family.email, notice.notice_line_ids.mapped('email'))
        self.assertIn('Dear students,', notice.message)
        # Both subjects change time: teacher_b's 11:00 lesson goes to 8:00 and teacher_a's back to 11:00.
        self.assertIn(f'{self.subject.name}: from 11:00-12:00 to 08:00-09:00', notice.message)
        self.assertIn(f'{self.subject.name}: from 08:00-09:00 to 11:00-12:00', notice.message)
        self.assertTrue(cover.is_effective, "the arrangement does not wait for the students' notice")
        self.assertTrue(self._messages(self.teacher_b, 'Timetable arrangement'))
        self.assertEqual(self.Notice.search([('arrangement_group_id', '=', self.group_a.id), ('arrangement_date', '=', self.day)]),
                         notice, "one notice, however many times the group's day is synced")
        with self.assertRaises(ValidationError):
            notice.recipient_type = 'both'

    def test_a_moved_lesson_opens_the_families_notice_first_and_drafts_the_students_one(self):
        cover, notice_action = self._apply(self._moved_lesson_plan())

        families = self.Notice.browse(notice_action['res_id'])
        students = cover.student_notice_id
        self.assertEqual(families._absence_change_tuples(), [('early_leave', 11.0)])
        self.assertEqual((students.state, students.recipient_type), ('draft', 'students'))
        self.assertIn(f'{self.subject.name}: from 11:00-12:00 to 10:00-11:00', students.message,
                      "the families' notice only says when the group leaves, not that a subject moved")

        families.state = 'scheduled'

        self.assertTrue(cover.is_effective, "only the families' notice is waited for")
        self.assertEqual(students.state, 'draft')

    def test_one_students_notice_per_group_and_day_kept_up_to_date(self):
        self._two_groups_day()
        covers, _notice_action = self._apply(self._plans()[0], keep=[0, 1, 2])
        notice_a, notice_b = self._students_drafts(), self._students_drafts(self.group_b)

        self.assertEqual((len(notice_a), len(notice_b)), (1, 1), "one draft per group, however many moves")
        self.assertEqual(covers.filtered(lambda cover: cover.group_id == self.group_a).student_notice_id, notice_a)
        for text in ('from 10:00-11:00 to 08:00-09:00', 'from 13:00-14:00 to 10:00-11:00'):
            self.assertIn(text, notice_a.message)
        self.assertIn('from 13:00-14:00 to 10:00-11:00', notice_b.message, "a shared lesson moved for both groups")

        shared = covers.filtered(lambda cover: cover.guard_employee_id == self.teacher_guard)
        self.Cover.with_user(self.department_chief).board_release(shared[0].id)

        self.assertEqual(self._students_drafts(), notice_a, "the same draft, updated")
        self.assertIn('from 10:00-11:00 to 08:00-09:00', notice_a.message)
        self.assertNotIn('13:00-14:00', notice_a.message)
        self.assertNotIn('13:00-14:00', notice_b.message)

        move_b = covers.filtered(lambda cover: cover.guard_employee_id == self.teacher_b)
        self.Cover.with_user(self.department_chief).board_release(move_b.id)

        self.assertFalse(notice_a.exists(), "nothing left to tell group_a's students")
        self.assertEqual(self._students_drafts(self.group_b), notice_b)

    def test_a_withdrawn_arrangement_after_the_students_notice_was_sent_proposes_a_correction(self):
        self._morning()
        self._absence(self.teacher_a, self.day, hour_from=8, hour_to=9)
        cover, notice_action = self._arrange('swap', self.teacher_b, lesson=(11.0, 12.0))
        sent = self.Notice.browse(notice_action['res_id'])
        sent.state = 'sent'

        self.Cover.with_user(self.department_chief).board_release(cover.id)

        correction = self._students_drafts()
        self.assertEqual(len(correction), 1)
        self.assertTrue(correction.subject.startswith('Correction:'))
        self.assertIn('will be at their usual time', correction.message)
        self.assertIn(f'{self.subject.name}: 11:00-12:00', correction.message)
        self.assertIn(f'{self.subject.name}: 08:00-09:00', correction.message)
        self.assertEqual(sent.state, 'sent', "a sent notice is never touched")

        again, _notice_action = self._arrange('swap', self.teacher_b, lesson=(11.0, 12.0))

        self.assertFalse(correction.exists(), "back to what the students were told: nothing to correct")
        self.assertEqual(again.student_notice_id, sent)

    def test_a_changed_arrangement_after_the_students_notice_was_sent_lists_the_lessons_as_they_are_now(self):
        self._two_groups_day()
        covers, _notice_action = self._apply(self._plans()[0], keep=[0, 1, 2])
        self._students_drafts().state = 'sent'
        shared = covers.filtered(lambda cover: cover.guard_employee_id == self.teacher_guard)

        self.Cover.with_user(self.department_chief).board_release(shared[0].id)

        correction = self._students_drafts()
        self.assertTrue(correction.subject.startswith('Correction:'))
        self.assertIn('from 10:00-11:00 to 08:00-09:00', correction.message, "what still changes is repeated")
        self.assertIn(f'{self.subject.name}: 13:00-14:00', correction.message, "the lesson back at its usual time")

    def test_a_department_chief_sends_the_students_notice_of_their_group_with_the_swap(self):
        student, _family = self._student_and_family()
        self.department_chief.email = 'tabc649.chief@example.com'
        self._morning()
        self._absence(self.teacher_a, self.day, hour_from=8, hour_to=9)

        cover, notice_action = self._arrange('swap', self.teacher_b, lesson=(11.0, 12.0))

        self.assertFalse(notice_action, "a swap from the board sends it at once too (issue #652)")
        notice = cover.student_notice_id.with_user(self.department_chief)
        self.assertEqual(notice.create_uid, self.department_chief)
        self.assertEqual(notice.sent_by, self.department_chief)
        self.assertFalse(self.Notice.with_user(self.other_department_chief).search([('id', '=', notice.id)]),
                         "another department's chief does not see it")
        self.assertEqual(notice.state, 'scheduled')
        self.assertEqual(notice.notice_line_ids.partner_id, student)
        with self.assertRaises(ValidationError):
            notice.group_ids = self.group_a | self.group_b

    # One notice per group, sent as soon as the plan is accepted (issue #652).

    def _can_send(self):
        """A student with a family to send to, and a sender address, which every real user has."""
        self._student_and_family()
        self.department_chief.email = 'tabc652.chief@example.com'

    def test_accepting_a_plan_sends_its_notice_and_the_move_counts_at_once(self):
        self._can_send()

        cover, notice_action = self._apply(self._moved_lesson_plan())

        self.assertFalse(notice_action, "nothing to open: keeping the step was the confirmation")
        notice = cover.notice_id
        self.assertEqual((notice._absence_change_tuples(), notice.state), ([('early_leave', 11.0)], 'scheduled'))
        self.assertEqual(notice.sent_by, self.department_chief)
        self.assertTrue(cover.is_effective)
        self.assertEqual(len(self._messages(self.teacher_b, 'Timetable arrangement')), 1, "told once")
        self.assertEqual(self._states()['leave']['communicated'], ('early_leave', 11))
        self.assertNotIn('pending_arrangement', [action['type'] for action in self._actions()])
        self.assertEqual(cover.student_notice_id.state, 'scheduled', "the students' notice is sent too")

    def _two_sides_day(self):
        """group_a's Monday with its first lesson (teacher_a) and its last one (teacher_b)
        without a teacher: it could come in at 9 and leave at 11."""
        self._morning()
        self._absence(self.teacher_a, self.day, hour_from=8, hour_to=9)
        return self._absence(self.teacher_b, self.day, hour_from=11, hour_to=12, approve=False)

    def _apply_notices(self, *changes):
        result = self.Cover.with_user(self.department_chief).board_apply_plan(str(self.day), [
            {'kind': 'notice', 'group_ids': self.group_a.ids, 'change': list(change)} for change in changes])
        return result

    def _families_notices(self):
        return self.Notice.search([('absence_group_id', '=', self.group_a.id), ('absence_date', '=', self.day)])

    def test_one_notice_tells_every_change_of_the_group(self):
        self._can_send()
        self._two_sides_day()
        proposed = self.Notice.browse(self.Notice.with_user(self.department_chief)._board_absence_change_draft(
            str(self.day), self.group_a.id, 'late_entry', 9.0)._absence_change_form_action()['res_id'])

        result = self._apply_notices(('early_leave', 11.0), ('late_entry', 9.0))

        self.assertFalse(result['notice_action'])
        notice = self._families_notices()
        self.assertEqual(len(notice), 1, "one notice for the whole day")
        self.assertFalse(proposed.exists(), "the draft prepared for one of its changes is replaced by it")
        self.assertEqual(sorted(notice._absence_change_tuples()), [('early_leave', 11.0), ('late_entry', 9.0)])
        self.assertEqual(notice.state, 'scheduled')
        self.assertIn('timetable changes on', notice.subject)
        start = notice.message.index('will start classes at 09:00')
        self.assertLess(start, notice.message.index('will finish classes at 11:00'), "from the start of the day to its end")
        self.assertEqual(notice.absence_change_label, 'Starts at 09:00 and Leaves at 11:00')
        self.assertFalse(self.Notice.with_user(self.other_department_chief).search([('id', '=', notice.id)]),
                         "another department's chief does not see it")
        states = self._states()
        self.assertEqual((states['entry']['status'], states['entry']['communicated']), ('communicated', ('late_entry', 9)))
        self.assertEqual((states['leave']['status'], states['leave']['communicated']), ('communicated', ('early_leave', 11)))
        self.assertEqual(self._row(8, 9)['authorized'], ('late_entry', 9))
        self.assertEqual(self._row(11, 12, teacher=self.teacher_b)['authorized'], ('early_leave', 11))

    def test_a_side_of_a_notice_with_several_changes_is_rectified_alone(self):
        self._can_send()
        leave = self._two_sides_day()
        self._apply_notices(('late_entry', 9.0), ('early_leave', 11.0))

        leave.action_refuse()

        states = self._states()
        self.assertEqual(states['entry']['status'], 'communicated', "the start of the day still holds")
        self.assertEqual((states['leave']['status'], states['leave']['options']), ('rectification', [('normal_leave', 0.0)]))
        correction = self.Notice.browse(self.Notice.with_user(self.department_chief)._board_absence_change_draft(
            str(self.day), self.group_a.id, 'normal_leave')._absence_change_form_action()['res_id'])
        self.assertEqual((correction._absence_change_tuples(), correction.state), ([('normal_leave', 0.0)], 'draft'))
        self.assertTrue(correction.subject.startswith('Correction:'))
        self.assertEqual(self._states()['leave']['draft'], correction)

    def test_a_notice_that_cannot_be_sent_stays_a_draft_to_review(self):
        self._can_send()

        def failing(notice):
            raise UserError("TABC mail server unreachable")

        plan = self._moved_lesson_plan()
        steps = [step['payload'] for step in self.env['ems.course']._arrangement_plan_data(plan)['steps']]
        with patch.object(type(self.Notice), 'action_send', failing):
            result = self.Cover.with_user(self.department_chief).board_apply_plan(str(self.day), steps)

        cover = self.Cover.browse(result['cover_ids'])
        notice = cover.notice_id
        self.assertEqual(result['notice_action']['res_id'], notice.id, "the families' notice opens first")
        self.assertIn('TABC mail server unreachable', result['notice_error'])
        self.assertEqual((notice.state, cover.student_notice_id.state), ('draft', 'draft'))
        self.assertFalse(cover.is_effective, "nothing changes until the families are told")
        self.assertFalse(self._messages(self.teacher_b, 'Timetable arrangement'))
        pending = [action for action in self._actions() if action['type'] == 'pending_arrangement']
        self.assertEqual([action['cover'].notice_id for action in pending], [notice], "the board offers to open it")

        notice.with_user(self.department_chief).action_send()

        self.assertTrue(cover.is_effective)
        self.assertEqual(len(self._messages(self.teacher_b, 'Timetable arrangement')), 1, "told once, when it is sent")

    def test_a_correction_to_the_students_after_a_withdrawal_stays_a_draft(self):
        self._can_send()
        self._morning()
        self._absence(self.teacher_a, self.day, hour_from=8, hour_to=9)
        cover, _notice_action = self._apply(self._plans()[0])
        sent = cover.student_notice_id
        self.assertEqual(sent.state, 'scheduled')

        self.Cover.with_user(self.department_chief).board_release(cover.id)

        correction = self._students_drafts()
        self.assertEqual(len(correction), 1, "nobody accepted anything: it waits to be reviewed")
        self.assertTrue(correction.subject.startswith('Correction:'))
        self.assertEqual(sent.state, 'scheduled')

    # The group's tutor gets a copy of every notice that moves its classes (issue #658).

    def _tutor(self, group=None):
        tutor = create_role_employee(self, create_role_user(self, 'teacher', 'test_tutor_tabc658'),
                                     name='TABC 658 Tutor')
        (group or self.group_a).tutor_id = tutor
        return tutor

    def _tutor_messages(self, tutor):
        return self.env['mail.message'].search([('model', '=', 'ems.notice'), ('partner_ids', 'in', tutor.user_id.partner_id.ids)])

    def test_the_tutor_gets_a_copy_of_the_students_notice(self):
        self._can_send()
        tutor = self._tutor()
        self._morning()
        self._absence(self.teacher_a, self.day, hour_from=8, hour_to=9)

        cover, _notice_action = self._apply(self._plans()[0])

        notice = cover.student_notice_id
        message = self._tutor_messages(tutor)
        self.assertEqual(len(message), 1)
        self.assertEqual(message.res_id, notice.id)
        self.assertIn(notice.subject, message.subject)
        self.assertIn(f'{self.subject.name}: from 11:00-12:00 to 08:00-09:00', message.body)

    def test_the_tutor_gets_a_copy_of_the_families_notice_once_sent(self):
        self._can_send()
        tutor = self._tutor()
        self._two_sides_day()
        draft = self.Notice.with_user(self.department_chief)._board_absence_change_draft(
            str(self.day), self.group_a.id, 'late_entry', 9.0)

        self.assertFalse(self._tutor_messages(tutor), "a draft tells nobody")

        self._apply_notices(('early_leave', 11.0), ('late_entry', 9.0))

        notice = self._families_notices()
        message = self._tutor_messages(tutor)
        self.assertEqual((len(message), message.res_id), (1, notice.id))
        self.assertIn('will finish classes at 11:00', message.body)
        self.assertFalse(draft.exists())

    def test_the_main_groups_tutors_get_a_copy_for_a_reinforcement_group(self):
        tutor_a, tutor_b = self._tutor(), create_role_employee(
            self, create_role_user(self, 'teacher', 'test_tutor_b_tabc658'), name='TABC 658 Tutor B')
        self.group_b.tutor_id = tutor_b
        reinforcement = self.env['ems.group'].create({
            'group_type': 'reinforcement', 'name': 'TABC 658 Reinforcement',
            'parent_group_ids': [(6, 0, (self.group_a | self.group_b).ids)]})
        notice = self.Notice._create_arrangement_notice(reinforcement, self.day, {
            'subject': 'TABC 658 moved lessons', 'message': '<p>TABC 658</p>', 'arrangement_lessons': []})

        notice.state = 'scheduled'

        self.assertEqual(len(self._tutor_messages(tutor_a)), 1)
        self.assertEqual(len(self._tutor_messages(tutor_b)), 1)

    def _send_change(self, change_type, hour=0.0):
        return self.Notice.with_user(self.department_chief).board_send_absence_change(
            str(self.day), self.group_a.id, change_type, hour)

    def test_send_notice_sends_the_change_at_once(self):
        self._can_send()
        self._two_sides_day()

        result = self._send_change('late_entry', 9.0)

        self.assertEqual(result, {'notice_action': False, 'notice_error': False}, "no draft to open")
        notice = self._families_notices()
        self.assertEqual((notice._absence_change_tuples(), notice.state), ([('late_entry', 9.0)], 'scheduled'))
        self.assertEqual(notice.sent_by, self.department_chief)
        self.assertEqual(self._states()['entry']['status'], 'communicated')

    def test_a_correction_with_nothing_allowed_any_more_says_the_usual_timetable(self):
        self._can_send()
        leave = self._two_sides_day()
        self._apply_notices(('early_leave', 11.0))
        leave.action_refuse()

        action = next(action for action in self._actions() if action['type'] == 'rectification')
        label = self.env['ems.course']._board_action_data(action)['label']

        self.assertIn('(now: Usual timetable)', label)
        self.assertNotIn('False', label)

    def test_send_correction_sends_it_at_once_too(self):
        self._can_send()
        leave = self._two_sides_day()
        self._apply_notices(('late_entry', 9.0), ('early_leave', 11.0))
        leave.action_refuse()

        self.assertFalse(self._send_change('normal_leave')['notice_action'])

        correction = self._families_notices().filtered(lambda notice: notice._absence_change_tuples() == [('normal_leave', 0.0)])
        self.assertEqual(correction.state, 'scheduled')
        self.assertTrue(correction.subject.startswith('Correction:'))
        self.assertEqual(self._states()['leave']['status'], None, "back to the usual timetable, nothing left to tell")

    def test_send_notice_that_cannot_be_sent_opens_its_draft(self):
        """The group has no students: there is nobody to send it to."""
        self._two_sides_day()

        result = self._send_change('late_entry', 9.0)

        notice = self._families_notices()
        self.assertEqual(result['notice_action']['res_id'], notice.id)
        self.assertTrue(result['notice_error'])
        self.assertEqual(notice.state, 'draft')
        self.assertEqual(self._states()['entry']['draft'], notice, "the board offers to open it")

    # Partial cover (issue #637): a guard whose duty only overlaps part of a class covers that part.

    def _partial_morning(self):
        """teacher_a, away, teaches group_a 9-10; teacher_guard is on guard 8:30-9:30 and
        teacher_guard_2 9:30-10:30, so each overlaps half of the class."""
        self._schedule_class(self.teacher_a, self.group_a, 'TABC Calendar A (Partial)', periods=((9, 10),))
        self._guards(self.teacher_guard, periods=((8.5, 9.5),))
        self._guards(self.teacher_guard_2, periods=((9.5, 10.5),))
        self._absence(self.teacher_a, self.day)

    def test_a_guard_overlapping_part_of_a_class_covers_that_part(self):
        self._partial_morning()

        candidates = self.env['ems.course']._get_guard_candidates(self.day, 9, 10)
        self.assertEqual(candidates[self.teacher_guard], (9, 9.5))
        self.assertEqual(candidates[self.teacher_guard_2], (9.5, 10))

        cover = self.Cover.browse(self._assign(self.teacher_guard, 9, 10))
        self.assertEqual((cover.hour_from, cover.hour_to), (9, 9.5))
        row = self._row(9, 10)
        self.assertEqual(row['covers'], cover)
        self.assertEqual(row['missing'], [(9.5, 10)], "the rest of the class still needs a guard")

        second = self.Cover.browse(self._assign(self.teacher_guard_2, 9, 10))
        self.assertEqual((second.hour_from, second.hour_to), (9.5, 10))
        row = self._row(9, 10)
        self.assertEqual(row['covers'], cover | second, "two guards, each with their part")
        self.assertEqual(row['missing'], [])

    def test_a_guard_for_the_whole_class_only_replaces_the_parts_it_overlaps(self):
        self._partial_morning()
        self._guards(self.teacher_c, periods=((9, 10),))
        first = self.Cover.browse(self._assign(self.teacher_guard, 9, 10))

        whole = self.Cover.browse(self._assign(self.teacher_c, 9, 10))

        self.assertEqual((whole.hour_from, whole.hour_to), (9, 10))
        self.assertEqual(first.state, 'released')
        self.assertEqual(self._row(9, 10)['covers'], whole)

    def test_the_board_offers_whole_guards_first_then_partial_ones_with_their_part(self):
        self._partial_morning()
        self._guards(self.teacher_c, periods=((9, 10),))

        data = self.env.company.current_course_id.with_user(self.department_chief).get_guard_duty_board_data(
            '0', 'morning', day=str(self.day))
        line = next(line for line in data['lines'] if line['time_label'] == '09:00-10:00')
        ours = [candidate for candidate in line['guard_candidates']
                if candidate['id'] in (self.teacher_guard | self.teacher_guard_2 | self.teacher_c).ids]
        self.assertEqual([(candidate['id'], candidate['label'], candidate['partial']) for candidate in ours], [
            (self.teacher_c.id, '09:00-10:00', False),
            (self.teacher_guard.id, '09:00-09:30', True),
            (self.teacher_guard_2.id, '09:30-10:00', True),
        ])

    def test_a_guard_takes_their_own_part_of_a_class(self):
        self._partial_morning()
        row = self._board_row(self.guard_user, hour_from=9)
        self.assertTrue(row['can_self_assign'])
        self.assertEqual(row['self_label'], '09:00-09:30')

        cover = self.Cover.browse(self.Cover.with_user(self.guard_user).board_self_assign(
            str(self.day), 9, 10, self.teacher_a.id, self.group_a.id))

        self.assertEqual((cover.hour_from, cover.hour_to), (9, 9.5))
        row = self._board_row(self.guard_user, hour_from=9)
        self.assertFalse(row['can_self_assign'], "their part is taken")
        self.assertEqual(row['self_cover_id'], cover.id)
        self.assertEqual(len(row['missing']), 1)
        self.assertIn('09:30-10:00', row['missing'][0])

    def test_a_partial_guard_shares_their_colour_across_lines_and_shows_as_partial(self):
        """The class is on another line than the guard's own block (9-10 against 8:30-9:30): they
        share one colour for the whole shift, and the guard's badge is marked partial."""
        self._partial_morning()
        self._assign(self.teacher_guard, 9, 10)

        data = self.env.company.current_course_id.with_user(self.department_chief).get_guard_duty_board_data(
            '0', 'morning', day=str(self.day))
        lines = {line['time_label']: line for line in data['lines']}
        cover = next(row for row in lines['09:00-10:00']['absences'] if row['teacher_id'] == self.teacher_a.id)['covers'][0]
        badge = next(guard for guard in lines['08:30-09:30']['guards'] if guard['id'] == self.teacher_guard.id)
        self.assertTrue(cover['partial'])
        self.assertEqual(badge['color'], cover['color'])
        self.assertTrue(badge['partial'])

    def test_guards_covering_one_class_share_its_colour_and_no_overlapping_class_takes_it(self):
        """The colour belongs to the class covered (issue #637): two guards each covering part of
        it share it; another class covered at the same time gets another one."""
        self._partial_morning()
        self._schedule_class(self.teacher_b, self.group_b, 'TABC Calendar B (Colours)', periods=((9, 10),))
        self._absence(self.teacher_b, self.day)
        self._guards(self.teacher_c, periods=((9, 10),))
        self._assign(self.teacher_guard, 9, 10)
        self._assign(self.teacher_guard_2, 9, 10)
        self.Cover.with_user(self.department_chief).board_assign(
            str(self.day), 9, 10, self.teacher_b.id, self.group_b.id, self.teacher_c.id, 'Other class')

        colors = self.course.get_guard_duty_board_lines('0', 'morning', day=self.day)['lines'][0]['cover_colors']

        self.assertEqual(colors[self.teacher_guard.id], colors[self.teacher_guard_2.id])
        self.assertNotEqual(colors[self.teacher_c.id], colors[self.teacher_guard.id])

    # Changing a timetable change already communicated (issue #659)

    def _change_options(self, side):
        return self.env['ems.course'].with_user(self.department_chief).get_change_proposal_options(
            str(self.day), self.group_a.id, side)

    def _change_to(self, change_type, hour=0.0, hour_to=0.0, user=None):
        return self.Notice.with_user(user or self.department_chief).board_send_absence_change(
            str(self.day), self.group_a.id, change_type, hour, hour_to)

    def test_a_communicated_longer_break_can_go_back_to_the_usual_break(self):
        """The absence has not changed, but whoever organises it changed their mind: one correction
        to the families, and the lessons need a guard again."""
        self._can_send()
        self._morning_with_break()
        self._absence(self.teacher_a, self.day, hour_from=9, hour_to=10)
        self._apply_notices(('long_break', 9.0, 10.5))
        side = next(side for side in self._states() if side.startswith('break@'))

        self.assertEqual(self._break_state()['change_options'], [('normal_break', 10, 10.5)])
        self.assertEqual(self._row(9, 10)['change_side'], side)
        data = self._change_options(side)
        self.assertEqual(data['told'], 'Break from 09:00 to 10:30')
        self.assertEqual([option['label'] for option in data['options']], ['Usual break'])

        self.assertFalse(self._change_to('normal_break', 10.0, 10.5)['notice_action'])

        notices = self._families_notices().sorted('id')
        self.assertEqual(len(notices), 2, "one correction, nothing else")
        self.assertEqual((notices[-1]._absence_change_tuples(), notices[-1].state), ([('normal_break', 10.0, 10.5)], 'scheduled'))
        self.assertTrue(notices[-1].subject.startswith('Correction:'))
        self.assertIsNone(self._row(9, 10)['authorized'])
        self.assertTrue(self._assign(hour_from=9, hour_to=10))

    def test_a_communicated_early_leave_can_be_changed_to_another_hour(self):
        self._can_send()
        self._morning()
        self._absence(self.teacher_a, self.day, hour_from=10, hour_to=11)
        self._absence(self.teacher_b, self.day)
        self._apply_notices(('early_leave', 10.0))

        self.assertEqual(self._states()['leave']['change_options'], [('early_leave', 11), ('normal_leave', 0.0)])

        self._change_to('early_leave', 11.0)

        correction = self._families_notices().sorted('id')[-1]
        self.assertEqual(correction._absence_change_tuples(), [('early_leave', 11.0)])
        self.assertTrue(correction.subject.startswith('Correction:'))
        self.assertEqual(self._states()['leave']['communicated'], ('early_leave', 11))
        self.assertIsNone(self._row(10, 11)['authorized'])
        self.assertEqual(self._row(11, 12, teacher=self.teacher_b)['authorized'], ('early_leave', 11))

    def test_a_change_whose_time_has_come_can_no_longer_be_changed(self):
        self._can_send()
        self._morning_with_break()
        self._absence(self.teacher_a, self.day, hour_from=9, hour_to=10)
        self._apply_notices(('long_break', 9.0, 10.5))

        with self._at(9.5):
            self.assertEqual(self._break_state()['change_options'], [])
            self.assertFalse(self._row(9, 10)['change_side'])
            with self.assertRaises(UserError):
                self._change_to('normal_break', 10.0, 10.5)

    def test_only_whoever_organises_the_absence_can_change_what_was_told(self):
        self._can_send()
        self._morning_with_break()
        self._absence(self.teacher_a, self.day, hour_from=9, hour_to=10)
        self._apply_notices(('long_break', 9.0, 10.5))
        side = next(side for side in self._states() if side.startswith('break@'))

        with self.assertRaises(AccessError):
            self.env['ems.course'].with_user(self.other_department_chief).get_change_proposal_options(
                str(self.day), self.group_a.id, side)

    @staticmethod
    def _corrections(plan):
        return [(step['change'], step['groups']) for step in plan['steps'] if step['kind'] == 'correction']

    def test_a_plan_carries_the_correction_its_group_still_needs(self):
        """The families were told the group starts at 9:00, and that absence was refused; a new
        one leaves the group's last lesson free. The plan that tells them it leaves earlier
        corrects the start too: one correction, not a notice and a correction apart."""
        self._can_send()
        self._morning()
        refused = self._absence(self.teacher_a, self.day, hour_from=8, hour_to=9, approve=False)
        self._apply_notices(('late_entry', 9.0))
        refused.action_refuse()
        self._absence(self.teacher_a, self.day, hour_from=10, hour_to=12)

        plan = self._plans()[0]

        self.assertEqual(self._plan_summary(plan)[:2], [
            ('move', self.teacher_b, 11, 10, self.group_a), ('notice', ('early_leave', 11), self.group_a)])
        for other in self._plans():
            self.assertEqual(self._corrections(other), [(('normal_entry', 0.0), self.group_a)],
                             "every plan of the group carries it, so it never goes out apart")
        label = self.env['ems.course']._arrangement_plan_data(plan)['steps'][-1]['label']
        self.assertEqual(label, f'Correction to the families of {self.group_a.name}: Usual timetable.')

        self._apply(plan)

        correction = self._families_notices().sorted('id')[-1]
        self.assertEqual(len(self._families_notices()), 2, "the first notice and one correction")
        self.assertEqual(sorted(correction._absence_change_tuples()), [('early_leave', 11.0), ('normal_entry', 0.0)])
        self.assertTrue(correction.subject.startswith('Correction:'))
        self.assertIsNone(self._states()['entry']['status'], "nothing left to correct")

    def _told_late_entry(self):
        """teacher_a away 8-9 and the families told the group starts at 9:00."""
        self._can_send()
        self._morning()
        self._absence(self.teacher_a, self.day, hour_from=8, hour_to=9)
        self._apply_notices(('late_entry', 9.0))

    def test_a_change_proposal_offers_arrangements_that_correct_what_was_told(self):
        """Instead of coming in at 9:00, teacher_b swaps their 11:00 lesson with teacher_a: the
        families are told, in one correction, that the group starts at the usual time."""
        self._told_late_entry()

        data = self._change_options('entry')

        swap = next(plan for plan in data['plans'] if plan['steps'][0]['kind'] == 'swap')
        self.assertEqual([step['kind'] for step in swap['steps']], ['swap', 'correction'])
        self.assertEqual(swap['steps'][-1]['payload']['change'], ['normal_entry', 0.0])
        self.assertEqual(data['reopen'], [self.group_a.id, 'entry'])

        result = self.Cover.with_user(self.department_chief).board_apply_plan(
            str(self.day), [step['payload'] for step in swap['steps']], reopen=data['reopen'])

        self.assertEqual(self.Cover.browse(result['cover_ids']).arrangement_type, 'swap')
        notices = self._families_notices().sorted('id')
        self.assertEqual(len(notices), 2, "the first notice and one correction")
        self.assertEqual(notices[-1]._absence_change_tuples(), [('normal_entry', 0.0)])
        self.assertTrue(notices[-1].subject.startswith('Correction:'))
        self.assertIsNone(self._states()['entry']['status'])

    def test_a_change_proposal_arrangement_with_its_own_notice_sends_one_correction(self):
        """teacher_b moves their 11:00 lesson to 8:00: the group starts at the usual time and
        leaves at 11:00, both in the same correction."""
        self._told_late_entry()

        data = self._change_options('entry')
        plan = next(plan for plan in data['plans'] if [step['kind'] for step in plan['steps']] == ['move', 'notice', 'correction'])
        self.Cover.with_user(self.department_chief).board_apply_plan(
            str(self.day), [step['payload'] for step in plan['steps']], reopen=data['reopen'])

        notices = self._families_notices().sorted('id')
        self.assertEqual(len(notices), 2)
        self.assertEqual(sorted(notices[-1]._absence_change_tuples()), [('early_leave', 11.0), ('normal_entry', 0.0)])
        self.assertTrue(notices[-1].subject.startswith('Correction:'))

    def test_a_side_already_told_is_not_changed_by_a_plan_without_reopening_it(self):
        self._told_late_entry()

        with self.assertRaises(UserError):
            self.Cover.with_user(self.department_chief).board_apply_plan(str(self.day), [
                {'kind': 'move', 'teacher_ids': self.teacher_b.ids, 'absent_ids': [], 'lesson': [11, 12],
                 'target': [8, 9], 'group_ids': self.group_a.ids},
                {'kind': 'notice', 'group_ids': self.group_a.ids, 'change': ['early_leave', 11.0]},
                {'kind': 'notice', 'group_ids': self.group_a.ids, 'change': ['normal_entry', 0.0]}])

    @staticmethod
    def _plan_changes(plan):
        """`[(kind, change, group ids)]` of the notice and correction steps of a plan's data."""
        return [(step['kind'], tuple(step['payload']['change']), tuple(step['payload']['group_ids']))
                for step in plan['steps'] if step['kind'] in ('notice', 'correction')]

    def test_a_plan_notice_on_the_side_being_changed_becomes_its_correction(self):
        """The families were told the group starts at 10:00; teacher_b's 11:00 lesson moved to 9:00
        lets it start at 9:00 instead. That is the correction itself, not a notice plus a
        correction back to the usual start."""
        self._can_send()
        self._morning()
        self._absence(self.teacher_a, self.day, hour_from=8, hour_to=10)
        self._apply_notices(('late_entry', 10.0))

        plan = next(plan for plan in self._change_options('entry')['plans']
                    if ('correction', ('late_entry', 9.0), tuple(self.group_a.ids)) in self._plan_changes(plan))

        changes = self._plan_changes(plan)
        self.assertFalse([change for change in changes if change[1][0] in ('late_entry', 'normal_entry') and change[0] == 'notice'])
        self.assertNotIn(('correction', ('normal_entry', 0.0), tuple(self.group_a.ids)), changes)
        self.Cover.with_user(self.department_chief).board_apply_plan(
            str(self.day), [step['payload'] for step in plan['steps']], reopen=[self.group_a.id, 'entry'])
        correction = self._families_notices().sorted('id')[-1]
        self.assertIn(('late_entry', 9.0), correction._absence_change_tuples())
        self.assertTrue(correction.subject.startswith('Correction:'))

    def test_a_plan_notice_repeating_what_was_told_is_dropped(self):
        """group_a was told it starts at 9:00, and nobody can fill its first lesson (teacher_b is
        with group_b then). Changing that start, the plan that moves teacher_b's 11:00 lesson into
        the 10:00 gap tells the families the group leaves at 11:00 - and nothing about the start,
        which stays as told: never a correction back to the usual start."""
        self._can_send()
        self._calendar_rows(self.teacher_a, ((8, 9, self.group_a), (9, 10, self.group_a), (10, 11, self.group_a)))
        self._calendar_rows(self.teacher_b, ((8, 9, self.group_b), (11, 12, self.group_a)))
        self._absence(self.teacher_a, self.day, hour_from=8, hour_to=9)
        self._apply_notices(('late_entry', 9.0))
        self._absence(self.teacher_a, self.day, hour_from=10, hour_to=11)

        plan = next(plan for plan in self._change_options('entry')['plans']
                    if ('notice', ('early_leave', 11.0), tuple(self.group_a.ids)) in self._plan_changes(plan))

        self.assertEqual(self._plan_changes(plan), [('notice', ('early_leave', 11.0), tuple(self.group_a.ids))])
