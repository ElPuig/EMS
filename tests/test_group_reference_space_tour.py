# -*- coding: utf-8 -*-

from datetime import date

from odoo.tests import HttpCase, tagged

from .common import create_level_study, create_role_user


@tagged('post_install', '-at_install')
class TestGroupReferenceSpaceTour(HttpCase):
    """Issue #458 - browser coverage for the group's reference classroom following its tutorship's
    room, on both views of the groups action (list + form), logged in as the least-privileged role
    that manages groups (Department Chief). Model behaviour is covered by
    tests/test_group_reference_space.py."""

    def test_group_reference_space_tour(self):
        create_role_user(self, 'department_chief', 'tour_tgrs_chief')
        level, study = create_level_study(self, 'TGRST', level={'name': 'Test Level (Group Reference Space Tour)'}, study={
            'code': 'TGRST001', 'name': 'Test Study (Group Reference Space Tour)', 'date': date.today(),
        })
        tutorship = self.env['ems.subject'].create({
            'code': 'TGRST001', 'acronym': 'TGRST', 'name': 'Test Tutorship (Group Reference Space Tour)',
            'study_ids': [(6, 0, [study.id])], 'is_tutorship': True,
        })
        old_space, tutorship_space = self.env['ems.space'].create([{
            'code': code, 'name': name,
            'space_type_id': self.env.ref('ems.space_type_classroom').id,
            'work_location_id': self.env.ref('ems.work_location_main').id,
        } for code, name in (
            ('TGRST-OLD', 'Tour Old Space (Group Reference Space)'),
            ('TGRST-TUT', 'Tour Tutorship Space (Group Reference Space)'),
        )])
        teacher = self.env['hr.employee'].create({
            'name': 'Tour Teacher (Group Reference Space)', 'employee_type': 'teacher',
            'work_email': 'tour.teacher.tgrs@example.com',
        })
        group = self.env['ems.group'].create({
            'course': 1, 'acronym': 'A', 'level_id': level.id, 'study_id': study.id,
            'space_id': old_space.id, 'name': 'Tour Reference Space Group',
        })
        template = self.env['ems.attendance_template'].create({
            'teacher_ids': [(6, 0, [teacher.id])], 'study_ids': [(6, 0, [study.id])],
            'subject_id': tutorship.id, 'group_ids': [(6, 0, [group.id])],
            'start_date': date(2020, 1, 1), 'end_date': date(2030, 12, 31),
        })
        schedule = self.env['ems.attendance_schedule'].create({
            'attendance_template_id': template.id, 'weekday': '0',
            'start_time': 9.0, 'end_time': 10.0, 'space_id': tutorship_space.id,
        })
        self.env['resource.calendar.attendance'].create({
            'calendar_id': teacher.resource_calendar_id.id, 'name': f"{teacher.name}: {tutorship.name}",
            'dayofweek': '0', 'hour_from': 9.0, 'hour_to': 10.0, 'day_period': 'morning',
            'group_ids': [group.id], 'subject_id': tutorship.id, 'space_id': tutorship_space.id,
            'attendance_schedule_id': schedule.id,
        })

        self.start_tour("/odoo", "ems_group_reference_space", login="tour_tgrs_chief")
