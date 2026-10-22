from datetime import date, timedelta

from odoo.tests import HttpCase, tagged

from .common import (
    create_head_of_studies_branch, create_level_study, create_role_employee, create_role_user, mock_outgoing_email,
    next_student_id,
)


@tagged('post_install', '-at_install')
class TestAbsenceCoverageTour(HttpCase):
    """Managing absences from the guard duty board's absences table (issues #539, #571, #581),
    as the Department Chief of the department that manages the group's study (issue #622) - the
    least-privileged role that can manage them (every teacher only reads the board)."""

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

    def _board_fixture(self, guard=None, away=(8, 10)):
        """Next Monday: 'Tour Absent Teacher' teaches TABTG 8-11 and is away 8-10 (or `away`), while
        `guard` (a plain employee unless given) is on guard duty 8-11. Returns (teacher, guard, group)."""
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
        # Issue #622: the teacher is shared - they belong to another department, out of the
        # chief's chain of command; the chief heads the department that manages the group's
        # study, which is what lets them organise this class and write to its families.
        chief = teacher.parent_id
        head = chief.parent_id
        study.managing_department_id = self.env['hr.department'].create({
            'name': 'Tour Absence Department', 'manager_id': chief.id})
        teacher.department_id = self.env['hr.department'].create({'name': 'Tour Shared Teacher Department'})
        teacher.parent_id = self.other_department_chief.employee_ids
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
            'ems_full_day': False, 'request_hour_from': away[0], 'request_hour_to': away[1],
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
        self.assertEqual((notice._absence_change_tuples(), notice.state), ([('late_entry', 9.0)], 'draft'))

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
            'name': 'Tour WC Guard', 'employee_type': 'teacher',
            # A guard duty has no students: it stays with the guard's own chain of command.
            'parent_id': self.department_chief.employee_ids.id})
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

    def _arrangement_teacher(self, name, hours, group):
        teacher = self.env['hr.employee'].create({'name': name, 'employee_type': 'teacher'})
        subject = self.env['ems.subject'].search([('code', '=', 'TABT001')])
        self._calendar(teacher, (hours,), subject_id=subject.id, group_ids=[group.id], name='TABTG: TABT')
        return teacher

    def test_absence_arrangement_tour(self):
        """Issues #605 and #645, as the Department Chief: the board proposes how the group's teachers
        could rearrange their lessons. All but the last step of the best plan is applied from the
        possible arrangements box: the lesson left free becomes a class to cover."""
        teacher, _guard, group = self._board_fixture()
        swapper = self._arrangement_teacher('Tour Swap Teacher', (11, 12), group)
        mover = self._arrangement_teacher('Tour Move Teacher', (12, 13), group)
        day = self.env['hr.leave'].search([('employee_id', '=', teacher.id)]).request_date_from
        plan = self.env['ems.course']._get_arrangement_plans(day, group)[0]
        # The absent teacher is in from 10:00: they teach their 8:00 lesson at 11 (the swap) and
        # their 9:00 one at 12 (the move left that hour free). Nobody loses a lesson.
        self.assertEqual([(step['kind'], step['teacher'], step['target'][0]) for step in plan['steps']],
                         [('swap', swapper, 8), ('move', mover, 9), ('move', teacher, 12)])

        self.start_tour("/odoo", "ems_absence_arrangement", login=self.department_chief.login)

        covers = self.env['ems.absence_cover'].search([('group_id', '=', group.id)], order='hour_from')
        self.assertEqual([(cover.hour_from, cover.arrangement_type, cover.guard_employee_id, cover.absent_employee_id)
                          for cover in covers], [(8, 'swap', swapper, teacher), (9, 'move', mover, teacher)])
        self.assertTrue(all(covers.mapped('is_effective')))
        self.assertFalse(covers.notice_id)
        # Issue #649: one notice to the group's students about the lessons that change time, left
        # a draft since the group has no students to send it to (issue #652).
        students = covers.student_notice_id
        self.assertEqual((len(students), students.state, students.recipient_type), (1, 'draft', 'students'))

        self.start_tour("/odoo", "ems_absence_arrangement_result", login=self.department_chief.login)

    def _move_fixture(self):
        """The absent teacher is only away 9-10, in the middle of the group's day; the group's
        last lesson, at 12, can be moved into it, the group leaving at 11: the one plan."""
        teacher, _guard, group = self._board_fixture(away=(9, 10))
        mover = self._arrangement_teacher('Tour Move Teacher', (12, 13), group)
        day = self.env['hr.leave'].search([('employee_id', '=', teacher.id)]).request_date_from
        plans = self.env['ems.course']._get_arrangement_plans(day, group)
        self.assertEqual([[(step['kind'], step.get('change') or step['teacher']) for step in plan['steps']] for plan in plans],
                         [[('move', mover), ('notice', ('early_leave', 11))]])
        return group, mover, day, plans[0]

    def test_absence_arrangement_dialog_tour(self):
        """Issues #605 and #645: the plan applied from the 9:00 lesson's dialog. The group has no
        students, so its notice for the families cannot be sent at once (issue #652): it opens as a
        draft to review, and the move waits for it."""
        group, mover, _day, _plan = self._move_fixture()

        self.start_tour("/odoo", "ems_absence_arrangement_dialog", login=self.department_chief.login)

        cover = self.env['ems.absence_cover'].search([('group_id', '=', group.id)])
        self.assertEqual((cover.hour_from, cover.guard_employee_id), (9, mover))
        notice = cover.notice_id
        self.assertEqual((notice._absence_change_tuples(), notice.state), ([('early_leave', 11.0)], 'draft'))
        self.assertFalse(cover.is_effective)

    def test_absence_arrangement_change_tour(self):
        """Issue #623: once the families were told, the class a lesson was moved into shows both
        who teaches it and the timetable change that came with it (the group leaves earlier)."""
        _group, _mover, day, plan = self._move_fixture()
        course = self.env['ems.course']
        result = self.env['ems.absence_cover'].with_user(self.department_chief).board_apply_plan(
            str(day), [step['payload'] for step in course._arrangement_plan_data(plan)['steps']])
        self.env['ems.notice'].browse(result['notice_action']['res_id']).state = 'scheduled'

        self.start_tour("/odoo", "ems_absence_arrangement_change", login=self.department_chief.login)

    def _told_late_entry(self, swapper=False):
        """Issue #659: `_board_fixture`, with a student and family the notices reach, and the
        families told the group starts at 10:00. With `swapper`, a teacher of the group at 11:00
        who could swap lessons with the absent one."""
        teacher, _guard, group = self._board_fixture()
        if swapper:
            self._arrangement_teacher('Tour Swap Teacher', (11, 12), group)
        student = self.env['res.partner'].create({
            'name': 'Tour 659 Student', 'contact_type': 'student', 'student_id': next_student_id(),
            'main_group_id': group.id, 'email': 'tour659.student@example.com'})
        family = self.env['res.partner'].create({
            'name': 'Tour 659 Family', 'contact_type': 'family', 'email': 'tour659.family@example.com'})
        self.env['res.partner.relation'].create({
            'left_partner_id': family.id, 'type_id': self.env.ref('ems.relation_type_father').id,
            'right_partner_id': student.id})
        self.department_chief.email = 'tour659.chief@example.com'
        day = self.env['hr.leave'].search([('employee_id', '=', teacher.id)]).request_date_from
        self.env['ems.notice'].with_user(self.department_chief).board_send_absence_change(str(day), group.id, 'late_entry', 10.0)
        return group

    def test_change_proposal_tour(self):
        """Issue #659, as the Department Chief: the families were told the group starts at 10:00;
        from the struck-out row, the chief sees a swap that would correct it, but changes it to 9:00
        instead (a guard will cover the 9:00 lesson), and one correction goes out."""
        group = self._told_late_entry(swapper=True)

        self.start_tour("/odoo", "ems_change_proposal", login=self.department_chief.login)

        notices = self.env['ems.notice'].search([('absence_group_id', '=', group.id)], order='id')
        self.assertEqual(len(notices), 2, "the notice and one correction")
        self.assertEqual((notices[-1]._absence_change_tuples(), notices[-1].state), ([('late_entry', 9.0)], 'scheduled'))
        self.assertTrue(notices[-1].subject.startswith('Correction:'))

    def test_corrections_box_tour(self):
        """Issue #659: the families were told the group starts at 10:00, and the absence then moved
        to 10-11. The group goes in the red corrections box; only telling the families, the chief
        unchecks the new early leave and sends the correction alone."""
        group = self._told_late_entry()
        leave = self.env['hr.leave'].search([('employee_id.name', '=', 'Tour Absent Teacher')])
        day = leave.request_date_from
        leave.action_refuse()
        self.env['hr.leave'].create({
            'employee_id': leave.employee_id.id, 'holiday_status_id': self.env.ref('ems.leave_type_justified').id,
            'request_date_from': day, 'request_date_to': day, 'ems_full_day': False,
            'request_hour_from': 10, 'request_hour_to': 11, 'ems_submitted': True, 'ems_responsible_declaration': True,
        }).action_approve()

        self.start_tour("/odoo", "ems_corrections_box", login=self.department_chief.login)

        notices = self.env['ems.notice'].search([('absence_group_id', '=', group.id)], order='id')
        self.assertEqual(len(notices), 2, "the notice and one correction")
        self.assertEqual(notices[-1]._absence_change_tuples(), [('normal_entry', 0.0)])

    def test_not_on_guard_tour(self):
        """Issue #659, as a plain teacher who is not on guard duty: a class still to be covered
        answers the pointer too, saying why they cannot cover it."""
        user = create_role_user(self, 'teacher', 'test_tour_not_on_guard', name='Tour Not On Guard')
        create_role_employee(self, user, name='Tour Not On Guard')
        self._board_fixture()

        self.start_tour("/odoo", "ems_not_on_guard", login=user.login)
