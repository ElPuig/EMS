from odoo.tests.common import TransactionCase


class TestWorkgroup(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

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
