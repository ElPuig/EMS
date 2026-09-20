# -*- coding: utf-8 -*-

import base64
import csv
import io
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError

# Accepts the two shapes a Drive address comes in: /d/<id>/ for documents and spreadsheets,
# and ?id=<id> for files opened through the viewer.
_DRIVE_ID_PATTERNS = (
    re.compile(r'/d/([A-Za-z0-9_-]{10,})'),
    re.compile(r'[?&]id=([A-Za-z0-9_-]{10,})'),
)


class EmsQualityDocumentLinkImport(models.TransientModel):
    _name = "ems.quality.document.link.import"
    _description = "Load the Drive links of the controlled documents from a code,url file."

    file_data = fields.Binary(string="File", required=True, help="A CSV with two columns: the document code and its link.")
    file_name = fields.Char(string="File name")
    has_header = fields.Boolean(string="First line is a header", default=True)
    result = fields.Text(string="Result", readonly=True)

    def action_import(self):
        """Fill url/drive_file_id on the documents whose code appears in the file.

        The links are not a data-file column on purpose (they are live application state, see
        docs/en/developers/quality/quality_overview.md), so this is how they get in: one file,
        kept outside the repository, loaded once per environment and again whenever a document
        moves."""
        self.ensure_one()
        rows = self._parse()
        documents = self.env['ems.quality.document'].with_context(active_test=False)
        updated, unknown, empty = [], [], 0
        for code, url in rows:
            if not code or not url:
                empty += 1
                continue
            document = documents.search([('code', '=', code)], limit=1)
            if not document:
                unknown.append(code)
                continue
            document.write({'url': url, 'drive_file_id': self._drive_id(url)})
            updated.append(code)
        self.result = self._summary(updated, unknown, empty)
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def _parse(self):
        self.ensure_one()
        try:
            content = base64.b64decode(self.file_data).decode('utf-8-sig')
        except (UnicodeDecodeError, ValueError) as error:
            raise UserError(_("The file could not be read as UTF-8 text: %s", error)) from error
        reader = csv.reader(io.StringIO(content), delimiter=self._delimiter(content))
        rows = [[cell.strip() for cell in row] for row in reader if row]
        if self.has_header and rows:
            rows = rows[1:]
        for row in rows:
            if len(row) < 2:
                raise UserError(_("Every line needs two columns, the code and the link. Offending line: %s", ",".join(row)))
        return [(row[0], row[1]) for row in rows]

    @api.model
    def _delimiter(self, content):
        """Semicolon when that is clearly what the file uses - a spreadsheet exported from a
        Spanish or Catalan locale does, and a Drive link never contains one."""
        first_line = content.splitlines()[0] if content else ''
        return ';' if first_line.count(';') > first_line.count(',') else ','

    @api.model
    def _drive_id(self, url):
        for pattern in _DRIVE_ID_PATTERNS:
            found = pattern.search(url or '')
            if found:
                return found.group(1)
        return False

    @api.model
    def _summary(self, updated, unknown, empty):
        lines = [_("%s links loaded.", len(updated))]
        if unknown:
            lines.append(_("%(count)s codes are not in the registry: %(codes)s",
                           count=len(unknown), codes=", ".join(sorted(unknown))))
        if empty:
            lines.append(_("%s lines were skipped for having no code or no link.", empty))
        missing = self.env['ems.quality.document'].with_context(active_test=False).search_count([('url', '=', False)])
        lines.append(_("%s documents in the registry still have no link.", missing))
        return "\n".join(lines)
