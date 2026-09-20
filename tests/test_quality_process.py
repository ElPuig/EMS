# -*- coding: utf-8 -*-

from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase

from .common import create_role_employee, create_role_user


class TestQualityProcess(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.role = cls.env['ems.role'].create({'name': 'Test quality post', 'employee_type': 'teacher'})
        cls.process = cls.env['ems.quality.process'].create({
            'code': 'ZZ1',
            'name': 'Test process',
            'kind': 'strategic',
            'responsible_role_id': cls.role.id,
        })

    def test_create_and_display_name(self):
        self.assertEqual(self.process.display_name, "ZZ1 Test process")

    def test_code_is_unique(self):
        with self.assertRaises(Exception):
            with self.env.cr.savepoint():
                self.env['ems.quality.process'].create({'code': 'ZZ1', 'name': 'Duplicate', 'kind': 'key'})

    def test_responsible_employees_follow_the_post(self):
        """The responsible is a post, so the people shown must follow whoever holds it."""
        self.assertFalse(self.process.responsible_employee_ids)
        user = create_role_user(self, 'quality', 'quality.process.holder@example.com')
        employee = create_role_employee(self, user)
        self.role.employee_ids = [(4, employee.id)]
        self.process.invalidate_recordset(['responsible_employee_ids'])
        self.assertIn(employee.name, self.process.responsible_employee_ids.mapped('name'))

    def test_procedure_count(self):
        self.env['ems.quality.procedure'].create({
            'code': 'ZZ1.01',
            'name': 'Test procedure',
            'process_id': self.process.id,
        })
        self.process.invalidate_recordset(['procedure_count'])
        self.assertEqual(self.process.procedure_count, 1)

    def test_teacher_cannot_read_the_process_map(self):
        """The process map is coordination material: the teaching staff has no access row."""
        user = create_role_user(self, 'teacher', 'quality.process.teacher@example.com')
        with self.assertRaises(AccessError):
            self.process.with_user(user).read(['name'])

    def test_quality_coordination_can_write(self):
        user = create_role_user(self, 'quality_admin', 'quality.process.coord@example.com')
        self.process.with_user(user).write({'is_quality_process': True})
        self.assertTrue(self.process.is_quality_process)
