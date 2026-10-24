# -*- coding: utf-8 -*-

import re

from odoo import http
from odoo.exceptions import UserError
from odoo.http import content_disposition, request
from odoo.addons.portal.controllers.portal import CustomerPortal

from odoo.addons.ems.models.erasmus.application import ANSWER_FIELDS
from odoo.addons.ems.models.erasmus.mobility import PROPOSAL_FIELDS

BOOLEAN_ANSWERS = ('previous_mobility', 'fewer_opportunities', 'image_consent', 'declared_never_staff_mobility')
# Answers given as a month (<input type="month">, "YYYY-MM"), stored as the 1st of that month.
MONTH_ANSWERS = ('declared_last_mobility_date', 'declared_centre_start_date')


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
        calls = partner._ems_erasmus_calls() | applications.call_id
        values = self._prepare_portal_layout_values()
        values.update({
            'page_name': 'erasmus',
            'calls': calls,
            # Students' call art. 6: too many conduct warnings this course rule the student out.
            'blocked': calls.filtered(lambda call: call._ems_conduct_blocked(partner)),
            'applications': {application.call_id: application for application in applications},
            'state_labels': dict(applications._fields['state']._description_selection(request.env)),
            'tz': request.env['ems.datetime_utils'].company_tz_name(),
            'submitted': kwargs.get('submitted'),
            'guardian_mobilities': partner._ems_erasmus_guardian_mobilities(),
            'guardian_error': kwargs.get('error'),
        })
        return request.render('ems.portal_erasmus', values)

    @http.route('/my/erasmus/commitment/<int:mobility_id>', type='http', auth='user', methods=['POST'], website=True)
    def portal_erasmus_guardian_commitment(self, mobility_id, **post):
        """Issue #687: the family of a minor signs their commitment letter, only for a mobility of a
        child it acts for."""
        mobility = request.env.user.partner_id._ems_erasmus_guardian_mobilities().filtered(
            lambda mobility: mobility.id == mobility_id)
        if not mobility:
            return request.redirect(f'{self._redirect}?error=1')
        try:
            mobility.action_sign_commitment(bool(post.get('accepted')), request.httprequest.remote_addr, guardian=True)
        except UserError:
            return request.redirect(f'{self._redirect}?error=1')
        return request.redirect(self._redirect)

    @http.route('/my/erasmus/call/<int:call_id>', type='http', auth='user', website=True)
    def portal_erasmus_application(self, call_id, **kwargs):
        call = self._ems_erasmus_call(call_id)
        if not call:
            return request.redirect('/my/home')
        partner = request.env.user.partner_id
        application = request.env['ems.erasmus.application'].sudo().search([
            ('call_id', '=', call.id), ('partner_id', '=', partner.id)])
        blocked = call._ems_conduct_blocked(partner) and (not application or application.state in ('draft', 'subsanation'))
        values = self._prepare_portal_layout_values()
        values.update({
            'page_name': 'erasmus',
            'call': call,
            'application': application,
            'modality': application.modality_id or call._ems_modality_for(partner),
            'blocked': blocked,
            'editable': not blocked and (application._ems_portal_editable() if application else call.is_accepting),
            'correctable': application._ems_portal_correctable() if application and not blocked
            else application.document_ids.browse(),
            'documents': call.document_ids,
            'lines': {line.call_document_id: line for line in application.document_ids},
            'is_minor': call.audience == 'student' and not partner.is_adult,
            'language_labels': dict(request.env['ems.erasmus.application']._fields[
                'declared_language_level']._description_selection(request.env)),
            'activity_labels': dict(request.env['ems.erasmus.application']._fields['staff_activity']._description_selection(
                request.env)),
            'state_labels': dict(request.env['ems.erasmus.application']._fields['state']._description_selection(
                request.env)),
            'tz': request.env['ems.datetime_utils'].company_tz_name(),
            'error': kwargs.get('error'),
            'saved': kwargs.get('saved'),
            # Issue #685: results of the published resolutions, newest first, and the place offered.
            'result_lines': application.resolution_line_ids.filtered(
                lambda line: line.resolution_id.state == 'published').sorted(
                lambda line: line.resolution_id.publish_date, reverse=True),
            'result_labels': dict(request.env['ems.erasmus.resolution.line']._fields['result']._description_selection(
                request.env)),
            'offer': application.offer_ids.filtered(lambda offer: offer.state == 'pending')[:1],
            # Issue #687: the mobility of an accepted place.
            'mobility': application.mobility_ids[:1],
            'countries': request.env['res.country'].sudo().search([]),
            'mobility_state_labels': dict(request.env['ems.erasmus.mobility']._fields['state']._description_selection(
                request.env)),
            # The participant's record, in its four categories.
            'record_categories': request.env['ems.erasmus.application.document']._fields[
                'file_category']._description_selection(request.env),
            'file_state_labels': dict(request.env['ems.erasmus.application.document']._fields[
                'file_state']._description_selection(request.env)),
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
                answers.update({name: re.fullmatch(r'\d{4}-\d{2}', answers[name] or '') and f'{answers[name]}-01'
                                or False for name in MONTH_ANSWERS if name in answers})
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

    # --- issue #687: mobility preparation -------------------------------------------------------

    @http.route('/my/erasmus/call/<int:call_id>/mobility/<string:step>', type='http', auth='user', methods=['POST'],
                website=True)
    def portal_erasmus_mobility(self, call_id, step, **post):
        """The participant's own mobility of this call: choose a destination in their turn, send a
        proposal, upload documents, sign the commitment letter, answer a week's self-assessment or
        renounce the place."""
        call = self._ems_erasmus_call(call_id)
        if not call:
            return request.redirect('/my/home')
        page = f'{self._redirect}/call/{call.id}'
        mobility = request.env['ems.erasmus.mobility'].sudo().search([
            ('call_id', '=', call.id), ('partner_id', '=', request.env.user.partner_id.id)], limit=1)
        if not mobility:
            return request.redirect(f'{page}?error=1')
        try:
            if step == 'choose':
                destination = call.destination_ids.filtered(
                    lambda destination: str(destination.id) == post.get('destination_id'))
                if not destination:
                    return request.redirect(f'{page}?error=1')
                mobility.action_choose_destination(destination)
            elif step == 'propose':
                country = request.env['res.country'].sudo().browse(int(post.get('proposal_country_id') or 0)).exists()
                values = {name: (post.get(name) or '').strip()[:2000] or False for name in PROPOSAL_FIELDS}
                values['proposal_country_id'] = country.id
                values.update({name: re.fullmatch(r'\d{4}-\d{2}-\d{2}', values[name] or '') and values[name] or False
                               for name in ('proposal_date_start', 'proposal_date_end')})
                files = [(upload.filename, upload.read())
                         for upload in request.httprequest.files.getlist('proposal_files') if upload.filename]
                mobility._ems_portal_propose(values, files, declaration=bool(post.get('leave_declaration')))
            elif step == 'upload':
                uploads = {}
                for line in mobility.document_ids:
                    files = [(upload.filename, upload.read()) for upload in
                             request.httprequest.files.getlist(f'document_{line.call_document_id.id}')
                             if upload.filename]
                    if files:
                        uploads[line.call_document_id.id] = files
                mobility._ems_portal_upload(uploads)
            elif step == 'commitment':
                mobility.action_sign_commitment(bool(post.get('accepted')), request.httprequest.remote_addr)
            elif step == 'self_assessment':
                answers = {int(name[len('question_'):]): value for name, value in post.items()
                           if re.fullmatch(r'question_\d+', name)}
                week = post.get('week') or ''
                mobility._ems_portal_self_assessment(int(week) if week.isdigit() else 0, answers)
            elif step == 'renounce':
                mobility.action_renounce((post.get('reason') or '').strip()[:2000] or False)
            else:
                return request.redirect(f'{page}?error=1')
        except UserError:
            return request.redirect(f'{page}?error=1')
        return request.redirect(f'{page}?saved=1')

    @http.route('/my/erasmus/call/<int:call_id>/mobility/file/<int:attachment_id>', type='http', auth='user',
                website=True)
    def portal_erasmus_mobility_file(self, call_id, attachment_id, **kwargs):
        """Download a file of the logged-in user's own mobility: one the Erasmus team uploaded for
        them, or one they uploaded themselves."""
        call = self._ems_erasmus_call(call_id)
        mobility = call and request.env['ems.erasmus.mobility'].sudo().search([
            ('call_id', '=', call.id), ('partner_id', '=', request.env.user.partner_id.id)], limit=1)
        lines = mobility and mobility.document_ids
        attachment = mobility and (lines.prepared_attachment_ids | lines.attachment_ids).filtered(
            lambda attachment: attachment.id == attachment_id)
        if not attachment:
            return request.redirect(self._redirect)
        return request.env['ir.binary']._get_stream_from(attachment).get_response(as_attachment=True)
