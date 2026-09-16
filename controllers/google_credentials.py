# -*- coding: utf-8 -*-
import io
import zipfile

from odoo import _, http
from odoo.http import content_disposition, request


class EmsGoogleCredentialsController(http.Controller):

    @http.route('/ems/google_credentials/download', type='http', auth='user', methods=['GET'])
    def download_google_credentials(self, partner_ids=''):
        """Issue #478 - ZIP with the Google credentials PDF of each requested student. Runs with
        the user's own rights, so a hand-edited partner_ids list still only yields the PDFs the
        user can read; 404 when none is left."""
        ids = [int(partner_id) for partner_id in partner_ids.split(',') if partner_id.isdigit()]
        documents = request.env['res.partner'].browse(ids)._get_google_credentials_documents()
        if not documents:
            raise request.not_found()
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as archive:
            for document in documents:
                name = f'{document.partner_id.name} - {document.doc_file_name}'.replace('/', '-')
                archive.writestr(name, request.env['ir.binary']._get_stream_from(document, 'doc_file').read())
        return request.make_response(stream.getvalue(), headers=[
            ('Content-Type', 'application/zip'),
            ('Content-Disposition', content_disposition(f"{_('Google credentials')}.zip")),
        ])
