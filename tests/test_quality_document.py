# -*- coding: utf-8 -*-

from odoo.tests.common import TransactionCase


class TestQualityDocument(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.process = cls.env['ems.quality.process'].create({'code': 'ZZ2', 'name': 'Doc test process', 'kind': 'support'})
        cls.procedure = cls.env['ems.quality.procedure'].create({
            'code': 'ZZ2.01',
            'name': 'Doc test procedure',
            'process_id': cls.process.id,
        })

    def _document(self, **overrides):
        vals = {'name': 'Test document'}
        vals.update(overrides)
        return self.env['ems.quality.document'].create(vals)

    def test_process_comes_from_the_procedure(self):
        document = self._document(procedure_id=self.procedure.id)
        self.assertEqual(document.process_id, self.process)

    def test_process_can_be_set_without_a_procedure(self):
        document = self._document(process_id=self.process.id)
        self.assertEqual(document.process_id, self.process)

    def test_several_documents_can_be_uncoded(self):
        """The code is nullable on purpose: some documents of the centre have no code yet."""
        self._document()
        self._document(name='Another uncoded document')

    def test_code_is_unique_when_set(self):
        self._document(code='ZZ2.01.01')
        with self.assertRaises(Exception):
            with self.env.cr.savepoint():
                self._document(code='ZZ2.01.01', name='Duplicate')

    def test_display_name(self):
        self.assertEqual(self._document(code='ZZ2.01.05').display_name, "ZZ2.01.05: Test document")
        self.assertEqual(self._document(name='Uncoded').display_name, "Uncoded")
