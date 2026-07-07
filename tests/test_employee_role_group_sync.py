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
        cls.role_hos = cls.env.ref('ems.role_hos')
        cls.role_dhos = cls.env.ref('ems.role_dhos')
        cls.group_head_of_studies = cls.env.ref('ems.group_head_of_studies')
        # These roles are unipersonal and may already be assigned to a real employee
        # in the working database; clear them so the tests are self-contained.
        (cls.role_hos + cls.role_dhos).sudo().write({'employee_ids': [(5, 0, 0)]})

    def test_assign_role_hos_adds_group(self):
        self.employee.write({'role_ids': [(4, self.role_hos.id)]})
        self.assertIn(self.group_head_of_studies, self.user.groups_id)

    def test_unassign_role_hos_removes_group(self):
        self.employee.write({'role_ids': [(4, self.role_hos.id)]})
        self.employee.write({'role_ids': [(3, self.role_hos.id)]})
        self.assertNotIn(self.group_head_of_studies, self.user.groups_id)

    def test_assign_role_dhos_adds_group(self):
        self.employee.write({'role_ids': [(4, self.role_dhos.id)]})
        self.assertIn(self.group_head_of_studies, self.user.groups_id)

    def test_unassign_role_dhos_removes_group(self):
        self.employee.write({'role_ids': [(4, self.role_dhos.id)]})
        self.employee.write({'role_ids': [(3, self.role_dhos.id)]})
        self.assertNotIn(self.group_head_of_studies, self.user.groups_id)
