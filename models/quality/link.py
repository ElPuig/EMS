# -*- coding: utf-8 -*-

import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError

# Google's own embeddable address for each kind of file, built from the ordinary link people copy
# from the browser: '/preview' shows the file read-only inside a frame and follows the file's own
# sharing, so one link per record is enough (no 'Publish to the web' copy to keep alongside).
_EMBEDDABLE_LINKS = (
    (re.compile(r'https://docs\.google\.com/(document|spreadsheets|presentation|drawings)(?:/u/\d+)?/d/([A-Za-z0-9_-]{10,})'),
     lambda match: f"https://docs.google.com/{match.group(1)}/d/{match.group(2)}/preview"),
    (re.compile(r'https://drive\.google\.com/file(?:/u/\d+)?/d/([A-Za-z0-9_-]{10,})'),
     lambda match: f"https://drive.google.com/file/d/{match.group(1)}/preview"),
    (re.compile(r'https://drive\.google\.com/open\?id=([A-Za-z0-9_-]{10,})'),
     lambda match: f"https://drive.google.com/file/d/{match.group(1)}/preview"),
)


class EmsQualityLink(models.AbstractModel):
    """A record of the quality structure backed by a file in Drive: the process sheet, the procedure
    sheet or the controlled document itself. Its form shows the file and opens it for editing."""

    _name = "ems.quality.link"
    _description = "Quality link: a record whose content is a file in Drive, previewed in its form."

    # Not a data/custom/ CSV column on purpose: the links point into the centre's Drive, which
    # this public repository does not publish. Filled in from the app, or loaded in one go with
    # the code,url wizard.
    url = fields.Char(string="Link", help="The document's ordinary address, as copied from the browser. It is what 'Open document' opens.")
    embed_url = fields.Char(
        string="Preview address",
        compute="_compute_embed_url",
        help="Built from the link for Google Docs, Sheets, Slides and Drive files. Empty for any other address.",
    )

    @api.depends('url')
    def _compute_embed_url(self):
        for record in self:
            record.embed_url = record._embeddable_url(record.url)

    @api.model
    def _embeddable_url(self, url):
        for pattern, build in _EMBEDDABLE_LINKS:
            match = pattern.match(url or '')
            if match:
                return build(match)
        return False

    def action_open_document(self):
        self.ensure_one()
        if not self.url:
            raise UserError(_("This document has no link yet."))
        return {'type': 'ir.actions.act_url', 'url': self.url, 'target': 'new'}
