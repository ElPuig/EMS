# -*- coding: utf-8 -*-

from datetime import timedelta

from markupsafe import escape

from odoo import _, fields, models
from odoo.exceptions import UserError

# A confidential document's files and where its owner is: model -> (fields holding the files, the owner).
CONFIDENTIAL_FILES = {
    'ems.erasmus.application.document': (('attachment_ids', 'prepared_attachment_ids'), 'application_id'),
    'ems.erasmus.project.document': (('attachment_ids',), 'project_id'),
}
# The same person opening the same file again within this time is noted once.
VIEW_LOG_MINUTES = 10


class IrBinary(models.AbstractModel):
    """The files of a confidential Erasmus+ document (health card, evidence of fewer opportunities)
    are shown, never downloaded, and every opening is noted on its application or project.

    /web/content and /web/image (what the file viewer and a pasted address use) pass 'download' as
    the 'download_attachments' context key; the portal's own controllers don't, so an applicant
    still downloads what they uploaded. The audit export reads the files through the ORM and is
    unaffected (EmsErasmusExport)."""
    _inherit = 'ir.binary'

    def _get_stream_from(self, record, *args, **kwargs):
        if record._name == 'ir.attachment' and 'download_attachments' in record.env.context:
            documents = self._ems_confidential_documents(record)
            if documents:
                if record.env.context['download_attachments']:
                    raise UserError(_("This document is confidential: it can be viewed, not downloaded."))
                self._ems_note_view(record, documents)
        return super()._get_stream_from(record, *args, **kwargs)

    def _ems_confidential_documents(self, attachment):
        """The confidential documents holding this file (one search per model, on the relation's index)."""
        documents = []
        for model, (file_fields, _owner) in CONFIDENTIAL_FILES.items():
            domain = [('confidential', '=', True)]
            domain += ['|'] * (len(file_fields) - 1) + [(name, 'in', attachment.ids) for name in file_fields]
            documents.append(self.env[model].sudo().search(domain))
        return [document for found in documents for document in found]

    def _ems_note_view(self, attachment, documents):
        """'Who opened it and when' on the owner's history, once per person and file within VIEW_LOG_MINUTES."""
        user = self.env.user
        label = _("%(user)s viewed the confidential document \"%(file)s\"", user=user.name, file=attachment.name)
        for document in documents:
            owner = document[CONFIDENTIAL_FILES[document._name][1]]
            recent = self.env['mail.message'].sudo().search_count([
                ('model', '=', owner._name), ('res_id', '=', owner.id), ('author_id', '=', user.partner_id.id),
                ('date', '>=', fields.Datetime.now() - timedelta(minutes=VIEW_LOG_MINUTES)),
                ('body', 'ilike', str(escape(attachment.name))),
            ])
            if not recent:
                owner.sudo().message_post(body=label, author_id=user.partner_id.id,
                                          message_type='comment', subtype_xmlid='mail.mt_note')
