# -*- coding: utf-8 -*-

import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

# Google's own embeddable address for each kind of file, built from the ordinary link people copy
# from the browser: '/preview' shows the file read-only inside a frame and follows the file's own
# sharing, so one link per document is enough (no 'Publish to the web' copy to keep alongside).
_EMBEDDABLE_LINKS = (
    (re.compile(r'https://docs\.google\.com/(document|spreadsheets|presentation|drawings)/d/([A-Za-z0-9_-]{10,})'),
     lambda match: f"https://docs.google.com/{match.group(1)}/d/{match.group(2)}/preview"),
    (re.compile(r'https://drive\.google\.com/file/d/([A-Za-z0-9_-]{10,})'),
     lambda match: f"https://drive.google.com/file/d/{match.group(1)}/preview"),
    (re.compile(r'https://drive\.google\.com/open\?id=([A-Za-z0-9_-]{10,})'),
     lambda match: f"https://drive.google.com/file/d/{match.group(1)}/preview"),
)


class EmsQualityDocument(models.Model):
    _name = "ems.quality.document"
    _description = "Controlled document: where it sits in the documentary structure and its link in Drive."
    _inherit = ['ems.quality.edit.mode']
    _order = "code, name"
    _sql_constraints = [
        # Nullable on purpose: some documents of the centre have no code yet. Postgres treats
        # NULLs as distinct, so several uncoded documents coexist without tripping the constraint.
        ('unique_code', 'unique (code)', "Another document already uses this code."),
    ]

    # Deliberately no version, state or dates: the document itself, in Drive, is the only place
    # those are kept, so nobody has to update them twice.
    code = fields.Char(string="Code", help="As in the centre's documentation: PE3.01.15. Empty while the document has no code.")
    name = fields.Char(string="Name", required=True, translate=True)
    procedure_id = fields.Many2one(string="Procedure", comodel_name="ems.quality.procedure", ondelete='set null')
    process_id = fields.Many2one(
        string="Process",
        comodel_name="ems.quality.process",
        compute="_compute_process_id",
        store=True,
        readonly=False,
        ondelete='set null',
        help="Taken from the procedure when there is one, and editable for documents that hang straight off a process.",
    )
    # Not a data/custom/ CSV column on purpose: the links point into the centre's Drive, which
    # this public repository does not publish. Filled in from the app, or loaded in one go with
    # the code,url wizard.
    url = fields.Char(string="Link", help="The document's ordinary address, as copied from the browser. It is what 'Open' uses.")
    embed_url = fields.Char(
        string="Preview address",
        compute="_compute_embed_url",
        help="Built from the link for Google Docs, Sheets, Slides and Drive files. Empty for any other address.",
    )
    is_process_map = fields.Boolean(string="Process map", help="The document shown in Quality > Process map. Only one document can be marked.")
    active = fields.Boolean(string="Active", default=True)

    @api.depends('procedure_id')
    def _compute_process_id(self):
        for document in self:
            if document.procedure_id:
                document.process_id = document.procedure_id.process_id

    @api.depends('url')
    def _compute_embed_url(self):
        for document in self:
            document.embed_url = document._embeddable_url(document.url)

    @api.model
    def _embeddable_url(self, url):
        for pattern, build in _EMBEDDABLE_LINKS:
            match = pattern.match(url or '')
            if match:
                return build(match)
        return False

    @api.constrains('is_process_map', 'active')
    def _check_single_process_map(self):
        if self.search_count([('is_process_map', '=', True)]) > 1:
            raise ValidationError(_("Only one document can be marked as the process map."))

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for document in self:
            document.display_name = f"{document.code}: {document.name}" if document.code else document.name

    def action_open_document(self):
        self.ensure_one()
        if not self.url:
            raise UserError(_("This document has no link yet."))
        return {'type': 'ir.actions.act_url', 'url': self.url, 'target': 'new'}

    @api.model
    def action_open_process_map(self):
        """Quality > Process map: the form of whichever document is marked as the process map."""
        document = self.search([('is_process_map', '=', True)], limit=1)
        if not document:
            raise UserError(_("No document is marked as the process map yet. Mark one in Quality > Configuration > Documents."))
        return {
            'type': 'ir.actions.act_window',
            'name': _("Process map"),
            'res_model': self._name,
            'res_id': document.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'current',
        }
