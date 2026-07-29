from datetime import date

from odoo.tests import tagged, HttpCase

from .common import create_level_study


@tagged('post_install', '-at_install')
class TestAttendanceStatusTour(HttpCase):

    def _seed_session(self):
        level, study = create_level_study(self, 'TAST', level={'name': 'Test Level (Attendance Status Tour)'}, study={
            'code': 'TAST001', 'name': 'Test Study (Attendance Status Tour)', 'date': date.today(),
        })
        subject = self.env['ems.subject'].create({
            'code': 'TAST001', 'acronym': 'TAST', 'name': 'Test Subject (Attendance Status Tour)',
            'study_ids': [(6, 0, [study.id])],
        })
        group = self.env['ems.group'].create({
            'course': 1, 'acronym': 'AST', 'level_id': level.id, 'study_id': study.id,
            'name': 'Attendance Status Tour Group',
        })
        space = self.env['ems.space'].create({
            'code': 'TAST-A', 'name': 'Test Space (Attendance Status Tour)',
            'space_type_id': self.env.ref('ems.space_type_classroom').id,
            'work_location_id': self.env.ref('ems.work_location_main').id,
        })
        admin_employee = self.env['hr.employee'].search([('user_id', '=', self.env.ref('base.user_admin').id)], limit=1)
        if not admin_employee:
            admin_employee = self.env['hr.employee'].create({
                'name': 'Test Admin Employee (Attendance Status Tour)',
                'employee_type': 'teacher',
                'user_id': self.env.ref('base.user_admin').id,
            })
        template = self.env['ems.attendance_template'].create({
            'teacher_ids': [(6, 0, [admin_employee.id])], 'level_id': level.id, 'study_id': study.id,
            'subject_id': subject.id, 'group_ids': [(6, 0, [group.id])], 'space_id': space.id,
            'start_date': date(2020, 1, 1), 'end_date': date(2030, 12, 31),
        })
        schedule = self.env['ems.attendance_schedule'].create({
            'attendance_template_id': template.id, 'weekday': str(date.today().weekday()),
            'start_time': 0.0, 'end_time': 23.0, 'space_id': space.id,
        })
        session = self.env['ems.attendance_session_header'].create({
            'attendance_schedule_id': schedule.id, 'date': date.today(),
            'mode': 'manual', 'session_teacher_id': admin_employee.id,
        })
        student = self.env['res.partner'].create({
            'name': 'Attendance Status Tour Student', 'contact_type': 'student',
            'student_email': 'attendance_status_tour_student@example.com', 'main_group_id': group.id,
        })
        self.env['ems.attendance_session_line'].create({
            'attendance_session_id': session.id, 'student_id': student.id,
        })

    def test_attendance_status_configuration_and_passlist_tour(self):
        self._seed_session()
        self.start_tour("/odoo", "ems_attendance_status_configuration", login="admin")
        self.start_tour("/odoo", "ems_attendance_status_passlist", login="admin")
