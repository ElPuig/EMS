from datetime import date, timedelta

from odoo.tests import HttpCase, tagged

from .common import (
    create_head_of_studies_branch, create_level_study, create_role_employee, create_role_user, mock_outgoing_email,
)


@tagged('post_install', '-at_install')
class TestAbsenceCoverageTour(HttpCase):
    """Managing absences from the guard duty board's absences table (issues #539, #571, #581),
    as the absent teacher's Department Chief - the least-privileged role that can manage them
    (every teacher only reads the board)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Approving the absence and notifying the guard both send email - see CLAUDE.md's
        # 'Email safety in tests'.
        mock_outgoing_email(cls)

    def _calendar(self, employee, periods, **vals):
        # Same fixture shape as TestGuardDutyBoardTour: a personal calendar ('employee_id') with
        # no generic default rows.
        calendar = self.env['resource.calendar'].create({
            'name': f'{employee.name} calendar', 'employee_id': employee.id, 'attendance_ids': [(5, 0, 0)]})
        employee.resource_calendar_id = calendar
        calendar.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': hour_from, 'hour_to': hour_to, 'day_period': 'morning', **vals,
        } for hour_from, hour_to in periods])

    def _board_fixture(self, guard=None):
        """Next Monday: 'Tour Absent Teacher' teaches TABTG 8-11 and is away 8-10, while `guard`
        (a plain employee unless given) is on guard duty 8-11. Returns (teacher, guard, group)."""
        if not self.env.company.current_course_id:
            self.env.company.current_course_id = self.env['ems.course'].create({'start': 1997, 'end': 1998})
        level, study = create_level_study(self, 'TABT', level={'name': 'Tour Absence Coverage Level'}, study={
            'code': 'TABT001', 'name': 'Tour Absence Coverage Study', 'date': date.today(),
        })
        subject = self.env['ems.subject'].create({
            'code': 'TABT001', 'acronym': 'TABT', 'name': 'Tour Absence Coverage Subject',
            'study_ids': [(6, 0, [study.id])],
        })
        group = self.env['ems.group'].create({
            'course': 1, 'acronym': 'TABTG', 'level_id': level.id, 'study_id': study.id, 'shift': 'morning',
        })
        teacher = self.env['hr.employee'].create({'name': 'Tour Absent Teacher', 'employee_type': 'teacher'})
        guard = guard or self.env['hr.employee'].create({'name': 'Tour Cover Guard', 'employee_type': 'teacher'})
        create_head_of_studies_branch(self, 'TABT', teacher)
        # The chief heads the teacher's real department, as in production: it is what lets them
        # write to the groups that department teaches.
        chief = teacher.parent_id
        head = chief.parent_id
        teacher.department_id = self.env['hr.department'].create({'name': 'Tour Absence Department', 'manager_id': chief.id})
        teacher.parent_id = chief
        chief.parent_id = head
        self._calendar(teacher, ((8, 9), (9, 10), (10, 11)),
                       subject_id=subject.id, group_ids=[group.id], name='TABTG: TABT')
        self._calendar(guard, ((8, 9), (9, 10), (10, 11)),
                       non_teaching=self.env.ref('ems.non_teaching_g').id, name='Guard')

        # Away for the first two lessons of next Monday: the group could start at 10:00. The board
        # opens on this week, so the tour moves one week forward to reach it.
        day = self.env['ems.datetime_utils'].get_local_today() + timedelta(days=1)
        while day.weekday() != 0:
            day += timedelta(days=1)
        self.env['hr.leave'].create({
            'employee_id': teacher.id,
            'holiday_status_id': self.env.ref('ems.leave_type_justified').id,
            'request_date_from': day, 'request_date_to': day,
            'ems_full_day': False, 'request_hour_from': 8, 'request_hour_to': 10,
            'ems_submitted': True, 'ems_responsible_declaration': True,
        }).action_approve()
        return teacher, guard, group

    def test_absence_coverage_tour(self):
        teacher, guard, group = self._board_fixture()

        self.start_tour("/odoo", "ems_absence_coverage", login=self.department_chief.login)

        cover = self.env['ems.absence_cover'].search([('absent_employee_id', '=', teacher.id)])
        self.assertEqual(cover.guard_employee_id, guard)
        self.assertEqual((cover.hour_from, cover.hour_to), (9, 10))
        self.assertEqual(cover.message, 'Exercises on page 12')
        notice = self.env['ems.notice'].search([('absence_group_id', '=', group.id)])
        self.assertEqual((notice.absence_change_type, notice.absence_change_hour, notice.state), ('late_entry', 9.0, 'draft'))

    def test_guard_self_assignment_tour(self):
        """Issue #601, as the guard on duty - a plain teacher, who manages nobody's absences."""
        user = create_role_user(self, 'teacher', 'test_tour_self_guard', name='Tour Self Guard')
        teacher, guard, _group = self._board_fixture(create_role_employee(self, user, name='Tour Self Guard'))

        self.start_tour("/odoo", "ems_guard_self_assignment", login=user.login)

        covers = self.env['ems.absence_cover'].search([('absent_employee_id', '=', teacher.id)], order='hour_from')
        self.assertEqual([(cover.hour_from, cover.state) for cover in covers], [(8, 'released'), (9, 'assigned')])
        self.assertEqual(covers.guard_employee_id, guard)

    def test_wc_guard_cover_tour(self):
        """Issue #606, as the Department Chief: the WC guard is away, so their duty is a row of the
        absences table, and the regular guard on duty is sent to it."""
        teacher, guard, _group = self._board_fixture()
        wc_guard = self.env['hr.employee'].create({
            'name': 'Tour WC Guard', 'employee_type': 'teacher', 'parent_id': teacher.parent_id.id})
        self._calendar(wc_guard, ((8, 9),), non_teaching=self.env.ref('ems.non_teaching_gwc').id, name='Guard (WC)')
        day = self.env['hr.leave'].search([('employee_id', '=', teacher.id)]).request_date_from
        self.env['hr.leave'].create({
            'employee_id': wc_guard.id,
            'holiday_status_id': self.env.ref('ems.leave_type_justified').id,
            'request_date_from': day, 'request_date_to': day,
            'ems_full_day': False, 'request_hour_from': 8, 'request_hour_to': 9,
            'ems_submitted': True, 'ems_responsible_declaration': True,
        }).action_approve()

        self.start_tour("/odoo", "ems_wc_guard_cover", login=self.department_chief.login)

        cover = self.env['ems.absence_cover'].search([('absent_employee_id', '=', wc_guard.id)])
        self.assertEqual((cover.duty_id, cover.guard_employee_id), (self.env.ref('ems.non_teaching_gwc'), guard))
