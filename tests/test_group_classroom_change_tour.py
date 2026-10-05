# -*- coding: utf-8 -*-

from datetime import date

from odoo.tests import HttpCase, tagged

from .common import create_level_study, force_user_language_to_english


@tagged('post_install', '-at_install')
class TestGroupClassroomChangeTour(HttpCase):
    """Issue #405 - browser coverage for the banner + wizard UI on top of the write()/model
    behaviour already covered by tests/test_group_classroom_change.py's TransactionCase tests."""

    def test_group_classroom_change_wizard_tour(self):
        force_user_language_to_english(self, self.env.ref('base.user_admin'))
        level, study = create_level_study(self, 'TGCT', level={'name': 'Test Level (Group Classroom Change Tour)'}, study={
            'code': 'TGCT001', 'name': 'Test Study (Group Classroom Change Tour)', 'date': date.today(),
        })
        subject = self.env['ems.subject'].create({
            'code': 'TGCT001', 'acronym': 'TGCT', 'name': 'Test Subject (Group Classroom Change Tour)',
            'study_ids': [(6, 0, [study.id])],
        })
        old_space, new_space, third_space = self.env['ems.space'].create([{
            'code': code, 'name': name,
            'space_type_id': self.env.ref('ems.space_type_classroom').id,
            'work_location_id': self.env.ref('ems.work_location_main').id,
        } for code, name in (
            ('TGCT-OLD', 'Tour Old Space'),
            ('TGCT-NEW', 'Tour New Space'),
            ('TGCT-3RD', 'Tour Third Space'),
        )])
        teacher = self.env['hr.employee'].create({
            'name': 'Tour Teacher (Group Classroom Change)', 'employee_type': 'teacher',
            'work_email': 'tour.teacher.gcc@example.com',
        })
        other_teacher = self.env['hr.employee'].create({
            'name': 'Tour Other Teacher (Group Classroom Change)', 'employee_type': 'teacher',
            'work_email': 'tour.other.teacher.gcc@example.com',
        })
        group = self.env['ems.group'].create({
            'course': 1, 'acronym': 'A', 'level_id': level.id, 'study_id': study.id,
            'space_id': old_space.id, 'name': 'Tour Classroom Change Group',
        })
        other_group = self.env['ems.group'].create({
            'course': 2, 'acronym': 'B', 'level_id': level.id, 'study_id': study.id,
            'space_id': new_space.id,
        })

        templates = {}

        def create_synced_block(teacher_, group_, space, weekday='0'):
            # One 'ems.attendance_template' per (teacher, subject, group) - its own uniqueness
            # constraint rejects a second one for the exact same assignment, even at a different
            # weekday (a single template carries every weekday's schedule line as its own child).
            key = (teacher_.id, group_.id)
            template = templates.get(key)
            if not template:
                template = self.env['ems.attendance_template'].create({
                    'teacher_ids': [(6, 0, [teacher_.id])], 'study_ids': [(6, 0, [study.id])],
                    'subject_id': subject.id, 'group_ids': [(6, 0, [group_.id])],
                    'start_date': date(2020, 1, 1), 'end_date': date(2030, 12, 31),
                })
                templates[key] = template
            schedule = self.env['ems.attendance_schedule'].create({
                'attendance_template_id': template.id, 'weekday': weekday,
                'start_time': 9.0, 'end_time': 10.0, 'space_id': space.id,
            })
            return self.env['resource.calendar.attendance'].create({
                'calendar_id': teacher_.resource_calendar_id.id, 'name': "%s: %s" % (teacher_.name, subject.name),
                'dayofweek': weekday, 'hour_from': 9.0, 'hour_to': 10.0, 'day_period': 'morning',
                'group_ids': [group_.id], 'subject_id': subject.id, 'space_id': space.id,
                'attendance_schedule_id': schedule.id,
            }), schedule

        # Two blocks for the SAME teacher/subject (different weekdays), each colliding with its own
        # already-active session in 'new_space' - lands in the same card sub-group (grouped by
        # teacher+subject), so the tour can exercise the bulk classroom picker added to that
        # sub-group's header, not just the per-row one. The group's classroom is then moved to
        # 'new_space' through a real write(), so both blocks get flagged pending exactly as in
        # production (issue #458: seeding them in 'old_space' while the group already says
        # 'new_space' would make the group's reference classroom follow them back to 'old_space').
        block_monday, _schedule_monday = create_synced_block(teacher, group, old_space, weekday='0')
        block_tuesday, _schedule_tuesday = create_synced_block(teacher, group, old_space, weekday='1')
        create_synced_block(other_teacher, other_group, new_space, weekday='0')
        create_synced_block(other_teacher, other_group, new_space, weekday='1')
        group.space_id = new_space
        self.assertTrue(all((block_monday + block_tuesday).mapped('space_pending_group_sync')))
        self.assertEqual(group.space_id, new_space)

        self.start_tour("/odoo", "ems_group_classroom_change_wizard", login="admin")
