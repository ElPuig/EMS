# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import content_disposition, request


class EmsGroupPublicScheduleController(http.Controller):

    @http.route('/ems/schedule/<string:slug>.pdf', type='http', auth='public', methods=['GET'])
    def group_public_schedule(self, slug):
        """Issue #453 - streams the group's pre-rendered schedule PDF to anyone, no login. Never
        renders on request: a group whose first PDF isn't generated yet is a 404, same as an
        unknown slug or an archived group (excluded by the default active_test)."""
        group = request.env['ems.group'].sudo().search([('public_schedule_slug', '=', slug)], limit=1)
        if not group.public_schedule_pdf:
            raise request.not_found()
        stream = request.env['ir.binary']._get_stream_from(
            group, 'public_schedule_pdf', filename=f'{slug}.pdf', mimetype='application/pdf')
        return stream.get_response(as_attachment=False)

    @http.route('/ems/schedule/study/<string:slug>.pdf', type='http', auth='public', methods=['GET'])
    def study_public_schedule(self, slug):
        """Every active group's schedule of the study (or studies sharing an acronym) behind `slug`,
        in one PDF merged from the groups' own pre-rendered PDFs - see
        ems.study._get_public_schedule_pdf. 404 when no group has a PDF yet, same as an unknown slug."""
        studies = request.env['ems.study'].sudo().search([('public_schedule_slug', '=', slug)])
        content = studies._get_public_schedule_pdf()
        if not content:
            raise request.not_found()
        return request.make_response(content, headers=[
            ('Content-Type', 'application/pdf'),
            ('Content-Length', len(content)),
            ('Content-Disposition', content_disposition(f'{slug}.pdf', 'inline')),
        ])
