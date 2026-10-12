from datetime import datetime, timedelta

from odoo.tests import HttpCase, tagged

from .common import create_head_of_studies_branch, create_role_employee, create_role_user


@tagged('post_install', '-at_install')
class TestEmployeeAttendanceListTour(HttpCase):
    """Issue #543 - the staff's own attendance list opens flat for a plain employee (who only sees
    their own, and comes to pick one and request a correction) and grouped from Department Chief
    up, who see their chain of command's. Access itself is covered by
    test_employee_attendance_access.py."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.teacher_user = create_role_user(cls, 'teacher', 'test_teacher_tealt', name='TEALT Teacher')
        teacher = create_role_employee(cls, cls.teacher_user)
        create_head_of_studies_branch(cls, 'TEALT', teacher)
        now = datetime.now().replace(microsecond=0)
        cls.env['hr.attendance'].create({
            'employee_id': teacher.id, 'check_in': now - timedelta(hours=3), 'check_out': now - timedelta(hours=1)})

    def test_an_employee_gets_a_flat_list(self):
        self.start_tour("/odoo", "ems_employee_attendance_list_employee", login=self.teacher_user.login)

    def test_a_department_chief_gets_it_grouped(self):
        self.start_tour("/odoo", "ems_employee_attendance_list_chief", login=self.department_chief.login)
