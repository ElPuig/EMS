from odoo.tests.common import TransactionCase


class TestJob(TransactionCase):
    """hr.job's own fields only — the group_id -> employee security-group sync is already
    covered from hr.employee's side by test_employee_role_group_sync.py."""

    def test_create_with_employee_type(self):
        job = self.env['hr.job'].create({'name': 'Test Job (Teacher)', 'employee_type': 'teacher'})
        self.assertEqual(job.employee_type, 'teacher')

    def test_create_with_group_id(self):
        group = self.env.ref('ems.group_secretary')
        job = self.env['hr.job'].create({'name': 'Test Job (Group)', 'group_id': group.id})
        self.assertEqual(job.group_id, group)

    def test_group_id_optional(self):
        job = self.env['hr.job'].create({'name': 'Test Job (No Group)'})
        self.assertFalse(job.group_id)
