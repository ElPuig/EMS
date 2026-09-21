# -*- coding: utf-8 -*-

from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase

from .common import create_role_user


class TestQualityProcess(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.process = cls.env['ems.quality.process'].create({
            'code': 'ZZ1',
            'name': 'Test process',
            'kind': 'strategic',
        })

    def test_create_and_display_name(self):
        self.assertEqual(self.process.display_name, "ZZ1 Test process")

    def test_code_is_unique(self):
        with self.assertRaises(Exception):
            with self.env.cr.savepoint():
                self.env['ems.quality.process'].create({'code': 'ZZ1', 'name': 'Duplicate', 'kind': 'key'})

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
        with self.assertRaises(AccessError):
            self.env['ems.quality.process'].with_user(user).get_process_map_url()

    def test_quality_coordination_can_write(self):
        user = create_role_user(self, 'quality_admin', 'quality.process.coord@example.com')
        self.process.with_user(user).write({'name': 'Renamed process'})
        self.assertEqual(self.process.name, 'Renamed process')

    def test_process_map_url_comes_from_the_company(self):
        """Readable by a quality role that has no access to the company settings."""
        url = "https://docs.google.com/document/d/e/2PACX-test/pub?embedded=true"
        self.env.company.quality_process_map_url = url
        user = create_role_user(self, 'quality', 'quality.process.reader@example.com')
        self.assertEqual(self.env['ems.quality.process'].with_user(user).get_process_map_url(), url)
        self.env.company.quality_process_map_url = False
        self.assertFalse(self.env['ems.quality.process'].with_user(user).get_process_map_url())
