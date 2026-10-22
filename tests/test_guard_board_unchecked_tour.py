from datetime import date

from odoo.tests import HttpCase, tagged

from .common import (
    create_level_study, create_role_employee, create_role_user, make_working_day, mock_outgoing_email, shift_ems_clock,
)


@tagged('post_install', '-at_install')
class TestGuardBoardUncheckedTour(HttpCase):
    """Issue #692 in the browser: a class whose teacher has not checked in shows up on the guard
    duty board's absences table, and the guard on duty - a plain teacher, the least-privileged role
    that can act on it - says the teacher is in the classroom."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Checking the teacher in tells them by message - see CLAUDE.md's 'Email safety in tests'.
        mock_outgoing_email(cls)

    def setUp(self):
        super().setUp()
        # 10:30 of a school day: the 8-9 class is over and the 10-11 one is going on.
        now = shift_ems_clock(self, hour=10.5, weekdays=range(5))
        self.today = now.date()
        make_working_day(self, self.today)
        weekday = str(self.today.weekday())
        if not self.env.company.current_course_id:
            self.env.company.current_course_id = self.env['ems.course'].create({'start': 1996, 'end': 1997})
        level, study = create_level_study(self, 'TGBUT', level={'name': 'Tour Unchecked Level'}, study={
            'code': 'TGBUT001', 'name': 'Tour Unchecked Study', 'date': date.today(),
        })
        subject = self.env['ems.subject'].create({
            'code': 'TGBUT001', 'acronym': 'TGBUT', 'name': 'Tour Unchecked Subject', 'study_ids': [(6, 0, [study.id])],
        })
        group = self.env['ems.group'].create({
            'course': 1, 'acronym': 'TGBUT', 'level_id': level.id, 'study_id': study.id, 'shift': 'morning',
        })
        self.teacher_user = create_role_user(self, 'teacher', 'test_tour_unchecked_teacher', name='Tour Unchecked Teacher')
        self.teacher = create_role_employee(self, self.teacher_user, name='Tour Unchecked Teacher')
        self.guard_user = create_role_user(self, 'teacher', 'test_tour_unchecked_guard', name='Tour Unchecked Guard')
        self.guard = create_role_employee(self, self.guard_user, name='Tour Unchecked Guard')
        self._calendar(self.teacher, weekday, ((8, 9), (10, 11)), subject_id=subject.id, group_ids=[group.id],
                       name='TGBUT: TGBUT')
        self._calendar(self.guard, weekday, ((10, 11),), non_teaching=self.env.ref('ems.non_teaching_g').id, name='Guard')
        utils = self.env['ems.datetime_utils']
        self.env['hr.attendance'].create({
            'employee_id': self.guard.id,
            'check_in': utils.datetime_to_odoo(utils.time_float_to_utc_datetime(self.today, 7.9)),
        })

    def _calendar(self, employee, weekday, periods, **vals):
        calendar = self.env['resource.calendar'].create({
            'name': f'{employee.name} calendar', 'employee_id': employee.id, 'attendance_ids': [(5, 0, 0)]})
        employee.resource_calendar_id = calendar
        calendar.apply_schedule_changes([{
            'dayofweek': weekday, 'hour_from': hour_from, 'hour_to': hour_to, 'day_period': 'morning', **vals,
        } for hour_from, hour_to in periods])

    def _teacher_check_in(self):
        return self.env['hr.attendance'].search([('employee_id', '=', self.teacher.id)])

    def test_the_guard_says_the_teacher_is_in_the_classroom(self):
        self.start_tour("/odoo", "ems_guard_board_unchecked", login=self.guard_user.login)

        attendance = self._teacher_check_in()
        self.assertEqual(len(attendance), 1)
        self.assertEqual(attendance.ems_checked_in_by_id, self.guard_user)

        # The teacher sees who registered it, on the check-in's own form.
        self.start_tour(f"/odoo/hr.attendance/{attendance.id}", "ems_guard_board_unchecked_form",
                        login=self.teacher_user.login)

    def test_the_guard_covers_it_from_the_dialog(self):
        self.start_tour("/odoo", "ems_guard_board_unchecked_cover", login=self.guard_user.login)
        cover = self.env['ems.absence_cover'].search([('absent_employee_id', '=', self.teacher.id)])
        self.assertEqual(cover.guard_employee_id, self.guard)
        self.assertEqual(cover.state, 'assigned')
        self.assertFalse(self._teacher_check_in(), "covering the class doesn't check the teacher in")

    def test_the_board_refreshes_itself(self):
        """Someone else checks the teacher in: the board hears it through the bus and reloads."""
        self.start_tour("/odoo", "ems_guard_board_unchecked_refresh", login=self.guard_user.login)
        self.assertEqual(self._teacher_check_in().ems_checked_in_by_id, self.guard_user)
