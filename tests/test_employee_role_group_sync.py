from odoo.tests.common import TransactionCase


class TestEmployeeRoleGroupSync(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test HOS User',
            'login': 'test_hos_user',
        })
        cls.employee = cls.env['hr.employee'].create({
            'name': 'Test HOS Employee',
            'employee_type': 'teacher',
            'user_id': cls.user.id,
        })
        cls.asp_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test ASP User',
            'login': 'test_asp_user',
        })
        cls.asp_employee = cls.env['hr.employee'].create({
            'name': 'Test ASP Employee',
            'employee_type': 'asp',
            'user_id': cls.asp_user.id,
        })
        cls.role_hos = cls.env.ref('ems.role_hos')
        cls.role_dhos = cls.env.ref('ems.role_dhos')
        cls.role_director = cls.env.ref('ems.role_director')
        cls.role_dchieff = cls.env.ref('ems.role_dchieff')
        cls.role_secretary = cls.env.ref('ems.role_secretary')
        cls.role_secretary_admin = cls.env.ref('ems.role_secretary_admin')
        cls.role_quality = cls.env.ref('ems.role_quality')
        cls.job_secretary = cls.env.ref('ems.job_secretary')
        cls.group_teacher = cls.env.ref('ems.group_teacher')
        cls.group_department_chief = cls.env.ref('ems.group_department_chief')
        cls.group_head_of_studies = cls.env.ref('ems.group_head_of_studies')
        cls.group_director = cls.env.ref('ems.group_director')
        cls.group_secretary = cls.env.ref('ems.group_secretary')
        cls.group_secretary_admin = cls.env.ref('ems.group_secretary_admin')
        cls.group_quality_admin = cls.env.ref('ems.group_quality_admin')
        cls.group_hr_attendance_manager = cls.env.ref('hr_attendance.group_hr_attendance_manager')
        # These roles are unipersonal and may already be assigned to a real employee
        # in the working database; clear them so the tests are self-contained.
        unipersonal_roles = (
            cls.role_hos + cls.role_dhos + cls.role_director
            + cls.role_secretary_admin + cls.role_quality + cls.role_secretary
        )
        unipersonal_roles.sudo().write({'employee_ids': [(5, 0, 0)]})

    def test_assign_role_hos_adds_group(self):
        self.employee.write({'role_ids': [(4, self.role_hos.id)]})
        self.assertIn(self.group_head_of_studies, self.user.groups_id)

    def test_unassign_role_hos_removes_group(self):
        self.employee.write({'role_ids': [(4, self.role_hos.id)]})
        self.employee.write({'role_ids': [(3, self.role_hos.id)]})
        self.assertNotIn(self.group_head_of_studies, self.user.groups_id)

    def test_assign_role_hos_adds_implied_external_group(self):
        self.employee.write({'role_ids': [(4, self.role_hos.id)]})
        self.assertIn(self.group_hr_attendance_manager, self.user.groups_id)

    def test_unassign_role_hos_removes_implied_external_group(self):
        self.employee.write({'role_ids': [(4, self.role_hos.id)]})
        self.employee.write({'role_ids': [(3, self.role_hos.id)]})
        self.assertNotIn(self.group_head_of_studies, self.user.groups_id)
        self.assertNotIn(self.group_hr_attendance_manager, self.user.groups_id)

    def test_direct_groups_id_write_demote_removes_implied_external_group(self):
        # Simulates the Users form's Academic reified selector / raw debug-mode
        # m2m edit: Teacher -> Head of Studies -> Teacher, entirely via
        # res.users.groups_id, bypassing hr.employee/role_ids altogether.
        self.user.write({'groups_id': [(4, self.group_head_of_studies.id)]})
        self.assertIn(self.group_hr_attendance_manager, self.user.groups_id)
        self.user.write({
            'groups_id': [(3, self.group_head_of_studies.id), (4, self.group_teacher.id)],
        })
        self.assertNotIn(self.group_head_of_studies, self.user.groups_id)
        self.assertNotIn(self.group_hr_attendance_manager, self.user.groups_id)

    def test_manual_external_group_kept_when_unrelated_to_ems(self):
        # Documents the accepted limitation: a group manually granted for an
        # exceptional reason, unrelated to any EMS group the user held, is not
        # touched by the sync even if it happens to be implied by an EMS group
        # elsewhere in the system - the fix only revokes groups that were
        # justified by an EMS group *this user* is losing in *this* write.
        self.employee.write({'role_ids': [(4, self.role_secretary.id)]})
        self.user.write({'groups_id': [(4, self.group_hr_attendance_manager.id)]})
        self.employee.write({'role_ids': [(3, self.role_secretary.id)]})
        self.assertIn(self.group_hr_attendance_manager, self.user.groups_id)

    def test_assign_role_dhos_adds_group(self):
        self.employee.write({'role_ids': [(4, self.role_dhos.id)]})
        self.assertIn(self.group_head_of_studies, self.user.groups_id)

    def test_unassign_role_dhos_removes_group(self):
        self.employee.write({'role_ids': [(4, self.role_dhos.id)]})
        self.employee.write({'role_ids': [(3, self.role_dhos.id)]})
        self.assertNotIn(self.group_head_of_studies, self.user.groups_id)

    def test_assign_role_director_adds_group(self):
        self.employee.write({'role_ids': [(4, self.role_director.id)]})
        self.assertIn(self.group_director, self.user.groups_id)

    def test_unassign_role_director_removes_group(self):
        self.employee.write({'role_ids': [(4, self.role_director.id)]})
        self.employee.write({'role_ids': [(3, self.role_director.id)]})
        self.assertNotIn(self.group_director, self.user.groups_id)

    def test_assign_role_dchieff_adds_group(self):
        self.employee.write({'role_ids': [(4, self.role_dchieff.id)]})
        self.assertIn(self.group_department_chief, self.user.groups_id)

    def test_unassign_role_dchieff_removes_group(self):
        self.employee.write({'role_ids': [(4, self.role_dchieff.id)]})
        self.employee.write({'role_ids': [(3, self.role_dchieff.id)]})
        self.assertNotIn(self.group_department_chief, self.user.groups_id)

    def test_assign_role_secretary_adds_group(self):
        self.employee.write({'role_ids': [(4, self.role_secretary.id)]})
        self.assertIn(self.group_secretary, self.user.groups_id)

    def test_unassign_role_secretary_removes_group(self):
        self.employee.write({'role_ids': [(4, self.role_secretary.id)]})
        self.employee.write({'role_ids': [(3, self.role_secretary.id)]})
        self.assertNotIn(self.group_secretary, self.user.groups_id)

    def test_assign_role_secretary_admin_adds_group(self):
        self.asp_employee.write({'role_ids': [(4, self.role_secretary_admin.id)]})
        self.assertIn(self.group_secretary_admin, self.asp_user.groups_id)

    def test_unassign_role_secretary_admin_removes_group(self):
        self.asp_employee.write({'role_ids': [(4, self.role_secretary_admin.id)]})
        self.asp_employee.write({'role_ids': [(3, self.role_secretary_admin.id)]})
        self.assertNotIn(self.group_secretary_admin, self.asp_user.groups_id)

    def test_assign_role_quality_adds_group(self):
        self.employee.write({'role_ids': [(4, self.role_quality.id)]})
        self.assertIn(self.group_quality_admin, self.user.groups_id)

    def test_unassign_role_quality_removes_group(self):
        self.employee.write({'role_ids': [(4, self.role_quality.id)]})
        self.employee.write({'role_ids': [(3, self.role_quality.id)]})
        self.assertNotIn(self.group_quality_admin, self.user.groups_id)

    def test_assign_job_secretary_adds_group(self):
        self.asp_employee.write({'job_id': self.job_secretary.id})
        self.assertIn(self.group_secretary, self.asp_user.groups_id)

    def test_unassign_job_secretary_removes_group(self):
        self.asp_employee.write({'job_id': self.job_secretary.id})
        self.asp_employee.write({'job_id': False})
        self.assertNotIn(self.group_secretary, self.asp_user.groups_id)
