# -*- coding: utf-8 -*-

import base64

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestQualityDocumentLinkImport(TransactionCase):
    """The links are not a data-file column (they are live application state), so this wizard is
    the way they get into an environment in one go. Worth covering: it is run once per deployment and
    a silent mismatch would leave the registry pointing nowhere."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.process = cls.env['ems.quality.process'].create({'code': 'ZL1', 'name': 'Link test process', 'kind': 'support'})
        cls.document = cls.env['ems.quality.document'].create({
            'code': 'ZL1.01.01',
            'name': 'Link test document',
            'process_id': cls.process.id,
        })

    def _run(self, content, **overrides):
        vals = {'file_data': base64.b64encode(content.encode('utf-8')), 'file_name': 'links.csv'}
        vals.update(overrides)
        wizard = self.env['ems.quality.document.link.import'].create(vals)
        wizard.action_import()
        return wizard

    def test_link_is_filled(self):
        url = "https://docs.google.com/document/d/1AbCdEfGhIjKlMnOpQrStUv/edit"
        wizard = self._run(f"code,url\nZL1.01.01,{url}\n")
        self.assertEqual(self.document.url, url)
        self.assertIn("1 links loaded", wizard.result)

    def test_semicolon_separated_file(self):
        """A spreadsheet exported from a Catalan or Spanish locale uses semicolons."""
        url = "https://docs.google.com/document/d/1SemiColonSeparated9/edit"
        self._run(f"code;url\nZL1.01.01;{url}\n")
        self.assertEqual(self.document.url, url)

    def test_unknown_codes_are_reported_not_silently_dropped(self):
        wizard = self._run("code,url\nZL1.01.01,https://docs.google.com/document/d/1Known0000000000/edit\nZZ9.99.99,https://docs.google.com/document/d/1Unknown000000000/edit\n")
        self.assertIn("ZZ9.99.99", wizard.result)
        self.assertIn("1 links loaded", wizard.result)

    def test_a_line_without_a_link_is_rejected(self):
        with self.assertRaises(UserError):
            self._run("code,url\nZL1.01.01\n")

    def test_a_link_that_is_not_a_drive_address_is_still_stored(self):
        """Not every controlled document lives in Drive; the link is what matters."""
        self._run("code,url\nZL1.01.01,https://elpuig.xeill.net/quality\n")
        self.assertEqual(self.document.url, "https://elpuig.xeill.net/quality")

    def test_processes_and_procedures_are_loaded_from_the_same_file(self):
        procedure = self.env['ems.quality.procedure'].create({'code': 'ZL1.01', 'name': 'Link test procedure', 'process_id': self.process.id})
        wizard = self._run(
            "code,url\n"
            "ZL1,https://docs.google.com/document/d/1ProcessSheet000000/edit\n"
            "ZL1.01,https://docs.google.com/document/d/1ProcedureSheet0000/edit\n"
            "ZL1.01.01,https://docs.google.com/document/d/1DocumentFile00000/edit\n"
        )
        self.assertEqual(self.process.url, "https://docs.google.com/document/d/1ProcessSheet000000/edit")
        self.assertEqual(procedure.url, "https://docs.google.com/document/d/1ProcedureSheet0000/edit")
        self.assertEqual(self.document.url, "https://docs.google.com/document/d/1DocumentFile00000/edit")
        self.assertIn("3 links loaded", wizard.result)
