from datetime import date, timedelta

from odoo.tests import HttpCase, tagged

from .common import create_level_study, create_role_user, mock_outgoing_email, shift_ems_clock


@tagged('post_install', '-at_install')
class TestGuardDutyBoardTour(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Approving the absence seeded below posts to the chatter and notifies its followers -
        # see CLAUDE.md's 'Email safety in tests'.
        mock_outgoing_email(cls)

    def test_guard_duty_board_tour(self):
        # Logged in as a plain teacher (issue #434's Red-step rule, CLAUDE.md's "Development
        # workflow": the least-privileged role that should have access, not admin by default) -
        # a teacher is exactly who is actually on guard duty, and already has read access to
        # everything this board needs (see test_guard_duty_board.py's own
        # test_teacher_can_call_board_methods) with no extra ACL. create_role_user() sets
        # 'lang': 'en_US' itself, so no separate force_user_language_to_english() call is needed
        # here the way it would be for a pre-existing account like admin.
        create_role_user(self, 'teacher', 'guard_duty_board_tour_teacher')
        # 09:30 of a school day (issue #647): the board opens on today's tab and the morning shift,
        # where the guard below is on duty, so its current-time line must show - whenever the
        # suite runs, weekends and nights included. Every date below is taken from it.
        now = shift_ems_clock(self, hour=9.5, weekdays=range(5))
        # To observe this tour in a real browser during development:
        #   self.start_tour("/odoo", "ems_guard_duty_board", login="guard_duty_board_tour_teacher", watch=True)

        # The board's own client action reads env.company.current_course_id directly (see
        # guard_duty_board.py's get_current_course_data()/get_guard_duty_board_data(), both of
        # which now raise a friendly error instead of crashing when it's unset) - a fresh CI DB
        # has no "current course" configured at all, unlike this box's own dev DB, so this must
        # be set explicitly rather than assumed. Reusing an already-configured one (if any) avoids
        # colliding with it on the unique_course_name constraint (a freshly create()'d course
        # defaults its start/end to this real year too) - same pattern as test_guard_duty_board.py.
        if not self.env.company.current_course_id:
            self.env.company.current_course_id = self.env['ems.course'].create({'start': 1998, 'end': 1999})

        level, study = create_level_study(self, 'TGDBT', level={'name': 'Tour Guard Board Level 1'}, study={
            'code': 'TGDBT001', 'name': 'Test Study (Guard Duty Board Tour)', 'date': date.today(),
        })
        subject = self.env['ems.subject'].create({
            'code': 'TGDBT001', 'acronym': 'TGDBT', 'name': 'Test Subject (Guard Duty Board Tour)',
            'study_ids': [(6, 0, [study.id])],
        })
        space = self.env['ems.space'].create({
            'code': 'TGDBT-A', 'name': 'Tour Guard Board Space',
            'space_type_id': self.env.ref('ems.space_type_classroom').id,
            'work_location_id': self.env.ref('ems.work_location_main').id,
        })
        group = self.env['ems.group'].create({
            'course': 1, 'acronym': 'TGDBT', 'level_id': level.id, 'study_id': study.id,
            'space_id': space.id, 'shift': 'morning',
        })
        teacher = self.env['hr.employee'].create({'name': 'Tour Guard Board Teacher', 'employee_type': 'teacher'})
        # 'employee_id' (matching every real personal calendar - see hr.employee.create()/
        # course_transition_wizard.py) is what '_get_guard_duty_board_attendance_ids' now uses to
        # tell a teacher's own working schedule apart from Odoo's generic default calendar (e.g.
        # "Standard 40 hours/week", 'employee_id' False) - omitting it here made this fixture
        # indistinguishable from that generic calendar on a clean install (found 2026-09-08 via CI).
        calendar = self.env['resource.calendar'].create({'name': 'Tour Guard Board Teacher Calendar', 'employee_id': teacher.id})
        teacher.resource_calendar_id = calendar
        calendar.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'subject_id': subject.id, 'group_ids': [group.id], 'name': 'TGDBT: TGDBT',
        }])

        guard_teacher = self.env['hr.employee'].create({'name': 'Tour Guard Board Guard', 'employee_type': 'teacher'})
        guard_calendar = self.env['resource.calendar'].create({'name': 'Tour Guard Board Guard Calendar', 'employee_id': guard_teacher.id})
        guard_teacher.resource_calendar_id = guard_calendar
        # On Monday, where the fixtures below are, and on today's weekday too, so the board the
        # tour opens on today has a block holding 09:30.
        guard_calendar.apply_schedule_changes([{
            'dayofweek': dayofweek, 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'non_teaching': self.env.ref('ems.non_teaching_g').id, 'name': 'Guard',
        } for dayofweek in sorted({'0', str(now.weekday())})])

        # A second guard, on 'Guard (WC)' duty specifically (2026-09-11, developer request) - the
        # one guard subtype worth calling out on the board itself since, unlike 'Guard (Break)',
        # it can fall at any time of day. Same period as the plain guard above, so the tour can
        # assert the "(WC)" suffix shows on this teacher's own badge and NOT on the plain guard's.
        wc_guard_teacher = self.env['hr.employee'].create({'name': 'Tour Guard Board WC Guard', 'employee_type': 'teacher'})
        wc_guard_calendar = self.env['resource.calendar'].create({'name': 'Tour Guard Board WC Guard Calendar', 'employee_id': wc_guard_teacher.id})
        wc_guard_teacher.resource_calendar_id = wc_guard_calendar
        wc_guard_calendar.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'non_teaching': self.env.ref('ems.non_teaching_gwc').id, 'name': 'Guard (WC)',
        }])

        # A patio/break-time guard (2026-09-11, developer request): a dedicated level whose own
        # schedule framework has NO teaching entry of its own, only a break period, so the row
        # this guard renders on has no cell content at all - exactly the "no real class in it"
        # half of 'is_break's own safety check (see get_guard_duty_board_lines' docstring).
        # Off-grid hours straddling (not fully inside, not fully spanning) the real 09:00-10:00
        # slot other fixtures above use - same reasoning as
        # test_get_guard_duty_board_lines_level_filter_shows_break_time_guard_as_patio_row in
        # test_guard_duty_board.py, empirically confirmed against this dev DB's own real data to
        # avoid this period being absorbed into (or absorbing) an unrelated real class.
        patio_level = self.env['ems.level'].create({'acronym': 'TGDBT3', 'name': 'Tour Guard Board Level 3 (Patio)'})
        patio_framework = self.env['resource.calendar'].create({
            'name': 'Tour Guard Board Patio Framework', 'is_framework': True, 'level_id': patio_level.id,
            'full_time_required_hours': 24,
        })
        self.env['resource.calendar.attendance'].create({
            'calendar_id': patio_framework.id, 'name': 'BR: Break', 'dayofweek': '0',
            'hour_from': 8.9, 'hour_to': 9.6, 'day_period': 'morning', 'non_teaching': self.env.ref('ems.non_teaching_br').id,
        })
        patio_guard_teacher = self.env['hr.employee'].create({'name': 'Tour Guard Board Patio Guard', 'employee_type': 'teacher'})
        patio_guard_calendar = self.env['resource.calendar'].create({'name': 'Tour Guard Board Patio Guard Calendar', 'employee_id': patio_guard_teacher.id})
        patio_guard_teacher.resource_calendar_id = patio_guard_calendar
        patio_guard_calendar.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 8.9, 'hour_to': 9.6, 'day_period': 'morning',
            'non_teaching': self.env.ref('ems.non_teaching_gb').id, 'name': 'Guard (Break)',
        }])

        # A distinct afternoon-only teacher, so the tour can prove the shift dropdown actually
        # re-fetches (not just keeps showing the morning data it already has).
        afternoon_teacher = self.env['hr.employee'].create({'name': 'Tour Guard Board Afternoon Teacher', 'employee_type': 'teacher'})
        afternoon_calendar = self.env['resource.calendar'].create({'name': 'Tour Guard Board Afternoon Calendar', 'employee_id': afternoon_teacher.id})
        afternoon_teacher.resource_calendar_id = afternoon_calendar
        afternoon_calendar.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 16, 'hour_to': 17, 'day_period': 'afternoon',
            'subject_id': subject.id, 'group_ids': [group.id], 'name': 'TGDBT: TGDBT (afternoon)',
        }])

        # A second level/study/group, in an area of its own, so the tour can prove checking an area
        # in the dropdown actually narrows the board down - not just that the dropdown opens. Own subject: 'subject' above is only valid for 'study' (see 'ems.
        # attendance_template._check_subject_valid_for_all_studies'), not 'study2'.
        level2, study2 = create_level_study(self, 'TGDBT2', level={'name': 'Tour Guard Board Level 2'}, study={
            'code': 'TGDBT2001', 'name': 'Test Study 2 (Guard Duty Board Tour)', 'date': date.today(),
        })
        subject2 = self.env['ems.subject'].create({
            'code': 'TGDBT2001', 'acronym': 'TGDBT2', 'name': 'Test Subject 2 (Guard Duty Board Tour)',
            'study_ids': [(6, 0, [study2.id])],
        })
        space2 = self.env['ems.space'].create({
            'code': 'TGDBT2-A', 'name': 'Tour Guard Board Space 2',
            'space_type_id': self.env.ref('ems.space_type_classroom').id,
            'work_location_id': self.env.ref('ems.work_location_main').id,
        })
        group2 = self.env['ems.group'].create({
            'course': 1, 'acronym': 'TGDBT2', 'level_id': level2.id, 'study_id': study2.id,
            'space_id': space2.id, 'shift': 'morning',
        })
        # One area per study (issue #637): the board's filter picks areas, the top-level department
        # above the department that manages each study.
        for area_name, area_study in (('Tour Guard Board Area 1', study), ('Tour Guard Board Area 2', study2)):
            area_study.managing_department_id = self.env['hr.department'].create({
                'name': area_name, 'is_top_level': True, 'top_level_area': 'academic'})
        level2_teacher = self.env['hr.employee'].create({'name': 'Tour Guard Board Level 2 Teacher', 'employee_type': 'teacher'})
        level2_calendar = self.env['resource.calendar'].create({'name': 'Tour Guard Board Level 2 Calendar', 'employee_id': level2_teacher.id})
        level2_teacher.resource_calendar_id = level2_calendar
        level2_calendar.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'subject_id': subject2.id, 'group_ids': [group2.id], 'name': 'TGDBT2: TGDBT2',
        }])

        # An approved whole-day absence for the morning teacher, on the Monday of the week the
        # board opens on - which is the same Monday its own date picker resolves (see mondayOf()
        # in guard_duty_board.js: a weekend belongs to the week it closes, exactly as
        # date.weekday() does here). Whole day explicitly: 'leave_type_justified' does not seed
        # it, and a request that is neither a whole day nor a span of hours is worth zero hours,
        # which hr_holidays itself then refuses to approve.
        today = now.date()
        monday = today - timedelta(days=today.weekday())
        self.env['hr.leave'].create({
            'employee_id': teacher.id,
            'holiday_status_id': self.env.ref('ems.leave_type_justified').id,
            'request_date_from': monday,
            'request_date_to': monday,
            'ems_full_day': True,
            'ems_submitted': True,
            'ems_responsible_declaration': True,
        }).action_approve()

        self.start_tour("/odoo", "ems_guard_duty_board", login="guard_duty_board_tour_teacher")
