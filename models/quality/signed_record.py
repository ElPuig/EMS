# -*- coding: utf-8 -*-

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class EmsSignedRecord(models.AbstractModel):
    """Everything that gets written, approved, turned into a PDF and filed.

    Minutes and evidence records today; audit reports and the management review in later phases.
    The machinery is here so that the day the institutional header or the versioning policy
    changes, it changes in one place."""

    _name = "ems.signed.record"
    _description = "Signed record: shared machinery for anything approved, rendered and filed."

    code = fields.Char(string="Code", readonly=True, copy=False, index=True)
    date = fields.Date(string="Date", required=True, default=fields.Date.context_today, tracking=True)
    state = fields.Selection(
        string="State",
        selection=[('draft', "Draft"), ('to_approve', "To approve"), ('approved', "Approved")],
        required=True,
        default='draft',
        tracking=True,
    )
    # Which controlled template this was written against, and the version it carried at the time.
    # The version is frozen on approval: that is what answers "which model was this written with?"
    # years later, without anybody having to remember.
    template_document_id = fields.Many2one(string="Template", comodel_name="ems.quality.document", ondelete='restrict')
    template_version = fields.Char(string="Template version", readonly=True, copy=False)
    pdf_attachment_id = fields.Many2one(string="PDF", comodel_name="ir.attachment", readonly=True, copy=False)
    drive_file_id = fields.Char(string="Drive file id", readonly=True, copy=False)
    drive_url = fields.Char(string="Drive link", readonly=True, copy=False)

    def action_submit(self):
        for record in self:
            if record.state != 'draft':
                raise UserError(_("Only a draft can be sent for approval."))
            record.state = 'to_approve'

    def action_back_to_draft(self):
        for record in self:
            if record.state == 'approved':
                raise UserError(_("An approved record cannot go back to draft: correct it with a new version instead."))
            record.state = 'draft'

    def action_approve(self):
        """Approve, freeze the template version and render the PDF.

        The PDF is deliberately generated here and not on demand: once approved it must not change,
        and rendering it later would silently follow any edit to the template."""
        for record in self:
            if record.state == 'approved':
                raise UserError(_("This record is already approved."))
            record._ems_check_can_approve()
            record.state = 'approved'
            record.template_version = record.template_document_id.version or ''
            record._ems_render_pdf()
            record._ems_upload_to_drive()

    def _ems_check_can_approve(self):
        """Hook for the concrete model to refuse approval. Nothing here by default."""
        return True

    def _ems_report_xmlid(self):
        """The QWeb report used to render this record. Concrete models override it."""
        self.ensure_one()
        raise NotImplementedError

    def _ems_file_name(self):
        """Name of the generated file, starting with the code so it is self-describing wherever
        it ends up - including somebody's downloads folder."""
        self.ensure_one()
        return f"{self.code or self._name}.pdf"

    def _ems_render_pdf(self):
        self.ensure_one()
        report = self.env['ir.actions.report']._render_qweb_pdf(self._ems_report_xmlid(), res_ids=self.ids)[0]
        self.pdf_attachment_id = self.env['ir.attachment'].create({
            'name': self._ems_file_name(),
            'type': 'binary',
            'raw': report,
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'application/pdf',
        })
        return self.pdf_attachment_id

    def _ems_upload_to_drive(self):
        """Seam for filing the PDF in the centre's shared drive.

        Not implemented yet, and on purpose: it needs a Drive scope added to the service account
        and the account made a content manager of the shared drives, which is a Google Workspace
        administration change (see the phase 2 issue). Until then the PDF lives as an attachment
        on the record, which is reachable and downloadable; this method only leaves a trace so the
        gap is visible in the log rather than silently absent."""
        for record in self:
            if not record.pdf_attachment_id:
                continue
            _logger.info(
                "EMS quality: %s %s approved; its PDF is attached but not filed in Drive yet "
                "(Drive write access is not configured).", record._name, record.code or record.id,
            )
        return False
