from datetime import date

from odoo.tests import tagged, HttpCase

from .common import create_level_study


@tagged('post_install', '-at_install')
class TestAttendanceTemplateColorTour(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # create()/unlink() are revoked for every group on ems.attendance_template (see
        # plans/calendar_driven_attendance_templates.md, point 3) - the tour used to create a
        # fresh record through the removed "New" button; it now opens this fixture instead,
        # created via sudo() exactly like the calendar-driven sync pipeline does internally.
        level, study = create_level_study(
            cls, 'TATCT', level={'name': 'Test Level (Attendance Template Color Tour)'},
            study={'code': 'TATCT001', 'name': 'Test Study (Attendance Template Color Tour)', 'date': date.today()},
        )
        subject = cls.env['ems.subject'].create({
            'code': 'TATCT001', 'acronym': 'TATCT', 'name': 'Test Subject (Attendance Template Color Tour)',
            'study_ids': [(6, 0, [study.id])],
        })
        group = cls.env['ems.group'].create({
            'course': 1, 'acronym': 'TATCT', 'level_id': level.id, 'study_id': study.id,
        })
        space = cls.env['ems.space'].create({
            'code': 'TATCT-A', 'name': 'Test Space (Attendance Template Color Tour)',
            'space_type_id': cls.env.ref('ems.space_type_classroom').id,
            'work_location_id': cls.env.ref('ems.work_location_main').id,
        })
        teacher = cls.env['hr.employee'].create({
            'name': 'Attendance Template Color Tour Teacher', 'employee_type': 'teacher',
        })
        cls.template = cls.env['ems.attendance_template'].sudo().create({
            'teacher_ids': [(6, 0, [teacher.id])], 'study_ids': [(6, 0, [study.id])],
            'subject_id': subject.id, 'group_ids': [(6, 0, [group.id])],
            'start_date': date(2020, 1, 1), 'end_date': date(2030, 12, 31),
        })

    def test_attendance_template_list_and_form_render(self):
        # To observe this tour in a real browser during development:
        #   self.start_tour("/odoo", "ems_attendance_template_color_smoke", login="admin", watch=True)
        self.start_tour("/odoo", "ems_attendance_template_color_smoke", login="admin")
