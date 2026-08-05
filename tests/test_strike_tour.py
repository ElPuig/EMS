from datetime import date

from odoo.tests import tagged, HttpCase

from .common import create_level_study, mock_outgoing_email


@tagged('post_install', '-at_install')
class TestStrikeTour(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # See tests/test_strike.py: neutralize real SMTP delivery — this environment has
        # real, credentialed outgoing mail servers configured (AWS SES / Gmail), and the
        # tour issues a real ems.strike (force_send=True on create()).
        mock_outgoing_email(cls)

    def _seed_session(self):
        level, study = create_level_study(self, 'TSTR', level={'name': 'Test Level (Strike Tour)'}, study={
            'code': 'TSTR001', 'name': 'Test Study (Strike Tour)', 'date': date.today(),
        })
        subject = self.env['ems.subject'].create({
            'code': 'TSTR001', 'acronym': 'TSTR', 'name': 'Test Subject (Strike Tour)',
            'study_ids': [(6, 0, [study.id])],
        })
        group = self.env['ems.group'].create({
            'course': 1, 'acronym': 'STR', 'level_id': level.id, 'study_id': study.id,
            'name': 'Strike Tour Group',
        })
        space = self.env['ems.space'].create({
            'code': 'TSTR-A', 'name': 'Test Space (Strike Tour)',
            'space_type_id': self.env.ref('ems.space_type_classroom').id,
            'work_location_id': self.env.ref('ems.work_location_main').id,
        })
        admin_employee = self.env['hr.employee'].search([('user_id', '=', self.env.ref('base.user_admin').id)], limit=1)
        if not admin_employee:
            admin_employee = self.env['hr.employee'].create({
                'name': 'Test Admin Employee (Strike Tour)',
                'employee_type': 'teacher',
                'user_id': self.env.ref('base.user_admin').id,
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
        student = self.env['res.partner'].create({
            'name': 'Strike Tour Student', 'contact_type': 'student',
            'student_email': 'strike_tour_student@example.com', 'main_group_id': group.id,
        })
        self.env['ems.attendance_session_line'].create({
            'attendance_session_id': session.id, 'student_id': student.id,
        })

    def test_strike_issue_and_consult_tour(self):
        self._seed_session()
        # To observe these tours in a real browser during development:
        #   self.start_tour("/odoo", "ems_strike_issue", login="admin", watch=True)
        self.start_tour("/odoo", "ems_strike_issue", login="admin")
        self.start_tour("/odoo", "ems_strike_consult", login="admin")
        self.start_tour("/odoo", "ems_strike_session_history", login="admin")
        self.start_tour("/odoo", "ems_strike_partner_stat_button", login="admin")
