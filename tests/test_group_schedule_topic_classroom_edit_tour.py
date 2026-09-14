# -*- coding: utf-8 -*-

from datetime import date

from odoo.tests import HttpCase, tagged

from .common import create_level_study, force_user_language_to_english


@tagged('post_install', '-at_install')
class TestGroupScheduleTopicClassroomEditTour(HttpCase):
    """Issue #446 - browser coverage for editing a teaching block's topic/classroom directly from
    the group's own Schedule tab. Model-level behaviour (update_topic_and_relocate, reusing the
    pre-existing relocate_or_flag_pending/pending-classroom wizard) is already covered by
    tests/test_group_schedule.py's TransactionCase tests - this only proves the group form's own
    inline edit affordance actually renders and works in a real browser, on both the plain-save
    and the collision paths."""

    def test_group_schedule_topic_classroom_edit_tour(self):
        force_user_language_to_english(self, self.env.ref('base.user_admin'))
        level, study = create_level_study(self, 'TGSE', level={'name': 'Test Level (Group Schedule Edit Tour)'}, study={
            'code': 'TGSE001', 'name': 'Test Study (Group Schedule Edit Tour)', 'date': date.today(),
        })
        subject = self.env['ems.subject'].create({
            'code': 'TGSE001', 'acronym': 'TGSE', 'name': 'Test Subject (Group Schedule Edit Tour)',
            'study_ids': [(6, 0, [study.id])],
        })
        old_space, free_space, colliding_space = self.env['ems.space'].create([{
            'code': code, 'name': name,
            'space_type_id': self.env.ref('ems.space_type_classroom').id,
            'work_location_id': self.env.ref('ems.work_location_main').id,
        } for code, name in (
            ('TGSE-OLD', 'Tour Old Space (Schedule Edit)'),
            ('TGSE-FREE', 'Tour Free Space (Schedule Edit)'),
            ('TGSE-COLL', 'Tour Colliding Space (Schedule Edit)'),
        )])
        teacher = self.env['hr.employee'].create({
            'name': 'Tour Teacher (Group Schedule Edit)', 'employee_type': 'teacher',
            'work_email': 'tour.teacher.gse@example.com',
        })
        other_teacher = self.env['hr.employee'].create({
            'name': 'Tour Other Teacher (Group Schedule Edit)', 'employee_type': 'teacher',
            'work_email': 'tour.other.teacher.gse@example.com',
        })
        group = self.env['ems.group'].create({
            'course': 1, 'acronym': 'A', 'level_id': level.id, 'study_id': study.id,
            'space_id': old_space.id, 'name': 'Tour Schedule Edit Group',
        })
        other_group = self.env['ems.group'].create({
            'course': 2, 'acronym': 'B', 'level_id': level.id, 'study_id': study.id,
            'space_id': colliding_space.id,
        })

        def create_synced_block(teacher_, group_, space, weekday='0'):
            template = self.env['ems.attendance_template'].create({
                'teacher_ids': [(6, 0, [teacher_.id])], 'study_ids': [(6, 0, [study.id])],
                'subject_id': subject.id, 'group_ids': [(6, 0, [group_.id])],
                'start_date': date(2020, 1, 1), 'end_date': date(2030, 12, 31),
            })
            schedule = self.env['ems.attendance_schedule'].create({
                'attendance_template_id': template.id, 'weekday': weekday,
                'start_time': 9.0, 'end_time': 10.0, 'space_id': space.id,
            })
            return self.env['resource.calendar.attendance'].create({
                'calendar_id': teacher_.resource_calendar_id.id, 'name': "%s: %s" % (teacher_.name, subject.name),
                'dayofweek': weekday, 'hour_from': 9.0, 'hour_to': 10.0, 'day_period': 'morning',
                'group_ids': [group_.id], 'subject_id': subject.id, 'space_id': space.id,
                'attendance_schedule_id': schedule.id,
            })

        create_synced_block(teacher, group, old_space)
        # An already-active session in the room the tour will later try (and fail) to move into.
        create_synced_block(other_teacher, other_group, colliding_space)

        self.start_tour("/odoo", "ems_group_schedule_topic_classroom_edit", login="admin")
