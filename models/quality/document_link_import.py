# -*- coding: utf-8 -*-

import base64
import csv
import io

from odoo import _, api, fields, models
from odoo.exceptions import UserError


# Every model of the quality structure that carries a link, looked up in this order. Their codes
# never collide (PE3, PE3.01, PE3.01.15), so one file can carry processes, procedures and documents.
_LINKED_MODELS = ('ems.quality.document', 'ems.quality.procedure', 'ems.quality.process')


class EmsQualityDocumentLinkImport(models.TransientModel):
    _name = "ems.quality.document.link.import"
    _description = "Load the Drive links of the quality structure from a code,url file."

    file_data = fields.Binary(string="File", required=True, help="A CSV with two columns: the code of a process, procedure or document, and its link.")
    file_name = fields.Char(string="File name")
    has_header = fields.Boolean(string="First line is a header", default=True)
    result = fields.Text(string="Result", readonly=True)

    def action_import(self):
        """Fill the link of the processes, procedures and documents whose code appears in the file.

        The links are not a data-file column on purpose (they are live application state, see
        docs/en/developers/quality/quality_overview.md), so this is how they get in: one file,
        kept outside the repository, loaded once per environment and again whenever a document
        moves."""
        self.ensure_one()
        rows = self._parse()
        updated, unknown, empty = [], [], 0
        for code, url in rows:
            if not code or not url:
                empty += 1
                continue
            record = self._find(code)
            if not record:
                unknown.append(code)
                continue
            record.url = url
            updated.append(code)
        self.result = self._summary(updated, unknown, empty)
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def _find(self, code):
        for model in _LINKED_MODELS:
            record = self.env[model].with_context(active_test=False).search([('code', '=', code)], limit=1)
            if record:
                return record
        return False

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
    def _summary(self, updated, unknown, empty):
        lines = [_("%s links loaded.", len(updated))]
        if unknown:
            lines.append(_("%(count)s codes are not in the registry: %(codes)s",
                           count=len(unknown), codes=", ".join(sorted(unknown))))
        if empty:
            lines.append(_("%s lines were skipped for having no code or no link.", empty))
        missing = sum(self.env[model].with_context(active_test=False).search_count([('url', '=', False)])
                      for model in _LINKED_MODELS)
        lines.append(_("%s processes, procedures and documents still have no link.", missing))
        return "\n".join(lines)
