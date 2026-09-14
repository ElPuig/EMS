# -*- coding: utf-8 -*-

from datetime import date

from odoo.tests import HttpCase, tagged

from .common import create_level_study, force_user_language_to_english


@tagged('post_install', '-at_install')
class TestEmployeeClassroomChangeTour(HttpCase):
    """Issue #444's follow-up - browser coverage for the SAME banner + wizard UI as issue #405's
    group-side flow (tests/test_group_classroom_change_tour.py), reached instead from a single
    teacher's own "Schedule" tab. Model-level behaviour (relocate_or_flag_pending, the
    generalized wizard) is already covered by tests/test_group_classroom_change.py's
    TransactionCase tests - this only proves the teacher-facing entry point actually renders and
    works in a real browser."""

    def test_employee_classroom_change_wizard_tour(self):
        force_user_language_to_english(self, self.env.ref('base.user_admin'))
        level, study = create_level_study(self, 'TECT', level={'name': 'Test Level (Employee Classroom Change Tour)'}, study={
            'code': 'TECT001', 'name': 'Test Study (Employee Classroom Change Tour)', 'date': date.today(),
        })
        subject = self.env['ems.subject'].create({
            'code': 'TECT001', 'acronym': 'TECT', 'name': 'Test Subject (Employee Classroom Change Tour)',
            'study_ids': [(6, 0, [study.id])],
        })
        old_space, new_space = self.env['ems.space'].create([{
            'code': code, 'name': name,
            'space_type_id': self.env.ref('ems.space_type_classroom').id,
            'work_location_id': self.env.ref('ems.work_location_main').id,
        } for code, name in (
            ('TECT-OLD', 'Tour Old Space (Employee Classroom Change)'),
            ('TECT-NEW', 'Tour New Space (Employee Classroom Change)'),
        )])
        teacher = self.env['hr.employee'].create({
            'name': '0000 Tour Teacher (Employee Classroom Change)', 'employee_type': 'teacher',
            'work_email': 'tour.teacher.ecc@example.com',
        })
        other_teacher = self.env['hr.employee'].create({
            'name': 'Tour Other Teacher (Employee Classroom Change)', 'employee_type': 'teacher',
            'work_email': 'tour.other.teacher.ecc@example.com',
        })
        group = self.env['ems.group'].create({
            'course': 1, 'acronym': 'A', 'level_id': level.id, 'study_id': study.id,
            'space_id': old_space.id, 'name': 'Tour Employee Classroom Change Group',
        })
        other_group = self.env['ems.group'].create({
            'course': 2, 'acronym': 'B', 'level_id': level.id, 'study_id': study.id,
            'space_id': new_space.id,
        })

        def create_synced_block(teacher_, group_, space):
            template = self.env['ems.attendance_template'].create({
                'teacher_ids': [(6, 0, [teacher_.id])], 'study_ids': [(6, 0, [study.id])],
                'subject_id': subject.id, 'group_ids': [(6, 0, [group_.id])],
                'start_date': date(2020, 1, 1), 'end_date': date(2030, 12, 31),
            })
            schedule = self.env['ems.attendance_schedule'].create({
                'attendance_template_id': template.id, 'weekday': '0',
                'start_time': 9.0, 'end_time': 10.0, 'space_id': space.id,
            })
            return self.env['resource.calendar.attendance'].create({
                'calendar_id': teacher_.resource_calendar_id.id, 'name': "%s: %s" % (teacher_.name, subject.name),
                'dayofweek': '0', 'hour_from': 9.0, 'hour_to': 10.0, 'day_period': 'morning',
                'group_ids': [group_.id], 'subject_id': subject.id, 'space_id': space.id,
                'attendance_schedule_id': schedule.id,
            }), schedule

        # The tour's own teacher already tried to move this class to 'new_space' - it collided
        # with 'other_teacher's already-active session there, so it's seeded directly as already
        # pending (the sync-time flagging itself is covered by test_attendance_template.py's
        # TestEmployeeSyncScheduleFromCalendar).
        block, _schedule = create_synced_block(teacher, group, old_space)
        block.write({'space_pending_group_sync': True, 'pending_new_space_id': new_space.id})
        create_synced_block(other_teacher, other_group, new_space)

        self.start_tour("/odoo", "ems_employee_classroom_change_wizard", login="admin")
