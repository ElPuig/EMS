from datetime import timedelta
from unittest.mock import patch

from pytz import UTC

from odoo.exceptions import AccessError, UserError

from odoo.addons.ems.models.shared.guard_board_notifier import GUARD_BOARD_CHANGED, GUARD_BOARD_CHANNEL

from .common import allow_every_absence_change, create_head_of_studies_branch, create_role_employee, create_role_user, make_working_day, shift_ems_clock
from .test_guard_duty_board import GuardDutyBoardCase


class TestGuardBoardUnchecked(GuardDutyBoardCase):
    """A class whose teacher has not checked in shows up on the guard duty board's absences table
    as soon as it starts (issue #692), and whoever is on guard then, or manages the absence, can say
    the teacher is in the classroom after all: that checks them in."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # 10:30 on a school day: the 8-9, 9-10 and 10-11 classes have started, 11-12 has not.
        cls.now = shift_ems_clock(cls, hour=10.5, weekdays=range(5))
        cls.today = cls.now.date()
        cls.weekday = str(cls.today.weekday())
        create_head_of_studies_branch(cls, 'TGBU', cls.teacher_a)
        cls.teacher_a_user = create_role_user(cls, 'teacher', 'test_teacher_a_tgbu', name='TGBU Teacher A')
        cls.teacher_a.user_id = cls.teacher_a_user
        cls.teacher_a_user.partner_id.lang = 'en_US'
        cls.guard_user = create_role_user(cls, 'teacher', 'test_guard_tgbu', name='TGBU Guard')
        cls.teacher_guard.user_id = cls.guard_user
        cls.other_teacher = create_role_user(cls, 'teacher', 'test_other_teacher_tgbu', name='TGBU Other Teacher')
        cls.director = create_role_user(cls, 'director', 'test_director_tgbu', name='TGBU Director')
        # The Director is the company's, as in production (see hr.employee.tutor_scope_user_ids).
        cls.env.company.director_id = create_role_employee(cls, cls.director)
        cls.Cover = cls.env['ems.absence_cover']
        cls.Attendance = cls.env['hr.attendance']
        # Every timetable change on: a teacher who only has not checked in must still never
        # propose one.
        allow_every_absence_change(cls.env)

    def setUp(self):
        super().setUp()
        make_working_day(self, self.today)
        # teacher_a teaches group_a all morning and has not checked in; teacher_b teaches group_b
        # at 10-11 and has; the guard is on duty 10-12 and has checked in too.
        self._schedule_class(self.teacher_a, self.group_a, 'TGBU Calendar A',
                             periods=((8, 9), (9, 10), (10, 11), (11, 12)), dayofweek=self.weekday)
        self._schedule_class(self.teacher_b, self.group_b, 'TGBU Calendar B', periods=((10, 11),), dayofweek=self.weekday)
        guard_calendar = self._new_calendar(self.teacher_guard, 'TGBU Guard Calendar')
        guard_calendar.apply_schedule_changes([{
            'dayofweek': self.weekday, 'hour_from': hour_from, 'hour_to': hour_to, 'day_period': 'morning',
            'non_teaching': self.non_teaching_guard.id, 'name': 'Guard',
        } for hour_from, hour_to in ((10, 11), (11, 12))])
        self._check_in(self.teacher_b, 7.9)
        self._check_in(self.teacher_guard, 7.9)

    def _check_in(self, employee, hour, day=None):
        utils = self.env['ems.datetime_utils']
        check_in = utils.datetime_to_odoo(utils.time_float_to_utc_datetime(day or self.today, hour))
        return self.Attendance.create({'employee_id': employee.id, 'check_in': check_in})

    def _line(self, hour_from, hour_to, day=None):
        return self._teaching_line(day or self.today, hour_from, hour_to)

    def _states(self, hour_from, hour_to, teacher=None, day=None):
        teacher = teacher or self.teacher_a
        return [row['state'] for row in self._line(hour_from, hour_to, day)['absences'] if row['teacher'] == teacher]

    def _data_row(self, hour_from, hour_to, user):
        data = self.env['ems.course'].with_user(user).get_guard_duty_board_data(self.weekday, 'morning', None, str(self.today))
        line = next(line for line in data['lines'] if (line['hour_from'], line['hour_to']) == (hour_from, hour_to))
        return next(row for row in line['absences'] if row['teacher_id'] == self.teacher_a.id)

    def _mark_present(self, user, hour_from=10, hour_to=11, day=None):
        return self.Cover.with_user(user).board_mark_present(
            str(day or self.today), hour_from, hour_to, self.teacher_a.id, self.group_a.id)

    # Which classes show up

    def test_every_class_started_without_a_check_in_is_on_the_table(self):
        for period in ((8, 9), (9, 10), (10, 11)):
            self.assertEqual(self._states(*period), ['unchecked'], period)
        # Not started yet: nothing to cover.
        self.assertEqual(self._states(11, 12), [])
        # teacher_b checked in: their class is not on the table.
        self.assertEqual(self._states(10, 11, teacher=self.teacher_b), [])

    def test_only_today_counts(self):
        next_week = self.today + timedelta(days=7)
        self.assertEqual(self._states(8, 9, day=next_week), [])
        last_week = self.today - timedelta(days=7)
        self.assertEqual(self._states(8, 9, day=last_week), [])

    def test_an_absence_outranks_a_missing_check_in(self):
        self._absence(self.teacher_a, self.today)
        self.assertEqual(self._states(8, 9), ['approved'])
        self.assertEqual(self._states(11, 12), ['approved'])

    def test_checking_in_late_clears_the_class_in_progress_and_the_next_ones(self):
        self._check_in(self.teacher_a, 9.5)
        # Over before they arrived: still a class they missed.
        self.assertEqual(self._states(8, 9), ['unchecked'])
        self.assertEqual(self._states(9, 10), [])
        self.assertEqual(self._states(10, 11), [])

    def test_a_guard_duty_that_is_not_regular_is_a_row_too(self):
        # A WC guard who has not checked in leaves their post empty, like an absent one (#606).
        wc_guard = self.env['hr.employee'].create({'name': 'TGBU WC Guard', 'employee_type': 'teacher'})
        calendar = self._new_calendar(wc_guard, 'TGBU WC Guard Calendar')
        calendar.apply_schedule_changes([{
            'dayofweek': self.weekday, 'hour_from': 10, 'hour_to': 11, 'day_period': 'morning',
            'non_teaching': self.non_teaching_guard_wc.id, 'name': 'Guard (WC)',
        }])
        rows = [row for row in self._line(10, 11)['absences'] if row['teacher'] == wc_guard]
        self.assertEqual([(row['state'], row['duty']) for row in rows], [('unchecked', self.non_teaching_guard_wc)])

    def test_the_printed_absences_table_says_not_checked_in(self):
        content, _content_type = self.env['ir.actions.report'].with_context(
            guard_duty_weekday=self.weekday, guard_duty_shift='morning', guard_duty_date=str(self.today),
            guard_duty_view='table')._render_qweb_html('ems.report_guard_duty_board', [self.course.id])
        self.assertIn(b'Not checked in', content)

    # Open boards are told (bus) when what they show changes

    def _board_notifications(self, action):
        with patch.object(type(self.env['bus.bus']), '_sendone') as sendone:
            action()
        return [call.args for call in sendone.call_args_list if call.args[0] == GUARD_BOARD_CHANNEL]

    def test_open_boards_are_told_when_the_day_changes(self):
        day = {'date_from': str(self.today), 'date_to': str(self.today)}
        expected = [(GUARD_BOARD_CHANNEL, GUARD_BOARD_CHANGED, day)]
        # A check-in.
        self.assertEqual(self._board_notifications(lambda: self._check_in(self.teacher_a, 10.4)), expected)
        # A guard sent to a class.
        self.Attendance.search([('employee_id', '=', self.teacher_a.id)]).unlink()
        sent = self._board_notifications(lambda: self.Cover.with_user(self.department_chief).board_assign(
            str(self.today), 10, 11, self.teacher_a.id, self.group_a.id, self.teacher_guard.id, False))
        self.assertIn(expected[0], sent)
        # An absence, for every day it spans.
        leave = self._absence(self.teacher_b, self.today + timedelta(days=7), approve=False)
        week = {'date_from': str(leave.request_date_from), 'date_to': str(leave.request_date_to)}
        self.assertIn((GUARD_BOARD_CHANNEL, GUARD_BOARD_CHANGED, week), self._board_notifications(leave.action_approve))
        # Nothing the board shows: no message.
        attendance = self.Attendance.search([('employee_id', '=', self.teacher_b.id)])
        self.assertEqual(self._board_notifications(lambda: attendance.write({'check_out': attendance.check_in})), [])

    # Who can cover it

    def test_a_guard_sent_to_it_is_released_once_the_teacher_checks_in(self):
        cover = self.Cover.browse(self.Cover.with_user(self.department_chief).board_assign(
            str(self.today), 10, 11, self.teacher_a.id, self.group_a.id, self.teacher_guard.id, False))
        self.assertEqual(cover.guard_employee_id, self.teacher_guard)
        self._check_in(self.teacher_a, 10.4)
        actions = self.course.get_guard_duty_board_lines(self.weekday, 'morning', day=self.today)['actions']
        self.assertIn(cover, [action['cover'] for action in actions if action['type'] == 'obsolete_cover'])

    def test_a_guard_who_has_not_checked_in_is_not_available(self):
        self.Attendance.search([('employee_id', '=', self.teacher_guard.id)]).unlink()
        line = self._line(10, 11)
        self.assertEqual(line['guard_absences'].get(self.teacher_guard.id), 'unchecked')
        self.assertNotIn(self.teacher_guard, line['guard_spans'])
        with self.assertRaises(UserError):
            self.Cover.with_user(self.department_chief).board_assign(
                str(self.today), 10, 11, self.teacher_a.id, self.group_a.id, self.teacher_guard.id, False)

    def test_only_a_guard_is_offered_never_a_timetable_change_or_an_arrangement(self):
        states = self.env['ems.course']._get_absence_change_states(self.today, self.group_a)[self.group_a.id]
        self.assertFalse([side for side, state in states.items() if state['status']])
        row = self._absence_row(self._line(10, 11), self.teacher_a)
        self.assertEqual(row['arrangement_plans'], [])
        with self.assertRaises(UserError):
            self.Cover.with_user(self.department_chief).board_arrange(
                str(self.today), 10, 11, self.teacher_a.id, self.group_a.id, 'manual', note='Groups joined')

    # "The teacher is in the classroom"

    def test_the_guard_on_duty_checks_the_teacher_in(self):
        self._mark_present(self.guard_user)

        attendance = self.Attendance.search([('employee_id', '=', self.teacher_a.id)])
        self.assertEqual(len(attendance), 1)
        self.assertEqual(attendance.ems_checked_in_by_id, self.guard_user)
        self.assertEqual(attendance.in_mode, 'manual')
        # Checked in now (10:30 company time), not at the class's start.
        utils = self.env['ems.datetime_utils']
        local_check_in = utils.utc_datetime_to_local(attendance.check_in.replace(tzinfo=UTC))
        self.assertAlmostEqual(utils.time_to_float(local_check_in), 10.5, delta=0.1)
        # The class in progress leaves the table; the ones already over stay.
        self.assertEqual(self._states(10, 11), [])
        self.assertEqual(self._states(8, 9), ['unchecked'])
        # The teacher is told who checked them in.
        message = self.env['mail.message'].search([
            ('model', '=', 'hr.attendance'), ('res_id', '=', attendance.id),
            ('partner_ids', 'in', self.teacher_a_user.partner_id.ids)])
        self.assertEqual(len(message), 1)
        self.assertIn('TGBU Guard', message.body)

    def test_whoever_manages_the_absence_can_check_the_teacher_in(self):
        for user in (self.department_chief, self.head_of_studies, self.director, self.env.ref('base.user_admin')):
            with self.subTest(user=user.login):
                self._mark_present(user)
                attendance = self.Attendance.search([('employee_id', '=', self.teacher_a.id)])
                self.assertEqual(attendance.ems_checked_in_by_id, user)
                attendance.unlink()

    def test_nobody_else_can(self):
        for user in (self.other_teacher, self.other_department_chief, self.teacher_a_user):
            with self.subTest(user=user.login), self.assertRaises(AccessError):
                self._mark_present(user)
        self.assertFalse(self.Attendance.search([('employee_id', '=', self.teacher_a.id)]))

    def test_only_a_class_in_progress_on_a_teacher_still_not_checked_in(self):
        # Already over: checking them in now would not take it off the table.
        with self.assertRaises(UserError):
            self._mark_present(self.department_chief, 8, 9)
        # Not today.
        with self.assertRaises(UserError):
            self._mark_present(self.department_chief, day=self.today + timedelta(days=7))
        # Already checked in.
        self._check_in(self.teacher_a, 10.4)
        with self.assertRaises(UserError):
            self._mark_present(self.department_chief)

    def test_the_board_offers_it_on_the_class_in_progress_only(self):
        self.assertTrue(self._data_row(10, 11, self.guard_user)['can_mark_present'])
        self.assertFalse(self._data_row(8, 9, self.guard_user)['can_mark_present'])
        self.assertTrue(self._data_row(10, 11, self.department_chief)['can_mark_present'])
        self.assertFalse(self._data_row(10, 11, self.other_teacher)['can_mark_present'])
