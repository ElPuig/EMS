# -*- coding: utf-8 -*-

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
