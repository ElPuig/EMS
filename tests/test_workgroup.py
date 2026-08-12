from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase


class TestWorkgroup(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.teacher_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Teacher (Workgroup)',
            'login': 'test_teacher_for_workgroup',
            'groups_id': [(4, cls.env.ref('ems.group_teacher').id)],
        })
        cls.secretary_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Secretary (Workgroup)',
            'login': 'test_secretary_for_workgroup',
            'groups_id': [(4, cls.env.ref('ems.group_secretary').id)],
        })
        cls.test_workgroup = cls.env['ems.workgroup'].create({'name': 'Test Workgroup'})

    def test_create_valid(self):
        workgroup = self.env['ems.workgroup'].create({'name': 'Test 01'})
        self.assertTrue(workgroup.id)
        self.assertEqual(workgroup.name, 'Test 01')

    def test_create_missing_name(self):
        with self.assertRaises(Exception):
            self.env['ems.workgroup'].create({})

    def test_employee_ids_relation(self):
        # employee_ids is hr.employee.public, not hr.employee — compare by id.
        employee = self.env['hr.employee'].create({
            'name': 'Test Employee (Workgroup)', 'employee_type': 'teacher',
        })
        workgroup = self.env['ems.workgroup'].create({
            'name': 'Test 02', 'employee_ids': [(4, employee.id)],
        })
        self.assertIn(employee.id, workgroup.employee_ids.ids)

    def test_admin_can_create(self):
        workgroup = self.env['ems.workgroup'].create({'name': 'Test 03'})
        self.assertTrue(workgroup.id)

    def test_admin_can_write(self):
        workgroup = self.env['ems.workgroup'].create({'name': 'Before Write'})
        workgroup.write({'name': 'After Write'})
        self.assertEqual(workgroup.name, 'After Write')

    def test_admin_can_unlink(self):
        workgroup = self.env['ems.workgroup'].create({'name': 'To Delete'})
        workgroup_id = workgroup.id
        workgroup.unlink()
        self.assertFalse(self.env['ems.workgroup'].search([('id', '=', workgroup_id)]))

    def test_teacher_cannot_create(self):
        with self.assertRaises(AccessError):
            self.env['ems.workgroup'].with_user(self.teacher_user).create({'name': 'Teacher Attempt'})

    def test_teacher_cannot_write(self):
        with self.assertRaises(AccessError):
            self.test_workgroup.with_user(self.teacher_user).write({'name': 'Teacher Write'})

    def test_teacher_cannot_unlink(self):
        with self.assertRaises(AccessError):
            self.test_workgroup.with_user(self.teacher_user).unlink()

    def test_teacher_can_read(self):
        workgroup = self.test_workgroup.with_user(self.teacher_user)
        self.assertEqual(workgroup.name, 'Test Workgroup')

    def test_secretary_cannot_create(self):
        with self.assertRaises(AccessError):
            self.env['ems.workgroup'].with_user(self.secretary_user).create({'name': 'Secretary Attempt'})

    def test_secretary_cannot_write(self):
        with self.assertRaises(AccessError):
            self.test_workgroup.with_user(self.secretary_user).write({'name': 'Secretary Write'})

    def test_secretary_cannot_unlink(self):
        with self.assertRaises(AccessError):
            self.test_workgroup.with_user(self.secretary_user).unlink()
