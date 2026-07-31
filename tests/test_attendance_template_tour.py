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

    def test_attendance_template_crud_tour(self):
        self.start_tour("/odoo", "ems_attendance_template_crud", login="admin")

        template = self.env['ems.attendance_template'].search([
            ('teacher_ids', 'in', self.teacher_employee.id),
            ('study_id', '=', self.study.id),
        ])
        self.assertEqual(len(template), 1)
        self.assertEqual(template.subject_id, self.subject)
        self.assertEqual(template.space_id, self.space)
        self.assertEqual(len(template.attendance_schedule_ids), 1)

        schedule = template.attendance_schedule_ids
        self.assertEqual(schedule.weekday, '0')
        self.assertEqual(schedule.start_time, 8.0)
        self.assertEqual(schedule.end_time, 9.0)
