from odoo.tests import HttpCase, tagged

from .common import create_role_employee, create_role_user


@tagged('post_install', '-at_install')
class TestDepartmentJobTour(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        user = create_role_user(cls, 'secretary', 'dept_job_secretary', name='Dept Job Secretary')
        create_role_employee(cls, user, employee_type='asp', name='Dept Job Secretary')
        job = cls.env['hr.job'].create({'name': 'Tour job 815', 'employee_type': 'asp'})
        area = cls.env['hr.department'].create({'name': 'Tour ASP area', 'is_top_level': True, 'top_level_area': 'asp'})
        cls.department = cls.env['hr.department'].create({
            'name': 'Tour ASP department', 'parent_id': area.id, 'shares_manager_with_parent': True, 'job_id': job.id})
        cls.employee = cls.env['hr.employee'].create({
            'name': 'Tour ASP employee', 'employee_type': 'asp', 'department_id': cls.department.id})

    def test_employee_form_hides_job_position(self):
        self.start_tour(f"/odoo/action-hr.open_view_employee_list_my/{self.employee.id}",
                        "ems_department_job_employee", login='dept_job_secretary')

    def test_department_form_shows_job_position(self):
        self.start_tour(f"/odoo/action-ems.action_department_tree/{self.department.id}",
                        "ems_department_job_department", login='dept_job_secretary')
