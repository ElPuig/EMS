# -*- coding: utf-8 -*-

from datetime import timedelta

from odoo import fields
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
        vals = {'name': 'Test document', 'kind': 'record'}
        vals.update(overrides)
        return self.env['ems.quality.document'].create(vals)

    def test_process_comes_from_the_procedure(self):
        document = self._document(procedure_id=self.procedure.id)
        self.assertEqual(document.process_id, self.process)

    def test_process_can_be_set_without_a_procedure(self):
        document = self._document(process_id=self.process.id)
        self.assertEqual(document.process_id, self.process)

    def test_several_documents_can_be_uncoded(self):
        """The code is nullable on purpose: a document exists before it is coded."""
        self._document()
        self._document(name='Another uncoded document')

    def test_code_is_unique_when_set(self):
        self._document(code='ZZ2.01.01')
        with self.assertRaises(Exception):
            with self.env.cr.savepoint():
                self._document(code='ZZ2.01.01', name='Duplicate')

    def test_legacy_code_detection(self):
        """A code whose leading segment is not a process of the current map is flagged.

        Regression guard for the real case this was written against: a code of the superseded
        scheme ('PS23.2.1') does start with a current process code ('PS2'), so a startswith()
        test let exactly the codes this is meant to catch slip through. Reproduced here with
        codes of its own ('ZQ9' / 'ZQ99') so the test never depends on - or collides with - the
        centre's real process codes."""
        current = self._document(code='ZZ2.01.90', name='Current scheme')
        legacy = self._document(code='ZZ29.2.1', name='Superseded scheme')
        self.assertFalse(current.is_legacy_code)
        self.assertTrue(legacy.is_legacy_code,
                        "'ZZ29' is not a process of the map, even though it starts with 'ZZ2', which is")

    def test_uncoded_document_is_not_flagged_as_legacy(self):
        self.assertFalse(self._document().is_legacy_code)

    def test_needs_review_reads_and_searches_the_same_way(self):
        today = fields.Date.context_today(self.env['ems.quality.document'])
        overdue = self._document(code='ZZ2.01.02', state='approved', next_review_date=today - timedelta(days=1))
        upcoming = self._document(code='ZZ2.01.03', state='approved', next_review_date=today + timedelta(days=30))
        draft = self._document(code='ZZ2.01.04', state='draft', next_review_date=today - timedelta(days=1))
        self.assertTrue(overdue.needs_review)
        self.assertFalse(upcoming.needs_review)
        self.assertFalse(draft.needs_review, "a draft is not due for review: it has not been approved yet")
        found = self.env['ems.quality.document'].search([('needs_review', '=', True)])
        self.assertIn(overdue, found)
        self.assertNotIn(upcoming, found)
        self.assertNotIn(draft, found)

    def test_display_name_includes_the_version(self):
        document = self._document(code='ZZ2.01.05', version='3')
        self.assertEqual(document.display_name, "ZZ2.01.05: Test document (v3)")
