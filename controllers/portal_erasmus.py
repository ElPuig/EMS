# -*- coding: utf-8 -*-

import re

from odoo import http
from odoo.exceptions import UserError
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal

from odoo.addons.ems.models.erasmus.application import ANSWER_FIELDS, PORTAL_STATE_BADGES
from odoo.addons.ems.models.erasmus.mobility import PROPOSAL_FIELDS
from odoo.addons.ems.models.erasmus.satisfaction import LOW_SCORE

BOOLEAN_ANSWERS = ('fewer_opportunities', 'image_consent', 'declared_never_staff_mobility')
# Answers given as a month (<input type="month">, "YYYY-MM"), stored as the 1st of that month.
MONTH_ANSWERS = ('declared_centre_start_date',)


class EmsPortalErasmusController(CustomerPortal):
    """Issue #683 - Erasmus+ applications on the portal. The applicant is always the logged-in
    user's own partner: no partner or application id travels in a form. sudo because portal users
    have no ACL on the Erasmus models; every route checks eligibility itself. See
    docs/en/developers/erasmus/erasmus.md."""

    _erasmus_redirect = '/my/erasmus'
    # Staff apply and prepare their mobility in the backend, never on the portal (the 2026-11-04 review).
    _staff_redirect = '/odoo/action-ems.action_erasmus_staff_calls'

    @staticmethod
    def _ems_error_redirect(page, error):
        """Back to the page, showing why the action was refused: a UserError is written for the
        person in front of the portal ("Upload the required documents first: ..."), and a generic
        message left them guessing which document was missing (usage test, 2026-11-04)."""
        request.session['ems_erasmus_error'] = error.args[0] if error.args else ''
        return request.redirect(f'{page}?error=1')

    @staticmethod
    def _ems_error_message(kwargs):
        return request.session.pop('ems_erasmus_error', None) if kwargs.get('error') else None

    def _ems_erasmus_call(self, call_id):
        """The published call `call_id` if the logged-in user can apply to it, or has applied. Never
        for an internal user: staff calls are handled in the backend."""
        if not request.env.user.share:
            return None
        partner = request.env.user.partner_id
        call = request.env['ems.erasmus.call'].sudo().browse(call_id).exists()
        if call and (call in partner._ems_erasmus_calls()
                     or call in partner._ems_erasmus_applications().call_id):
            return call
        return None

    @http.route('/my/erasmus', type='http', auth='user', website=True)
    def portal_erasmus(self, **kwargs):
        if not request.env.user.share:
            return request.redirect(self._staff_redirect)
        partner = request.env.user.partner_id
        # Right after answering the last pending satisfaction survey the page may have nothing else to
        # show: it still opens, to thank them (the 2026-11-05 usage test).
        if not partner._ems_erasmus_portal_visible() and not kwargs.get('satisfaction_answered'):
            return request.redirect('/my/home')
        applications = partner._ems_erasmus_applications()
        calls = partner._ems_erasmus_calls() | applications.call_id
        # The issue-#682 review: the person's own applications first, then the calls they can apply
        # to now, and the rest (not open yet, or closed) folded away at the end.
        open_calls = calls.filtered(lambda call: call.is_accepting) - applications.call_id
        values = self._prepare_portal_layout_values()
        values.update({
            'page_name': 'erasmus',
            'calls': calls,
            'my_calls': applications.call_id,
            'open_calls': open_calls,
            'other_calls': calls - applications.call_id - open_calls,
            'progress': {application.call_id: application._ems_portal_progress() for application in applications},
            'state_badges': PORTAL_STATE_BADGES,
            'applications': {application.call_id: application for application in applications},
            'state_labels': dict(applications._fields['state']._description_selection(request.env)),
            'tz': request.env['ems.datetime_utils'].company_tz_name(),
            'submitted': kwargs.get('submitted'),
            'guardian_mobilities': partner._ems_erasmus_guardian_mobilities(),
            'guardian_applications': partner._ems_erasmus_guardian_applications(),
            'guardian_error': kwargs.get('error'),
            'satisfaction_surveys': partner._ems_erasmus_satisfaction_pending(),
            'satisfaction_answered': kwargs.get('satisfaction_answered'),
        })
        return request.render('ems.portal_erasmus', values)

    # --- satisfaction survey (docs/en/developers/erasmus/quality.md) ------------------------------

    def _ems_satisfaction_survey(self, survey_id):
        """The logged-in user's own pending satisfaction survey `survey_id`, if any."""
        return request.env.user.partner_id._ems_erasmus_satisfaction_pending().filtered(
            lambda survey: survey.id == survey_id)

    def _ems_satisfaction_render(self, survey, **values):
        page = self._prepare_portal_layout_values()
        page.update({'page_name': 'erasmus', 'survey': survey, 'low_score': LOW_SCORE, **values})
        return request.render('ems.portal_erasmus_satisfaction', page)

    @http.route('/my/erasmus/satisfaction/<int:survey_id>', type='http', auth='user', website=True)
    def portal_erasmus_satisfaction(self, survey_id, **kwargs):
        survey = self._ems_satisfaction_survey(survey_id)
        if not survey:
            return request.redirect(self._erasmus_redirect)
        return self._ems_satisfaction_render(survey)

    @http.route('/my/erasmus/satisfaction/<int:survey_id>/answer', type='http', auth='user', methods=['POST'],
                website=True)
    def portal_erasmus_satisfaction_answer(self, survey_id, **post):
        """A score of 6 or lower shows the confirmation step first (is it right?), which also asks
        what did not work; any other score is saved at once."""
        survey = self._ems_satisfaction_survey(survey_id)
        if not survey:
            return request.redirect(self._erasmus_redirect)
        score = int(post['score']) if (post.get('score') or '').isdigit() else 0
        what_failed = (post.get('what_failed') or '').strip()[:4000]
        comment = (post.get('comment') or '').strip()[:4000]
        if not 1 <= score <= 10:
            return self._ems_satisfaction_render(survey, error=True, comment=comment)
        if score <= LOW_SCORE and not (post.get('confirmed') and what_failed):
            return self._ems_satisfaction_render(survey, confirm=True, score=score, comment=comment,
                                                 what_failed=what_failed, error=bool(post.get('confirmed')))
        try:
            survey._ems_portal_answer(score, what_failed, comment)
        except UserError:
            return self._ems_satisfaction_render(survey, error=True, comment=comment)
        return request.redirect(f'{self._erasmus_redirect}?satisfaction_answered=1')

    @http.route('/my/erasmus/commitment/<int:mobility_id>', type='http', auth='user', methods=['POST'], website=True)
    def portal_erasmus_guardian_commitment(self, mobility_id, **post):
        """Issue #687: the family of a minor signs their commitment letter, only for a mobility of a
        child it acts for."""
        mobility = request.env.user.partner_id._ems_erasmus_guardian_mobilities().filtered(
            lambda mobility: mobility.id == mobility_id)
        if not mobility:
            return request.redirect(f'{self._erasmus_redirect}?error=1')
        try:
            mobility.action_sign_commitment(bool(post.get('accepted')), request.httprequest.remote_addr, guardian=True)
        except UserError:
            return request.redirect(f'{self._erasmus_redirect}?error=1')
        return request.redirect(self._erasmus_redirect)

    @http.route('/my/erasmus/call/<int:call_id>', type='http', auth='user', website=True)
    def portal_erasmus_application(self, call_id, **kwargs):
        if not request.env.user.share:
            return request.redirect(self._staff_redirect)
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
            'correctable': application._ems_portal_correctable() if application else application.document_ids.browse(),
            'documents': call.document_ids,
            'lines': {line.call_document_id: line for line in application.document_ids},
            'is_minor': call.audience == 'student' and not partner.is_adult,
            'language_labels': dict(request.env['ems.erasmus.application']._fields[
                'declared_language_level']._description_selection(request.env)),
            'activity_labels': dict(request.env['ems.erasmus.mobility']._fields['proposal_activity']._description_selection(
                request.env)),
            'state_labels': dict(request.env['ems.erasmus.application']._fields['state']._description_selection(
                request.env)),
            'state_badges': PORTAL_STATE_BADGES,
            'progress': application._ems_portal_progress() if application else None,
            'tz': request.env['ems.datetime_utils'].company_tz_name(),
            'error': kwargs.get('error'),
            'error_message': self._ems_error_message(kwargs),
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
            'todo_state_labels': dict(request.env['ems.erasmus.application.document']._fields[
                'todo_state']._description_selection(request.env)),
            'answered': kwargs.get('answered'),
            'claimed': kwargs.get('claimed'),
            'claimable': application._ems_portal_claimable() if application else None,
            'claim_state_labels': dict(request.env['ems.erasmus.claim']._fields['state']._description_selection(
                request.env)),
        })
        return request.render('ems.portal_erasmus_application', values)

    @http.route('/my/erasmus/call/<int:call_id>/save', type='http', auth='user', methods=['POST'], website=True)
    def portal_erasmus_save(self, call_id, **post):
        call = self._ems_erasmus_call(call_id)
        if not call:
            return request.redirect('/my/home')
        page = f'{self._erasmus_redirect}/call/{call.id}'
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
            links = {document.id: post.get(f'link_{document.id}') for document in call.document_ids
                     if document.upload_kind == 'link' and post.get(f'link_{document.id}')}
            application._ems_portal_save(answers, uploads, links)
            if post.get('submit'):
                application.action_submit()
        except UserError as error:
            return self._ems_error_redirect(page, error)
        if post.get('submit'):
            return request.redirect(f'{self._erasmus_redirect}?submitted=1')
        return request.redirect(f'{page}?saved=1')

    @http.route('/my/erasmus/call/<int:call_id>/file/<int:attachment_id>/remove', type='http', auth='user',
                methods=['POST'], website=True)
    def portal_erasmus_remove_file(self, call_id, attachment_id, **post):
        """The applicant removes a file uploaded by mistake, while the application is a draft."""
        call = self._ems_erasmus_call(call_id)
        if not call:
            return request.redirect('/my/home')
        page = f'{self._erasmus_redirect}/call/{call.id}'
        application = request.env['ems.erasmus.application'].sudo().search([
            ('call_id', '=', call.id), ('partner_id', '=', request.env.user.partner_id.id)])
        try:
            application._ems_portal_remove_file(attachment_id)
        except UserError as error:
            return self._ems_error_redirect(page, error)
        return request.redirect(f'{page}?saved=1')

    @http.route('/my/erasmus/call/<int:call_id>/template/<int:document_id>', type='http', auth='user', website=True)
    def portal_erasmus_template(self, call_id, document_id, **kwargs):
        """Download the model of a document of a call the logged-in user can see (e.g. the family
        authorisation)."""
        call = self._ems_erasmus_call(call_id) or request.env.user.partner_id._ems_erasmus_guardian_applications(
            ).call_id.filtered(lambda call: call.id == call_id)
        document = call and call.sudo().document_ids.filtered(lambda line: line.id == document_id and line.template_file)
        if not document:
            return request.redirect(self._erasmus_redirect)
        return request.env['ir.binary']._get_stream_from(
            document, 'template_file', filename=document.template_filename).get_response(as_attachment=True)

    @http.route('/my/erasmus/call/<int:call_id>/rules', type='http', auth='user', website=True)
    def portal_erasmus_rules(self, call_id, **kwargs):
        call = self._ems_erasmus_call(call_id)
        if not (call and call.rules_document):
            return request.redirect(self._erasmus_redirect)
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
            return request.redirect(self._erasmus_redirect)
        return self._ems_render_resolution(resolution, f'{self._erasmus_redirect}/call/{call_id}',
                                           f'{self._erasmus_redirect}/call/{call_id}/resolution/{resolution.id}')

    def _ems_render_resolution(self, resolution, back_url, list_url):
        """A published list's page (a call's or a group mobility's)."""
        values = self._prepare_portal_layout_values()
        # The issue-#682 review: the applicant finds their own row (only on the portal, never in the PDF).
        values.update({'page_name': 'erasmus', 'resolution': resolution, 'back_url': back_url, 'list_url': list_url,
                       'my_partner': request.env.user.partner_id})
        return request.render('ems.portal_erasmus_resolution', values)

    @http.route('/my/erasmus/call/<int:call_id>/resolution/<int:resolution_id>/pdf', type='http', auth='user',
                website=True)
    def portal_erasmus_resolution_pdf(self, call_id, resolution_id, **kwargs):
        resolution = self._ems_erasmus_resolution(call_id, resolution_id)
        if not resolution:
            return request.redirect(self._erasmus_redirect)
        return self._ems_resolution_pdf(resolution)

    def _ems_resolution_pdf(self, resolution):
        return resolution._ems_pdf_response()

    @http.route('/my/erasmus/call/<int:call_id>/claim', type='http', auth='user', methods=['POST'], website=True)
    def portal_erasmus_claim(self, call_id, description=None, **kwargs):
        """A claim against the provisional resolution, with its files (the issue-#682 review)."""
        call = self._ems_erasmus_call(call_id)
        if not call:
            return request.redirect('/my/home')
        page = f'{self._erasmus_redirect}/call/{call.id}'
        application = request.env['ems.erasmus.application'].sudo().search([
            ('call_id', '=', call.id), ('partner_id', '=', request.env.user.partner_id.id)])
        files = [(upload.filename, upload.read()) for upload in request.httprequest.files.getlist('claim_files')
                 if upload.filename]
        try:
            if not application:
                return request.redirect(f'{page}?error=1')
            application._ems_portal_claim(description, files)
        except UserError as error:
            return self._ems_error_redirect(page, error)
        return request.redirect(f'{page}?claimed=1')

    @http.route('/my/erasmus/call/<int:call_id>/offer', type='http', auth='user', methods=['POST'], website=True)
    def portal_erasmus_offer(self, call_id, answer=None, reason=None, **kwargs):
        """Accept or renounce the place offered to the logged-in user in this call."""
        call = self._ems_erasmus_call(call_id)
        if not call:
            return request.redirect('/my/home')
        page = f'{self._erasmus_redirect}/call/{call.id}'
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
        except UserError as error:
            return self._ems_error_redirect(page, error)
        return request.redirect(f'{page}?answered=1')

    # --- issue #687: mobility preparation -------------------------------------------------------

    @http.route('/my/erasmus/call/<int:call_id>/mobility/<string:step>', type='http', auth='user', methods=['POST'],
                website=True)
    def portal_erasmus_mobility(self, call_id, step, **post):
        """The participant's own mobility of this call: choose a destination in their turn, send a
        proposal, upload documents, sign the commitment letter, answer a week's self-assessment, say
        the EU Survey is answered or renounce the place."""
        call = self._ems_erasmus_call(call_id)
        if not call:
            return request.redirect('/my/home')
        page = f'{self._erasmus_redirect}/call/{call.id}'
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
            elif step == 'eu_survey':
                mobility._ems_portal_eu_survey()
            elif step == 'renounce':
                mobility.action_renounce((post.get('reason') or '').strip()[:2000] or False)
            else:
                return request.redirect(f'{page}?error=1')
        except UserError as error:
            return self._ems_error_redirect(page, error)
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
            return request.redirect(self._erasmus_redirect)
        return request.env['ir.binary']._get_stream_from(attachment).get_response(as_attachment=True)
