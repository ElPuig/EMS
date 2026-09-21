# -*- coding: utf-8 -*-

from odoo.exceptions import UserError, ValidationError
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

    def test_embed_url_is_derived_from_the_ordinary_link(self):
        """One link per document: the preview address is built from the one people copy."""
        doc_id = "1nCknSDrX3Phc-MKOFZeQflerdEe82eUOe0VnAvHnbw4"
        cases = {
            f"https://docs.google.com/document/d/{doc_id}/edit?usp=sharing": f"https://docs.google.com/document/d/{doc_id}/preview",
            f"https://docs.google.com/spreadsheets/d/{doc_id}/edit#gid=0": f"https://docs.google.com/spreadsheets/d/{doc_id}/preview",
            f"https://docs.google.com/presentation/d/{doc_id}/edit": f"https://docs.google.com/presentation/d/{doc_id}/preview",
            f"https://drive.google.com/file/d/{doc_id}/view?usp=sharing": f"https://drive.google.com/file/d/{doc_id}/preview",
            f"https://drive.google.com/open?id={doc_id}": f"https://drive.google.com/file/d/{doc_id}/preview",
        }
        for url, expected in cases.items():
            self.assertEqual(self._document(url=url).embed_url, expected, url)
        self.assertFalse(self._document(url="https://elpuig.xeill.net/qualitat").embed_url,
                         "an address EMS does not know how to embed shows no preview, only 'Open'")

    def test_open_uses_the_ordinary_link(self):
        url = "https://docs.google.com/document/d/1AbCdEfGhIjKlMnOpQrStUv/edit"
        action = self._document(url=url).action_open_document()
        self.assertEqual((action['type'], action['url'], action['target']), ('ir.actions.act_url', url, 'new'))
        with self.assertRaises(UserError):
            self._document().action_open_document()

    def test_only_one_process_map(self):
        Document = self.env['ems.quality.document']
        Document.search([('is_process_map', '=', True)]).is_process_map = False
        current = self._document(name='Process map', is_process_map=True)
        with self.assertRaises(ValidationError):
            self._document(name='Another map', is_process_map=True)
        action = Document.action_open_process_map()
        self.assertEqual((action['res_model'], action['res_id']), ('ems.quality.document', current.id))
        current.is_process_map = False
        with self.assertRaises(UserError):
            Document.action_open_process_map()

