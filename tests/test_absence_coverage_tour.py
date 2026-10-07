from datetime import date, timedelta

from odoo.tests import HttpCase, tagged

from .common import create_head_of_studies_branch, create_level_study, mock_outgoing_email


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

    def test_absence_coverage_tour(self):
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
        guard = self.env['hr.employee'].create({'name': 'Tour Cover Guard', 'employee_type': 'teacher'})
        create_head_of_studies_branch(self, 'TABT', teacher)
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

        self.start_tour("/odoo", "ems_absence_coverage", login=self.department_chief.login)

        cover = self.env['ems.absence_cover'].search([('absent_employee_id', '=', teacher.id)])
        self.assertEqual(cover.guard_employee_id, guard)
        self.assertEqual((cover.hour_from, cover.hour_to), (9, 10))
        self.assertEqual(cover.message, 'Exercises on page 12')
        notice = self.env['ems.notice'].search([('absence_group_id', '=', group.id)])
        self.assertEqual((notice.absence_change_type, notice.absence_change_hour, notice.state), ('late_entry', 9.0, 'draft'))
