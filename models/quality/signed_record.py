# -*- coding: utf-8 -*-

import io
import logging
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..shared.google_workspace_mixin import HttpError, MediaIoBaseUpload

_logger = logging.getLogger(__name__)

# A Drive folder link (https://drive.google.com/drive/folders/<id>?usp=...) or the bare id.
DRIVE_FOLDER_ID = re.compile(r'(?:/folders/|^)([\w-]{10,})')


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
    # Which controlled template this was written against.
    template_document_id = fields.Many2one(string="Template", comodel_name="ems.quality.document", ondelete='restrict')
    pdf_attachment_id = fields.Many2one(string="PDF", comodel_name="ir.attachment", readonly=True, copy=False)
    drive_file_id = fields.Char(string="Drive file id", readonly=True, copy=False)
    drive_url = fields.Char(string="Drive link", readonly=True, copy=False)

    # --- Filing in Drive (issue #769) ------------------------------------------------------------
    # One file per record in the configured folder, named after its code, replaced whenever the
    # record is created or changes state, and sent to the bin when the record is deleted. In the
    # background (queue_job): Google may be slow or down, and nobody should wait for it.

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._ems_queue_drive_upload()
        return records

    def write(self, vals):
        result = super().write(vals)
        if 'state' in vals:
            self._ems_queue_drive_upload()
        return result

    def unlink(self):
        file_ids = [file_id for file_id in self.mapped('drive_file_id') if file_id]
        result = super().unlink()
        if file_ids and self._ems_drive_folder_id():
            for file_id in file_ids:
                self.browse().with_delay(identity_key=f"ems_drive_trash_{file_id}",
                                description=f"Send to the Drive bin: {file_id}")._ems_drive_trash(file_id)
        return result

    @api.model
    def _ems_drive_folder_id(self):
        """The folder of the settings, or False when filing in Drive is not configured."""
        company = self.env.company.sudo()
        match = company.google_ws_enabled and DRIVE_FOLDER_ID.search((company.minute_drive_folder_url or '').strip())
        return match.group(1) if match else False

    def _ems_queue_drive_upload(self):
        if not self._ems_drive_folder_id():
            return
        for record in self:
            # One waiting job per record: several state changes in a row file it once.
            record.with_delay(identity_key=f"ems_drive_upload_{record._name}_{record.id}",
                              description=f"File in Drive: {record.code or record.id}")._ems_upload_to_drive()

    def _ems_drive_pdf(self):
        """The PDF to file: the one kept on approval, or the record as it stands otherwise."""
        self.ensure_one()
        if self.state == 'approved' and self.pdf_attachment_id:
            return self.pdf_attachment_id.raw
        return self.env['ir.actions.report']._render_qweb_pdf(self._ems_report_xmlid(), res_ids=self.ids)[0]

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
        """Approve and render the PDF.

        The PDF is deliberately generated here and not on demand: once approved it must not change,
        and rendering it later would silently follow any edit to the template."""
        for record in self:
            if record.state == 'approved':
                raise UserError(_("This record is already approved."))
            record._ems_check_can_approve()
            record.state = 'approved'
            # With sudo: the approval has been checked, and an approved record can no longer be
            # written by whoever approved it - which attaching its PDF to it requires.
            record.sudo()._ems_render_pdf()

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

    def action_open_pdf(self):
        """Show the PDF itself, in a browser tab, rather than the attachment record that holds it."""
        self.ensure_one()
        if not self.pdf_attachment_id:
            raise UserError(_("There is no PDF yet: it is generated when the record is approved."))
        return {'type': 'ir.actions.act_url', 'url': f"/web/content/{self.pdf_attachment_id.id}?download=false", 'target': 'new'}

    def _ems_upload_to_drive(self):
        """Job: put the record's PDF in the Drive folder, replacing the file it already has there."""
        folder_id = self._ems_drive_folder_id()
        gw = self.env['google.workspace.mixin']
        for record in self.sudo().exists():
            # Locked first: two jobs for the same record (one started, the next queued behind it)
            # would otherwise both see no file yet and create two. The second fails here and
            # queue_job retries it once the first has saved the file id.
            gw._gw_lock_for_creation(record)
            pdf = record._ems_drive_pdf()
            # Just the code: what finds a record in the folder, and never changes.
            name = f"{record.code or record.id}.pdf"
            if self.env.company.google_ws_dry_run:
                _logger.info("[GW dry-run] file %s in Drive folder %s (%d bytes)", name, folder_id, len(pdf))
                continue
            service = gw._gw_get_drive_service()
            media = MediaIoBaseUpload(io.BytesIO(pdf), mimetype='application/pdf', resumable=False)
            result = False
            if record.drive_file_id:
                try:
                    result = service.files().update(
                        fileId=record.drive_file_id, body={'name': name}, media_body=media,
                        fields='id,webViewLink', supportsAllDrives=True).execute()
                except HttpError as error:
                    # Deleted or moved out of reach in Drive: file it again.
                    if getattr(getattr(error, 'resp', None), 'status', None) != 404:
                        raise
                    media = MediaIoBaseUpload(io.BytesIO(pdf), mimetype='application/pdf', resumable=False)
            if not result:
                result = service.files().create(
                    body={'name': name, 'parents': [folder_id]}, media_body=media,
                    fields='id,webViewLink', supportsAllDrives=True).execute()
            record.write({'drive_file_id': result['id'], 'drive_url': result.get('webViewLink')})
        return True

    @api.model
    def _ems_drive_trash(self, file_id):
        """Job: send the file of a deleted record to the bin of the shared drive (kept 30 days)."""
        if self.env.company.google_ws_dry_run:
            _logger.info("[GW dry-run] send Drive file %s to the bin", file_id)
            return True
        service = self.env['google.workspace.mixin']._gw_get_drive_service()
        try:
            service.files().update(fileId=file_id, body={'trashed': True}, supportsAllDrives=True).execute()
        except HttpError as error:
            if getattr(getattr(error, 'resp', None), 'status', None) != 404:
                raise
        return True
