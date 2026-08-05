from datetime import date

from odoo.tests import tagged, HttpCase

from .common import create_level_study


@tagged('post_install', '-at_install')
class TestAttendanceReportsTour(HttpCase):

    def _seed_session(self):
        level, study = create_level_study(self, 'TART', level={'name': 'Attendance Reports Tour Level'}, study={
            'name': 'Attendance Reports Tour Study',
        })
        subject = self.env['ems.subject'].create({
            'code': 'TART001', 'acronym': 'TART', 'name': 'Attendance Reports Tour Subject',
            'study_ids': [(6, 0, [study.id])],
        })
        space = self.env['ems.space'].create({
            'code': 'TART-A', 'name': 'Attendance Reports Tour Space',
            'space_type_id': self.env.ref('ems.space_type_classroom').id,
            'work_location_id': self.env.ref('ems.work_location_main').id,
        })
        admin_employee = self.env['hr.employee'].search([('user_id', '=', self.env.ref('base.user_admin').id)], limit=1)
        if not admin_employee:
            admin_employee = self.env['hr.employee'].create({
                'name': 'Attendance Reports Tour Admin Employee',
                'employee_type': 'teacher',
                'user_id': self.env.ref('base.user_admin').id,
            })
        group = self.env['ems.group'].create({
            'course': 1, 'acronym': 'TART', 'level_id': level.id, 'study_id': study.id,
            'name': 'Attendance Reports Tour Group', 'tutor_id': admin_employee.id,
        })
        self.env['ems.teaching'].create({
            'teacher_id': admin_employee.id, 'group_id': group.id, 'subject_id': subject.id,
        })
        student = self.env['res.partner'].create({
            'name': 'Attendance Reports Tour Student', 'contact_type': 'student',
            'student_email': 'attendance_reports_tour_student@example.com', 'main_group_id': group.id,
        })
        self.env['ems.enrollment'].create({
            'student_id': student.id, 'group_id': group.id, 'subject_id': subject.id,
        })
        template = self.env['ems.attendance_template'].create({
            'teacher_ids': [(6, 0, [admin_employee.id])], 'study_ids': [(6, 0, [study.id])],
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
        self.env['ems.attendance_session_line'].create({
            'attendance_session_id': session.id, 'student_id': student.id,
        })
        # A 'Miss' line (+ a strike on it) so the subject wizard tour has something to show in
        # the opt-in 'Details'/'Strikes' sections, which default to absence-category statuses.
        miss_status = self.env.ref('ems.attendance_status_miss')
        miss_line = self.env['ems.attendance_session_line'].create({
            'attendance_session_id': session.id, 'student_id': student.id, 'status_id': miss_status.id,
        })
        self.env['ems.strike'].create({
            'student_id': student.id, 'teacher_id': admin_employee.id,
            'attendance_session_line_id': miss_line.id,
        })

    def test_attendance_report_wizards_and_analysis_tour(self):
        self._seed_session()
        # step_delay: the wizard tour ends on a 'Print' click, which triggers a real report
        # download; without a delay, the harness's post-tour "no dirty form left open" check can
        # race that download and intermittently fail even though every tour step itself already
        # matched (same class of flake as TestWithdrawalTour, see that test file).
        self.start_tour("/odoo", "ems_attendance_report_wizard", login="admin", step_delay=300)
        self.start_tour("/odoo", "ems_attendance_report_analysis", login="admin", step_delay=300)
