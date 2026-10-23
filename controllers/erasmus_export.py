# -*- coding: utf-8 -*-

from werkzeug.wsgi import wrap_file

from odoo import _, http
from odoo.exceptions import AccessError, UserError
from odoo.http import content_disposition, request


class EmsErasmusExportController(http.Controller):

    @http.route('/ems/erasmus/participants', type='http', auth='user', methods=['GET'])
    def download_participants(self, application_ids=''):
        """Issue #685 - the .xlsx of the people who accepted an Erasmus+ place. Built on the fly
        and never stored (it carries personal and bank data); Erasmus team only."""
        ids = [int(application_id) for application_id in application_ids.split(',') if application_id.isdigit()]
        try:
            content = request.env['ems.erasmus.application'].browse(ids).exists()._ems_participants_xlsx()
        except (AccessError, UserError):
            raise request.not_found()
        return request.make_response(content, headers=[
            ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
            ('Content-Disposition', content_disposition(f"{_('Erasmus+ participants')}.xlsx")),
        ])

    @http.route('/ems/erasmus/project/<int:project_id>/dossier', type='http', auth='user', methods=['GET'])
    def download_dossier(self, project_id):
        """Issue #697 - a project's dossier, every document in SEPIE's folders, as a ZIP built on
        the fly in a temporary file and streamed (never held whole in memory, never stored);
        Erasmus team and Secretary only."""
        project = request.env['ems.erasmus.project'].browse(project_id).exists()
        try:
            archive = project and project._ems_dossier_zip()
        except AccessError:
            archive = None
        if not archive:
            raise request.not_found()
        size = archive.seek(0, 2)
        archive.seek(0)
        response = request.make_response(wrap_file(request.httprequest.environ, archive), headers=[
            ('Content-Type', 'application/zip'),
            ('Content-Length', str(size)),
            ('Content-Disposition', content_disposition(f"{project.name}.zip")),
        ])
        response.direct_passthrough = True
        return response
