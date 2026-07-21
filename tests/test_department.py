from odoo.tests.common import TransactionCase


class TestDepartment(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.role_dchieff = cls.env.ref('ems.role_dchieff')
        cls.role_seminar = cls.env.ref('ems.role_seminar')
        cls.group_department_chief = cls.env.ref('ems.group_department_chief')

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

    def test_seminar_head_becomes_manager_of_other_members(self):
        department = self.env['hr.department'].create({'name': 'Test Department (Seminar Cascade)'})
        head = self._create_employee('Test Head (Seminar Cascade)', department)
        seminar_head = self._create_employee('Test Seminar Chief (Seminar Cascade)', department)
        regular = self._create_employee('Test Regular (Seminar Cascade)', department)
        department.write({'manager_id': head.id, 'seminar_head_id': seminar_head.id})

        self.assertEqual(regular.parent_id, seminar_head)

    def test_department_head_excluded_from_cascade(self):
        department = self.env['hr.department'].create({'name': 'Test Department (Head Excluded)'})
        head = self._create_employee('Test Head (Head Excluded)', department)
        seminar_head = self._create_employee('Test Seminar Chief (Head Excluded)', department)
        department.write({'manager_id': head.id, 'seminar_head_id': seminar_head.id})

        self.assertFalse(head.parent_id)

    def test_seminar_head_manager_is_department_head(self):
        department = self.env['hr.department'].create({'name': 'Test Department (Seminar Manager)'})
        head = self._create_employee('Test Head (Seminar Manager)', department)
        seminar_head = self._create_employee('Test Seminar Chief (Seminar Manager)', department)
        department.write({'manager_id': head.id, 'seminar_head_id': seminar_head.id})

        self.assertEqual(seminar_head.parent_id, head)

    def test_self_reference_guarded(self):
        department = self.env['hr.department'].create({'name': 'Test Department (Self Reference)'})
        head = self._create_employee('Test Head (Self Reference)', department)
        department.write({'manager_id': head.id, 'seminar_head_id': head.id})

        self.assertNotEqual(head.parent_id, head)

    def test_changing_department_manager_recascades_existing_members(self):
        department = self.env['hr.department'].create({'name': 'Test Department (Manager Recascade)'})
        seminar_head = self._create_employee('Test Seminar Chief (Manager Recascade)', department)
        regular = self._create_employee('Test Regular (Manager Recascade)', department)
        department.seminar_head_id = seminar_head.id
        old_head = self._create_employee('Test Old Head (Manager Recascade)', department)
        new_head = self._create_employee('Test New Head (Manager Recascade)', department)
        department.manager_id = old_head.id

        department.manager_id = new_head.id

        self.assertEqual(seminar_head.parent_id, new_head)
        self.assertEqual(regular.parent_id, seminar_head)

    def test_changing_seminar_head_recascades_members(self):
        department = self.env['hr.department'].create({'name': 'Test Department (Seminar Recascade)'})
        head = self._create_employee('Test Head (Seminar Recascade)', department)
        regular = self._create_employee('Test Regular (Seminar Recascade)', department)
        old_seminar_head = self._create_employee('Test Old Seminar Chief (Seminar Recascade)', department)
        new_seminar_head = self._create_employee('Test New Seminar Chief (Seminar Recascade)', department)
        department.write({'manager_id': head.id, 'seminar_head_id': old_seminar_head.id})

        department.seminar_head_id = new_seminar_head.id

        self.assertEqual(regular.parent_id, new_seminar_head)
        self.assertEqual(old_seminar_head.parent_id, new_seminar_head)

    def test_department_head_role_auto_assigned_and_removed(self):
        head = self._create_employee('Test Head (Role Assign)', with_user=True)
        department = self.env['hr.department'].create({'name': 'Test Department (Role Assign)', 'manager_id': head.id})

        self.assertIn(self.role_dchieff, head.role_ids)
        self.assertIn(self.group_department_chief, head.user_id.groups_id)

        department.manager_id = False

        self.assertNotIn(self.role_dchieff, head.role_ids)
        self.assertNotIn(self.group_department_chief, head.user_id.groups_id)

    def test_department_head_role_survives_other_headed_department(self):
        head = self._create_employee('Test Head (Multi Department)', with_user=True)
        department_a = self.env['hr.department'].create({'name': 'Test Department A (Multi)', 'manager_id': head.id})
        department_b = self.env['hr.department'].create({'name': 'Test Department B (Multi)', 'manager_id': head.id})

        department_a.manager_id = False

        self.assertIn(self.role_dchieff, head.role_ids)
        self.assertEqual(head.headed_department_ids, department_b)

    def test_seminar_head_role_auto_assigned_and_removed(self):
        seminar_head = self._create_employee('Test Seminar Chief (Role Assign)', with_user=True)
        department = self.env['hr.department'].create({
            'name': 'Test Department (Seminar Role Assign)', 'seminar_head_id': seminar_head.id,
        })

        self.assertIn(self.role_seminar, seminar_head.role_ids)
        self.assertIn(self.group_department_chief, seminar_head.user_id.groups_id)

        department.seminar_head_id = False

        self.assertNotIn(self.role_seminar, seminar_head.role_ids)
        self.assertNotIn(self.group_department_chief, seminar_head.user_id.groups_id)

    def test_employee_changing_department_recomputes_manager(self):
        department_a = self.env['hr.department'].create({'name': 'Test Department A (Move)'})
        department_b = self.env['hr.department'].create({'name': 'Test Department B (Move)'})
        seminar_head_a = self._create_employee('Test Seminar Chief A (Move)', department_a)
        seminar_head_b = self._create_employee('Test Seminar Chief B (Move)', department_b)
        department_a.seminar_head_id = seminar_head_a.id
        department_b.seminar_head_id = seminar_head_b.id
        employee = self._create_employee('Test Employee (Move)', department_a)
        self.assertEqual(employee.parent_id, seminar_head_a)

        employee.department_id = department_b.id

        self.assertEqual(employee.parent_id, seminar_head_b)

    def test_onchange_role_ids_blocks_manual_department_head_assignment(self):
        employee = self._create_employee('Test Employee (Onchange Dchieff)')
        employee.role_ids = [(4, self.role_dchieff.id)]

        result = employee._onchange_role_ids()

        self.assertNotIn(self.role_dchieff, employee.role_ids)
        self.assertIn('warning', result)

    def test_onchange_role_ids_blocks_manual_seminar_head_assignment(self):
        employee = self._create_employee('Test Employee (Onchange Seminar)')
        employee.role_ids = [(4, self.role_seminar.id)]

        result = employee._onchange_role_ids()

        self.assertNotIn(self.role_seminar, employee.role_ids)
        self.assertIn('warning', result)

    def test_reassigning_department_head_demotes_old_head(self):
        department = self.env['hr.department'].create({'name': 'Test Department (Demote Head)'})
        old_head = self._create_employee('Test Old Head (Demote Head)', department, with_user=True)
        department.manager_id = old_head.id
        new_head = self._create_employee('Test New Head (Demote Head)', department, with_user=True)

        department.manager_id = new_head.id

        self.assertNotIn(self.role_dchieff, old_head.role_ids)
        self.assertNotIn(self.group_department_chief, old_head.user_id.groups_id)
        self.assertIn(self.role_dchieff, new_head.role_ids)

    def test_reassigning_seminar_head_demotes_old_seminar_head(self):
        department = self.env['hr.department'].create({'name': 'Test Department (Demote Seminar)'})
        old_seminar_head = self._create_employee('Test Old Seminar Chief (Demote Seminar)', department, with_user=True)
        department.seminar_head_id = old_seminar_head.id
        new_seminar_head = self._create_employee('Test New Seminar Chief (Demote Seminar)', department, with_user=True)

        department.seminar_head_id = new_seminar_head.id

        self.assertNotIn(self.role_seminar, old_seminar_head.role_ids)
        self.assertNotIn(self.group_department_chief, old_seminar_head.user_id.groups_id)
        self.assertIn(self.role_seminar, new_seminar_head.role_ids)

    def test_onchange_role_ids_blocks_manual_department_head_removal(self):
        head = self._create_employee('Test Employee (Onchange Remove Dchieff)')
        department = self.env['hr.department'].create({'name': 'Test Department (Onchange Remove Dchieff)', 'manager_id': head.id})
        head.role_ids = [(3, self.role_dchieff.id)]

        result = head._onchange_role_ids()

        self.assertIn(self.role_dchieff, head.role_ids)
        self.assertIn('warning', result)

    def test_onchange_role_ids_blocks_manual_seminar_head_removal(self):
        seminar_head = self._create_employee('Test Employee (Onchange Remove Seminar)')
        department = self.env['hr.department'].create({
            'name': 'Test Department (Onchange Remove Seminar)', 'seminar_head_id': seminar_head.id,
        })
        seminar_head.role_ids = [(3, self.role_seminar.id)]

        result = seminar_head._onchange_role_ids()

        self.assertIn(self.role_seminar, seminar_head.role_ids)
        self.assertIn('warning', result)

    def test_no_seminar_head_falls_back_to_department_chief(self):
        department = self.env['hr.department'].create({'name': 'Test Department (No Seminar Fallback)'})
        head = self._create_employee('Test Head (No Seminar Fallback)', department)
        regular = self._create_employee('Test Regular (No Seminar Fallback)', department)
        department.manager_id = head.id

        self.assertEqual(regular.parent_id, head)
