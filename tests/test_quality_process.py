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

    def test_quality_coordination_can_write(self):
        user = create_role_user(self, 'quality_admin', 'quality.process.coord@example.com')
        self.process.with_user(user).write({'name': 'Renamed process'})
        self.assertEqual(self.process.name, 'Renamed process')

    def test_forms_open_read_only_and_edit_follows_write_access(self):
        """'edit_mode' always loads False, and 'Edit' is only offered to whoever may write."""
        coordinator = create_role_user(self, 'quality_admin', 'quality.process.editor@example.com')
        reader = create_role_user(self, 'quality', 'quality.process.reader@example.com')
        as_coordinator = self.process.with_user(coordinator)
        self.assertFalse(as_coordinator.edit_mode)
        self.assertTrue(as_coordinator.can_edit)
        self.assertFalse(self.process.with_user(reader).can_edit)
        self.assertTrue(self.env['ems.quality.process'].new({'code': 'ZZ9'}).edit_mode,
                        "a record being created has nothing to consult: it starts in edit mode")

    def test_process_sheet_is_previewed_from_its_link(self):
        """A process (and a procedure) carries its own sheet, shown in its form like a document."""
        doc_id = "1_cG64QU70c0i_Oslo76eZbn9RrOLMRJCDpz0Yzqigdc"
        self.process.url = f"https://docs.google.com/document/d/{doc_id}/edit?usp=sharing"
        self.assertEqual(self.process.embed_url, f"https://docs.google.com/document/d/{doc_id}/preview")
        action = self.process.action_open_document()
        self.assertEqual((action['url'], action['target']), (self.process.url, 'new'))
        procedure = self.env['ems.quality.procedure'].create({
            'code': 'ZZ1.02',
            'name': 'Previewed procedure',
            'process_id': self.process.id,
            # The centre's own map links some sheets through the '/u/0/' form of the address.
            'url': f"https://docs.google.com/document/u/0/d/{doc_id}/edit",
        })
        self.assertEqual(procedure.embed_url, f"https://docs.google.com/document/d/{doc_id}/preview")
