from datetime import date

from odoo.tests import HttpCase, tagged

from .common import create_level_study, force_user_language_to_english


@tagged('post_install', '-at_install')
class TestGuardDutyBoardTour(HttpCase):

    def test_guard_duty_board_tour(self):
        force_user_language_to_english(self, self.env.ref('base.user_admin'))
        # To observe this tour in a real browser during development:
        #   self.start_tour("/odoo", "ems_guard_duty_board", login="admin", watch=True)

        # The board's own client action reads env.company.current_course_id directly (see
        # guard_duty_board.py's get_current_course_data()/get_guard_duty_board_data(), both of
        # which now raise a friendly error instead of crashing when it's unset) - a fresh CI DB
        # has no "current course" configured at all, unlike this box's own dev DB, so this must
        # be set explicitly rather than assumed. Reusing an already-configured one (if any) avoids
        # colliding with it on the unique_course_name constraint (a freshly create()'d course
        # defaults its start/end to this real year too) - same pattern as test_guard_duty_board.py.
        if not self.env.company.current_course_id:
            self.env.company.current_course_id = self.env['ems.course'].create({'start': 1998, 'end': 1999})

        level, study = create_level_study(self, 'TGDBT', level={'name': 'Test Level (Guard Duty Board Tour)'}, study={
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
        calendar = self.env['resource.calendar'].create({'name': 'Tour Guard Board Teacher Calendar'})
        teacher.resource_calendar_id = calendar
        calendar.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'subject_id': subject.id, 'group_ids': [group.id], 'name': 'TGDBT: TGDBT',
        }])

        guard_teacher = self.env['hr.employee'].create({'name': 'Tour Guard Board Guard', 'employee_type': 'teacher'})
        guard_calendar = self.env['resource.calendar'].create({'name': 'Tour Guard Board Guard Calendar'})
        guard_teacher.resource_calendar_id = guard_calendar
        guard_calendar.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'non_teaching': self.env.ref('ems.non_teaching_g').id, 'name': 'Guard',
        }])

        # A distinct afternoon-only teacher, so the tour can prove the shift dropdown actually
        # re-fetches (not just keeps showing the morning data it already has).
        afternoon_teacher = self.env['hr.employee'].create({'name': 'Tour Guard Board Afternoon Teacher', 'employee_type': 'teacher'})
        afternoon_calendar = self.env['resource.calendar'].create({'name': 'Tour Guard Board Afternoon Calendar'})
        afternoon_teacher.resource_calendar_id = afternoon_calendar
        afternoon_calendar.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 16, 'hour_to': 17, 'day_period': 'afternoon',
            'subject_id': subject.id, 'group_ids': [group.id], 'name': 'TGDBT: TGDBT (afternoon)',
        }])

        self.start_tour("/odoo", "ems_guard_duty_board", login="admin")
