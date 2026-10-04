from odoo.tests.common import TransactionCase


class TestWorkgroup(TransactionCase):

    def test_employee_ids_relation(self):
        # employee_ids is hr.employee.public, not hr.employee — compare by id.
        employee = self.env['hr.employee'].create({
            'name': 'Test Employee (Workgroup)', 'employee_type': 'teacher',
        })
        workgroup = self.env['ems.workgroup'].create({
            'name': 'Test 02', 'employee_ids': [(4, employee.id)],
        })
        self.assertIn(employee.id, workgroup.employee_ids.ids)
