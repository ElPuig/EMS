from datetime import date

from odoo.tests.common import HttpCase, tagged

from .common import create_level_study


@tagged('post_install', '-at_install')
class TestAttendanceTemplateTour(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.level, cls.study = create_level_study(
            cls, 'TATTT',
            level={'name': 'Test Level (Attendance Template Tour)'},
            study={'code': 'TATTT001', 'name': 'Test Study (Attendance Template Tour)', 'date': date.today()},
        )
        cls.subject = cls.env['ems.subject'].create({
            'code': 'TATTT001', 'acronym': 'TATTT', 'name': 'Test Subject (Attendance Template Tour)',
            'study_ids': [(6, 0, [cls.study.id])],
        })
        cls.group = cls.env['ems.group'].create({
            'course': 1, 'acronym': 'TATTT', 'level_id': cls.level.id, 'study_id': cls.study.id,
            'name': 'Attendance Template Tour Group',
        })
        cls.space = cls.env['ems.space'].create({
            'code': 'TATTT-A', 'name': 'Test Space (Attendance Template Tour)',
            'space_type_id': cls.env.ref('ems.space_type_classroom').id,
            'work_location_id': cls.env.ref('ems.work_location_main').id,
        })
        cls.teacher_employee = cls.env['hr.employee'].create({
            'name': 'Attendance Template Tour Teacher', 'employee_type': 'teacher',
        })
        # create()/unlink() are revoked for every group on ems.attendance_template (see
        # plans/calendar_driven_attendance_templates.md, point 3) - a template only ever comes
        # from the calendar-driven sync pipeline now, never a direct UI create, so this tour can
        # no longer build one through the "New" button (removed). sudo() here mirrors exactly what
        # that pipeline itself does internally (ems.attendance_template.sync_from_schedule_batch*),
        # not a workaround - this fixture stands in for "a template the sync pipeline already
        # produced", which is the only way one can exist.
        cls.template = cls.env['ems.attendance_template'].sudo().create({
            'teacher_ids': [(6, 0, [cls.teacher_employee.id])],
            'study_ids': [(6, 0, [cls.study.id])],
            'subject_id': cls.subject.id,
            'group_ids': [(6, 0, [cls.group.id])],
            'space_id': cls.space.id,
            'start_date': date(2020, 1, 1), 'end_date': date(2030, 12, 31),
        })
        cls.schedule = cls.env['ems.attendance_schedule'].create({
            'attendance_template_id': cls.template.id,
            'weekday': '0', 'start_time': 8.0, 'end_time': 9.0, 'space_id': cls.space.id,
        })

    def test_attendance_template_crud_tour(self):
        self.start_tour("/odoo", "ems_attendance_template_view_tour", login="admin")
