# -*- coding: utf-8 -*-

from datetime import date

from odoo.tests import HttpCase, tagged

from .common import create_level_study, create_role_employee, create_role_user


@tagged('post_install', '-at_install')
class TestGroupScheduleSubgroupsTour(HttpCase):
    """Issue #611 - a main group's Schedule tab in a real browser: the classes of its subgroups,
    two halves side by side and four optatives collapsed into one block. The aggregation itself is
    covered by tests/test_group_schedule.py."""

    def test_group_schedule_subgroups_tour(self):
        teacher_user = create_role_user(self, 'teacher', 'tour_teacher_subgroups')
        create_role_employee(self, teacher_user)
        level, study = create_level_study(self, 'TGSS', level={'name': 'Test Level (Subgroups Tour)'}, study={
            'code': 'TGSS001', 'name': 'Test Study (Subgroups Tour)', 'date': date.today(),
        })
        subject = self.env['ems.subject'].create({
            'code': 'TGSS001', 'acronym': 'TGSS', 'name': 'Test Subject (Subgroups Tour)',
            'study_ids': [(6, 0, [study.id])],
        })
        space = self.env['ems.space'].create({
            'code': 'TGSS-A', 'name': 'Tour Space (Subgroups)',
            'space_type_id': self.env.ref('ems.space_type_classroom').id,
            'work_location_id': self.env.ref('ems.work_location_main').id,
        })
        group = self.env['ems.group'].create({
            'course': 1, 'acronym': 'A', 'level_id': level.id, 'study_id': study.id,
            'space_id': space.id, 'shift': 'morning', 'name': 'Tour Subgroups Main',
        })

        def add_class(subgroup_name, hour_from):
            # A room of its own: two classes at the same time can't share one.
            subgroup_space = space.copy({'code': f'TGSS-{subgroup_name[-10:]}', 'name': f'Tour Space ({subgroup_name})'})
            subgroup = self.env['ems.group'].create({
                'group_type': 'reinforcement', 'name': subgroup_name, 'space_id': subgroup_space.id,
                'parent_group_ids': [(6, 0, group.ids)],
            })
            teacher = self.env['hr.employee'].create({
                'name': subgroup_name.replace('Tour', 'Tour Teacher'), 'employee_type': 'teacher',
            })
            calendar = self.env['resource.calendar'].create({'name': f'Tour Calendar ({subgroup_name})'})
            teacher.resource_calendar_id = calendar
            calendar.apply_schedule_changes([{
                'dayofweek': '0', 'hour_from': hour_from, 'hour_to': hour_from + 1, 'day_period': 'morning',
                'subject_id': subject.id, 'group_ids': [subgroup.id], 'name': 'TGSS: TGSS',
            }])

        for number in (1, 2):
            add_class(f'Tour Half {number}', 9)
        for number in (1, 2, 3, 4):
            add_class(f'Tour Optative {number}', 11)

        self.start_tour("/odoo", "ems_group_schedule_subgroups", login=teacher_user.login)
