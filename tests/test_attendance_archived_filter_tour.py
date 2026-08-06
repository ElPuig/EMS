from datetime import date

from odoo.tests.common import HttpCase, tagged

from .common import create_level_study_group


@tagged('post_install', '-at_install')
class TestAttendanceArchivedFilterTour(HttpCase):
    """Phase 8 of plans/course_transition_teacher_schedule_archival.md: an explicit 'show
    archived' affordance for ems.attendance_template/resource.calendar/ems.attendance_session_header,
    plus the new employee_id/course_id-based grouping on resource.calendar."""

    def test_attendance_template_archived_filter_tour(self):
        level, study, group = create_level_study_group(self, 'TAAFT1')
        subject = self.env['ems.subject'].create({
            'code': 'TAAFT1', 'acronym': 'TAAFT1', 'name': 'Tour Archived Template',
            'study_ids': [(6, 0, [study.id])],
        })
        space = self.env['ems.space'].create({
            'code': 'TAAFT1-A', 'name': 'Test Space (Archived Filter Tour)',
            'space_type_id': self.env.ref('ems.space_type_classroom').id,
            'work_location_id': self.env.ref('ems.work_location_main').id,
        })
        teacher = self.env['hr.employee'].create({
            'name': 'Test Teacher (Archived Filter Tour)', 'employee_type': 'teacher',
        })
        template = self.env['ems.attendance_template'].create({
            'teacher_ids': [(6, 0, [teacher.id])], 'study_ids': [(6, 0, [study.id])],
            'subject_id': subject.id, 'group_ids': [(6, 0, [group.id])], 'space_id': space.id,
            'start_date': date(2020, 1, 1), 'end_date': date(2030, 12, 31),
        })
        template.action_archive()

        self.start_tour("/odoo", "ems_attendance_template_archived_filter", login="admin")

    def test_attendance_session_archived_filter_tour(self):
        level, study, group = create_level_study_group(self, 'TAAFT2')
        subject = self.env['ems.subject'].create({
            'code': 'TAAFT2', 'acronym': 'TAAFT2', 'name': 'Test Subject (Archived Filter Tour)',
            'study_ids': [(6, 0, [study.id])],
        })
        space = self.env['ems.space'].create({
            'code': 'TAAFT2-A', 'name': 'Test Space (Archived Filter Tour)',
            'space_type_id': self.env.ref('ems.space_type_classroom').id,
            'work_location_id': self.env.ref('ems.work_location_main').id,
        })
        teacher = self.env['hr.employee'].create({
            'name': 'Tour Archived Session Teacher', 'employee_type': 'teacher',
        })
        template = self.env['ems.attendance_template'].create({
            'teacher_ids': [(6, 0, [teacher.id])], 'study_ids': [(6, 0, [study.id])],
            'subject_id': subject.id, 'group_ids': [(6, 0, [group.id])], 'space_id': space.id,
            'start_date': date(2020, 1, 1), 'end_date': date(2030, 12, 31),
        })
        schedule = self.env['ems.attendance_schedule'].create({
            'attendance_template_id': template.id, 'weekday': '0',
            'start_time': 8.0, 'end_time': 9.0, 'space_id': space.id,
        })
        session = self.env['ems.attendance_session_header'].create({
            'attendance_schedule_id': schedule.id, 'date': date(2026, 1, 5),
            'mode': 'scheduled', 'session_teacher_id': teacher.id,
        })
        session.action_archive()

        self.start_tour("/odoo", "ems_attendance_session_archived_filter", login="admin")

    def test_working_schedule_course_grouping_tour(self):
        course = self.env['ems.course'].create({'start': 2199, 'end': 2200})
        teacher = self.env['hr.employee'].create({
            'name': 'Test Teacher (Working Schedule Grouping Tour)', 'employee_type': 'teacher',
        })
        teacher.resource_calendar_id.course_id = course.id

        self.start_tour("/odoo", "ems_working_schedule_course_grouping", login="admin")
