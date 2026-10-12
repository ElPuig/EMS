from datetime import date

from odoo.tests import HttpCase, tagged

from .common import create_level_study, create_role_employee, create_role_user


@tagged('post_install', '-at_install')
class TestNoticeDepartmentChiefTour(HttpCase):
    """Department and Seminar chiefs reach Communications > Notices, limited to the groups their
    department teaches (see models/communications/notice_department_scope.py)."""

    def test_notice_department_chief_tour(self):
        chief_user = create_role_user(self, 'department_chief', 'notice_department_chief_tour',
                                      email='notice.chief@example.com')
        chief = create_role_employee(self, chief_user)
        department = self.env['hr.department'].create({'name': 'Tour Notice Department', 'manager_id': chief.id})
        teacher = self.env['hr.employee'].create({
            'name': 'Tour Notice Department Teacher', 'employee_type': 'teacher', 'department_id': department.id})
        level, study = create_level_study(self, 'TNDC', level={'name': 'Tour Notice Department Level'}, study={
            'code': 'TNDC001', 'name': 'Tour Notice Department Study', 'date': date.today()})
        subject = self.env['ems.subject'].create({
            'code': 'TNDC001', 'acronym': 'TNDC', 'name': 'Tour Notice Department Subject',
            'study_ids': [(6, 0, [study.id])]})
        taught, other = (self.env['ems.group'].create({
            'course': 1, 'acronym': acronym, 'level_id': level.id, 'study_id': study.id, 'shift': 'morning',
        }) for acronym in ('TNDCA', 'TNDCB'))
        self.env['ems.teaching'].create({'teacher_id': teacher.id, 'group_id': taught.id, 'subject_id': subject.id})

        self.start_tour("/odoo", "ems_notice_department_chief", login=chief_user.login)

        notice = self.env['ems.notice'].search([('subject', '=', 'Department notice')])
        self.assertEqual(notice.group_ids, taught)
        self.assertEqual(notice.create_uid, chief_user)
