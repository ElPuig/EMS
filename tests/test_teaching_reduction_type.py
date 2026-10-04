from odoo.tests.common import TransactionCase


class TestTeachingReductionType(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.test_type = cls.env['ems.teaching_reduction_type'].create({
            'code': 'TST',
            'name': 'Test Type',
            'reduction_hours': 2,
        })

    def test_code_must_be_unique(self):
        self.env['ems.teaching_reduction_type'].create({'code': 'UNIQ', 'name': 'First', 'reduction_hours': 1})
        with self.assertRaises(Exception):
            self.env['ems.teaching_reduction_type'].create({'code': 'UNIQ', 'name': 'Second', 'reduction_hours': 1})

    def test_employee_can_have_several_reduction_types(self):
        other_type = self.env['ems.teaching_reduction_type'].create({'code': 'T09', 'name': 'Other Type', 'reduction_hours': 1})
        employee = self.env['hr.employee'].create({
            'name': 'Test Teacher With Reductions',
            'employee_type': 'teacher',
            'teaching_reduction_ids': [(6, 0, [self.test_type.id, other_type.id])],
        })
        self.assertEqual(employee.teaching_reduction_ids, self.test_type | other_type)

    def test_reduction_hours_added_to_teaching_summary(self):
        employee = self.env['hr.employee'].create({
            'name': 'Test Teacher Reduction Summary',
            'employee_type': 'teacher',
            'teaching_reduction_ids': [(6, 0, [self.test_type.id])],
        })
        summary = employee.resource_calendar_id.get_schedule_hours_summary()
        reduction_row = next(row for row in summary['teaching']['rows'] if row['label'] == 'Test Type')
        self.assertEqual(reduction_row['hours'], 2)
        self.assertEqual(summary['teaching']['total'], 2)
        self.assertEqual(summary['total'], 2)
