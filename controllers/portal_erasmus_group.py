# -*- coding: utf-8 -*-

from odoo import http
from odoo.exceptions import UserError
from odoo.http import request

from .portal_erasmus import EmsPortalErasmusController


class EmsPortalErasmusGroupController(EmsPortalErasmusController):
    """Issue #701 - group mobilities on the portal: a student enrols with one click and withdraws
    while the enrolment is open; once selected, they hand in their documents (issue #703). The
    student is always the logged-in user's own partner: no partner or enrolment id travels in a
    form. sudo because portal users have no ACL on the Erasmus models; every route checks the
    mobility is one the student can see (`res.partner._ems_erasmus_group_mobilities`). See
    docs/en/developers/erasmus/group_mobility.md."""

    _redirect = '/my/erasmus'

    def _ems_group_mobility(self, mobility_id):
        partner = request.env.user.partner_id
        return partner._ems_erasmus_group_mobilities().filtered(lambda mobility: mobility.id == mobility_id)

    def _ems_group_participant(self, mobility):
        """The logged-in student's own file in `mobility`, once selected."""
        return mobility.participant_ids.filtered(
            lambda participant: participant.partner_id == request.env.user.partner_id and participant.role == 'student')

    def _ems_group_resolution(self, mobility_id, resolution_id):
        """A published list of a group mobility the logged-in student enrolled in."""
        mobility = self._ems_group_mobility(mobility_id)
        if not mobility.registration_ids.filtered(lambda registration: registration.partner_id ==
                                                  request.env.user.partner_id):
            return None
        return mobility.resolution_ids.filtered(lambda resolution: resolution.id == resolution_id
                                                and resolution.state == 'published')

    @http.route('/my/erasmus/group/<int:mobility_id>/resolution/<int:resolution_id>', type='http', auth='user',
                website=True)
    def portal_erasmus_group_resolution(self, mobility_id, resolution_id, **kwargs):
        resolution = self._ems_group_resolution(mobility_id, resolution_id)
        if not resolution:
            return request.redirect(self._redirect)
        return self._ems_render_resolution(resolution, self._redirect,
                                           f'{self._redirect}/group/{mobility_id}/resolution/{resolution.id}')

    @http.route('/my/erasmus/group/<int:mobility_id>/resolution/<int:resolution_id>/pdf', type='http', auth='user',
                website=True)
    def portal_erasmus_group_resolution_pdf(self, mobility_id, resolution_id, **kwargs):
        resolution = self._ems_group_resolution(mobility_id, resolution_id)
        if not resolution:
            return request.redirect(self._redirect)
        return self._ems_resolution_pdf(resolution)

    @http.route('/my/erasmus/group/<int:mobility_id>/enrol', type='http', auth='user', methods=['POST'], website=True)
    def portal_erasmus_group_enrol(self, mobility_id, **post):
        mobility = self._ems_group_mobility(mobility_id)
        if not mobility:
            return request.redirect('/my/home')
        try:
            request.env['ems.erasmus.group.registration'].sudo()._ems_portal_enrol(
                mobility, request.env.user.partner_id, bool(post.get('fewer_opportunities')))
        except UserError:
            return request.redirect(f'{self._redirect}?group_error=1')
        return request.redirect(f'{self._redirect}?enrolled=1')

    @http.route('/my/erasmus/group/<int:mobility_id>/withdraw', type='http', auth='user', methods=['POST'],
                website=True)
    def portal_erasmus_group_withdraw(self, mobility_id, **post):
        mobility = self._ems_group_mobility(mobility_id)
        registration = mobility.registration_ids.filtered(
            lambda registration: registration.partner_id == request.env.user.partner_id)
        if not registration:
            return request.redirect('/my/home')
        try:
            registration.action_withdraw()
        except UserError:
            return request.redirect(f'{self._redirect}?group_error=1')
        return request.redirect(self._redirect)

    @http.route('/my/erasmus/group/<int:mobility_id>', type='http', auth='user', website=True)
    def portal_erasmus_group(self, mobility_id, **kwargs):
        """The selected student's file: the mobility, their documents, and renouncing the place."""
        mobility = self._ems_group_mobility(mobility_id)
        participant = mobility and self._ems_group_participant(mobility)
        if not participant:
            return request.redirect(self._redirect)
        values = self._prepare_portal_layout_values()
        values.update({
            'page_name': 'erasmus',
            'mobility': mobility,
            'participant': participant,
            'registration': mobility.registration_ids.filtered(lambda registration: registration.participant_id ==
                                                               participant),
            'file_state_labels': dict(request.env['ems.erasmus.application.document']._fields[
                'file_state']._description_selection(request.env)),
            'category_labels': dict(request.env['ems.erasmus.application.document']._fields[
                'file_category']._description_selection(request.env)),
            'tz': request.env['ems.datetime_utils'].company_tz_name(),
            'error': kwargs.get('error'),
            'saved': kwargs.get('saved'),
        })
        return request.render('ems.portal_erasmus_group', values)

    @http.route('/my/erasmus/group/<int:mobility_id>/<string:step>', type='http', auth='user', methods=['POST'],
                website=True)
    def portal_erasmus_group_step(self, mobility_id, step, **post):
        """Upload documents, accept the commitment letter, or renounce the place."""
        mobility = self._ems_group_mobility(mobility_id)
        participant = mobility and self._ems_group_participant(mobility)
        if not participant:
            return request.redirect(self._redirect)
        page = f'{self._redirect}/group/{mobility.id}'
        try:
            if step == 'upload':
                uploads = {}
                for line in participant.document_ids:
                    files = [(upload.filename, upload.read()) for upload in
                             request.httprequest.files.getlist(f'document_{line.call_document_id.id}')
                             if upload.filename]
                    if files:
                        uploads[line.call_document_id.id] = files
                participant._ems_portal_upload(uploads)
            elif step == 'commitment':
                participant.action_sign_commitment(bool(post.get('accepted')), request.httprequest.remote_addr)
            elif step == 'renounce':
                participant.registration_ids.action_renounce((post.get('reason') or '').strip()[:2000] or False)
                return request.redirect(self._redirect)
            else:
                return request.redirect(f'{page}?error=1')
        except UserError:
            return request.redirect(f'{page}?error=1')
        return request.redirect(f'{page}?saved=1')

    @http.route('/my/erasmus/group/commitment/<int:participant_id>', type='http', auth='user', methods=['POST'],
                website=True)
    def portal_erasmus_group_guardian_commitment(self, participant_id, **post):
        """The family of a minor accepts their commitment letter, only for a child it acts for (the
        same as the internship mobilities')."""
        participant = request.env.user.partner_id._ems_erasmus_guardian_group_participants().filtered(
            lambda participant: participant.id == participant_id)
        if not participant:
            return request.redirect(f'{self._redirect}?error=1')
        try:
            participant.action_sign_commitment(bool(post.get('accepted')), request.httprequest.remote_addr,
                                               guardian=True)
        except UserError:
            return request.redirect(f'{self._redirect}?error=1')
        return request.redirect(self._redirect)

    @http.route('/my/erasmus/group/<int:mobility_id>/file/<int:attachment_id>', type='http', auth='user',
                website=True)
    def portal_erasmus_group_file(self, mobility_id, attachment_id, **kwargs):
        """Download a document the Erasmus team uploaded for the logged-in student (their own, or
        the group's shared one that is not confidential)."""
        mobility = self._ems_group_mobility(mobility_id)
        participant = mobility and self._ems_group_participant(mobility)
        if not participant:
            return request.redirect(self._redirect)
        lines = participant.document_ids | mobility.document_ids.filtered(lambda line: not line.confidential)
        attachment = (lines.prepared_attachment_ids | lines.filtered(
            lambda line: line.handled_by == 'team').attachment_ids).filtered(
            lambda attachment: attachment.id == attachment_id)
        if not attachment:
            return request.redirect(self._redirect)
        return request.env['ir.binary']._get_stream_from(attachment).get_response(as_attachment=True)
