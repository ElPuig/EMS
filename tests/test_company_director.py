from odoo.tests.common import TransactionCase


class TestCompanyDirector(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.role_director = cls.env.ref('ems.role_director')
        cls.group_director = cls.env.ref('ems.group_director')
        role_hos = cls.env.ref('ems.role_hos')
        role_dhos = cls.env.ref('ems.role_dhos')
        # role_director/role_hos/role_dhos are unipersonal and may already be assigned to a
        # real employee in the working database; clear them so the tests are self-contained.
        (cls.role_director + role_hos + role_dhos).sudo().write({'employee_ids': [(5, 0, 0)]})

    def _create_employee(self, name, department=False, with_user=False):
        vals = {'name': name, 'employee_type': 'teacher'}
        if department:
            vals['department_id'] = department.id
        if with_user:
            user = self.env['res.users'].with_context(no_reset_password=True).create({
                'name': name, 'login': name.lower().replace(' ', '_'),
            })
            vals['user_id'] = user.id
        return self.env['hr.employee'].create(vals)

    def test_setting_director_grants_role_and_group(self):
        director = self._create_employee('Test Director (Grant)', with_user=True)

        self.env.company.director_id = director.id

        self.assertIn(self.role_director, director.role_ids)
        self.assertIn(self.group_director, director.user_id.groups_id)

    def test_clearing_director_revokes_role_and_group(self):
        director = self._create_employee('Test Director (Revoke)', with_user=True)
        self.env.company.director_id = director.id

        self.env.company.director_id = False

        self.assertNotIn(self.role_director, director.role_ids)
        self.assertNotIn(self.group_director, director.user_id.groups_id)

    def test_reassigning_director_demotes_old_director(self):
        old_director = self._create_employee('Test Old Director (Reassign)', with_user=True)
        self.env.company.director_id = old_director.id
        new_director = self._create_employee('Test New Director (Reassign)', with_user=True)

        self.env.company.director_id = new_director.id

        self.assertNotIn(self.role_director, old_director.role_ids)
        self.assertIn(self.role_director, new_director.role_ids)

    def test_top_level_manager_gets_director_as_manager(self):
        director = self._create_employee('Test Director (Top Level Manager)')
        head = self._create_employee('Test Head (Top Level Manager)')
        self.env['hr.department'].create({
            'name': 'Test VET (Top Level Manager)', 'is_top_level': True, 'top_level_area': 'academic', 'top_level_role': 'hos', 'manager_id': head.id,
        })

        self.env.company.director_id = director.id

        self.assertEqual(head.parent_id, director)

    def test_director_heading_top_level_department_not_self_referenced(self):
        director = self._create_employee('Test Director (Self Reference)')
        self.env['hr.department'].create({
            'name': 'Test VET (Self Reference)', 'is_top_level': True, 'top_level_area': 'academic', 'top_level_role': 'hos', 'manager_id': director.id,
        })

        self.env.company.director_id = director.id

        self.assertNotEqual(director.parent_id, director)
        self.assertFalse(director.parent_id)

    def test_onchange_role_ids_blocks_manual_director_assignment(self):
        employee = self._create_employee('Test Employee (Onchange Director Add)')
        employee.role_ids = [(4, self.role_director.id)]

        result = employee._onchange_role_ids()

        self.assertNotIn(self.role_director, employee.role_ids)
        self.assertIn('warning', result)

    def test_onchange_role_ids_blocks_manual_director_removal(self):
        director = self._create_employee('Test Employee (Onchange Director Remove)')
        self.env.company.director_id = director.id
        director.role_ids = [(3, self.role_director.id)]

        result = director._onchange_role_ids()

        self.assertIn(self.role_director, director.role_ids)
        self.assertIn('warning', result)

    def test_get_report_role_lines_director_shows_company(self):
        director = self._create_employee('Test Director (Report Lines)')
        self.env.company.director_id = director.id

        lines = director.get_report_role_lines()

        self.assertEqual(len(lines), 1)
        self.assertIn(self.env.company.name, lines[0])
