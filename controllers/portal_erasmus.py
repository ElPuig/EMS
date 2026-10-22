# -*- coding: utf-8 -*-

from odoo import http
from odoo.exceptions import UserError
from odoo.http import content_disposition, request
from odoo.addons.portal.controllers.portal import CustomerPortal

from odoo.addons.ems.models.erasmus.application import ANSWER_FIELDS

BOOLEAN_ANSWERS = ('previous_mobility', 'fewer_opportunities', 'image_consent', 'host_not_identified',
                   'accompany_students')


class EmsPortalErasmusController(CustomerPortal):
    """Issue #683 - Erasmus+ applications on the portal. The applicant is always the logged-in
    user's own partner: no partner or application id travels in a form. sudo because portal users
    have no ACL on the Erasmus models; every route checks eligibility itself. See
    docs/en/developers/erasmus/erasmus.md."""

    _redirect = '/my/erasmus'

    def _ems_erasmus_call(self, call_id):
        """The published call `call_id` if the logged-in user can apply to it, or has applied."""
        partner = request.env.user.partner_id
        call = request.env['ems.erasmus.call'].sudo().browse(call_id).exists()
        if call and (call in partner._ems_erasmus_calls()
                     or call in partner._ems_erasmus_applications().call_id):
            return call
        return None

    @http.route('/my/erasmus', type='http', auth='user', website=True)
    def portal_erasmus(self, **kwargs):
        partner = request.env.user.partner_id
        if not partner._ems_erasmus_portal_visible():
            return request.redirect('/my/home')
        applications = partner._ems_erasmus_applications()
        values = self._prepare_portal_layout_values()
        values.update({
            'page_name': 'erasmus',
            'calls': partner._ems_erasmus_calls() | applications.call_id,
            'applications': {application.call_id: application for application in applications},
            'state_labels': dict(applications._fields['state'].selection),
            'tz': request.env['ems.datetime_utils'].company_tz_name(),
            'submitted': kwargs.get('submitted'),
        })
        return request.render('ems.portal_erasmus', values)

    @http.route('/my/erasmus/call/<int:call_id>', type='http', auth='user', website=True)
    def portal_erasmus_application(self, call_id, **kwargs):
        call = self._ems_erasmus_call(call_id)
        if not call:
            return request.redirect('/my/home')
        partner = request.env.user.partner_id
        application = request.env['ems.erasmus.application'].sudo().search([
            ('call_id', '=', call.id), ('partner_id', '=', partner.id)])
        values = self._prepare_portal_layout_values()
        values.update({
            'page_name': 'erasmus',
            'call': call,
            'application': application,
            'modality': application.modality_id or call._ems_modality_for(partner),
            'editable': application._ems_portal_editable() if application else call.is_accepting,
            'correctable': application._ems_portal_correctable() if application else application.document_ids,
            'documents': call.document_ids,
            'lines': {line.call_document_id: line for line in application.document_ids},
            'is_minor': call.audience == 'student' and not partner.is_adult,
            'activity_labels': dict(request.env['ems.erasmus.application']._fields['staff_activity']._description_selection(
                request.env)),
            'state_labels': dict(request.env['ems.erasmus.application']._fields['state'].selection),
            'tz': request.env['ems.datetime_utils'].company_tz_name(),
            'error': kwargs.get('error'),
            'saved': kwargs.get('saved'),
            # Issue #685: results of the published resolutions, newest first, and the place offered.
            'result_lines': application.resolution_line_ids.filtered(
                lambda line: line.resolution_id.state == 'published').sorted(
                lambda line: line.resolution_id.publish_date, reverse=True),
            'result_labels': dict(request.env['ems.erasmus.resolution.line']._fields['result'].selection),
            'offer': application.offer_ids.filtered(lambda offer: offer.state == 'pending')[:1],
            'answered': kwargs.get('answered'),
        })
        return request.render('ems.portal_erasmus_application', values)

    @http.route('/my/erasmus/call/<int:call_id>/save', type='http', auth='user', methods=['POST'], website=True)
    def portal_erasmus_save(self, call_id, **post):
        call = self._ems_erasmus_call(call_id)
        if not call:
            return request.redirect('/my/home')
        page = f'{self._redirect}/call/{call.id}'
        Application = request.env['ems.erasmus.application'].sudo()
        try:
            application = Application._ems_portal_get_or_create(call, request.env.user.partner_id)
            answers = {}
            names = ANSWER_FIELDS[application.audience]
            if application._ems_portal_editable():
                answers = {name: bool(post.get(name)) if name in BOOLEAN_ANSWERS
                           else (post.get(name) or '').strip()[:2000] or False for name in names}
            elif any(post.get(name) for name in names):
                # Answers sent after the closing date: refused, nothing saved.
                return request.redirect(f'{page}?error=1')
            uploads = {}
            for document in call.document_ids:
                files = [(upload.filename, upload.read())
                         for upload in request.httprequest.files.getlist(f'document_{document.id}')
                         if upload.filename]
                if files:
                    uploads[document.id] = files
            application._ems_portal_save(answers, uploads)
            if post.get('submit'):
                application.action_submit()
        except UserError:
            return request.redirect(f'{page}?error=1')
        if post.get('submit'):
            return request.redirect(f'{self._redirect}?submitted=1')
        return request.redirect(f'{page}?saved=1')

    @http.route('/my/erasmus/call/<int:call_id>/rules', type='http', auth='user', website=True)
    def portal_erasmus_rules(self, call_id, **kwargs):
        call = self._ems_erasmus_call(call_id)
        if not (call and call.rules_document):
            return request.redirect(self._redirect)
        return request.env['ir.binary']._get_stream_from(
            call, 'rules_document', filename_field='rules_filename').get_response(
            as_attachment=True)

    # --- issue #685: resolutions and place offers ----------------------------------------------

    def _ems_erasmus_resolution(self, call_id, resolution_id):
        """A published resolution of a call the logged-in user applied to."""
        call = self._ems_erasmus_call(call_id)
        if not call or call not in request.env.user.partner_id._ems_erasmus_applications().call_id:
            return None
        return call._ems_published_resolutions().filtered(lambda resolution: resolution.id == resolution_id)

    @http.route('/my/erasmus/call/<int:call_id>/resolution/<int:resolution_id>', type='http', auth='user',
                website=True)
    def portal_erasmus_resolution(self, call_id, resolution_id, **kwargs):
        resolution = self._ems_erasmus_resolution(call_id, resolution_id)
        if not resolution:
            return request.redirect(self._redirect)
        values = self._prepare_portal_layout_values()
        values.update({'page_name': 'erasmus', 'resolution': resolution})
        return request.render('ems.portal_erasmus_resolution', values)

    @http.route('/my/erasmus/call/<int:call_id>/resolution/<int:resolution_id>/pdf', type='http', auth='user',
                website=True)
    def portal_erasmus_resolution_pdf(self, call_id, resolution_id, **kwargs):
        resolution = self._ems_erasmus_resolution(call_id, resolution_id)
        if not resolution:
            return request.redirect(self._redirect)
        pdf, _type = request.env['ir.actions.report'].sudo()._render_qweb_pdf(
            'ems.action_report_erasmus_resolution', resolution.ids)
        return request.make_response(pdf, headers=[
            ('Content-Type', 'application/pdf'),
            ('Content-Disposition', content_disposition(f'{resolution.name}.pdf')),
        ])

    @http.route('/my/erasmus/call/<int:call_id>/offer', type='http', auth='user', methods=['POST'], website=True)
    def portal_erasmus_offer(self, call_id, answer=None, reason=None, **kwargs):
        """Accept or renounce the place offered to the logged-in user in this call."""
        call = self._ems_erasmus_call(call_id)
        if not call:
            return request.redirect('/my/home')
        page = f'{self._redirect}/call/{call.id}'
        offer = request.env['ems.erasmus.offer'].sudo().search([
            ('call_id', '=', call.id), ('partner_id', '=', request.env.user.partner_id.id),
            ('state', '=', 'pending')], limit=1)
        if not offer or answer not in ('accept', 'renounce'):
            return request.redirect(f'{page}?error=1')
        try:
            if answer == 'accept':
                offer.action_accept()
            else:
                offer.action_renounce((reason or '').strip()[:2000] or False)
        except UserError:
            return request.redirect(f'{page}?error=1')
        return request.redirect(f'{page}?answered=1')
