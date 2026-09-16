from datetime import date

from odoo.tests import tagged, HttpCase

from .common import create_level_study, create_role_employee, create_role_user


@tagged('post_install', '-at_install')
class TestSpaceScheduleTour(HttpCase):

    def test_space_schedule_tab_tour(self):
        # Logged in as the least-privileged role with access to this tab (teacher/secretary, both
        # read-only per docs/en/developers/facilities/space_schedule.md's access-control table -
        # teacher picked as the plainest of the two), not admin - see CLAUDE.md's Development
        # workflow step 2 ("Log in as the least-privileged role", added after issue #434).
        teacher_user = create_role_user(self, 'teacher', 'test_teacher_space_schedule_tour')
        create_role_employee(self, teacher_user)

        level, study = create_level_study(self, 'TSPT', level={'name': 'Tour Space Schedule Level'}, study={
            'code': 'TSPT001', 'name': 'Tour Space Schedule Study', 'date': date.today(),
        })
        subject = self.env['ems.subject'].create({
            'code': 'TSPT001', 'acronym': 'TSPT', 'name': 'Tour Space Schedule Subject',
            'study_ids': [(6, 0, [study.id])],
        })
        space = self.env['ems.space'].create({
            'code': 'TSPT-A', 'name': 'Tour Schedule Space',
            'space_type_id': self.env.ref('ems.space_type_classroom').id,
            'work_location_id': self.env.ref('ems.work_location_main').id,
        })
        group = self.env['ems.group'].create({
            'course': 1, 'acronym': 'TSPT', 'level_id': level.id, 'study_id': study.id,
            'space_id': space.id, 'shift': 'morning',
        })
        teacher = self.env['hr.employee'].create({'name': 'Tour Space Schedule Teacher', 'employee_type': 'teacher'})
        calendar = self.env['resource.calendar'].create({'name': 'Tour Space Schedule Calendar'})
        teacher.resource_calendar_id = calendar
        calendar.apply_schedule_changes([{
            'dayofweek': '0', 'hour_from': 9, 'hour_to': 10, 'day_period': 'morning',
            'subject_id': subject.id, 'group_ids': [group.id], 'space_id': space.id,
            'name': 'TSPT: TSPT',
        }])

        self.start_tour("/odoo", "ems_space_schedule_tab", login="test_teacher_space_schedule_tour")
