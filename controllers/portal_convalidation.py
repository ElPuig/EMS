# -*- coding: utf-8 -*-

import base64

from odoo import http
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal

from odoo.addons.ems.models.grades.convalidation import REVIEW_STATES


class EmsPortalConvalidationController(CustomerPortal):
    """Issues #276 and #529 - subject convalidation requests on the portal. An adult student
    files them himself, and so does his family when he authorized sharing with it; a minor's
    family files them for him, and the minor himself only reads them
    (res.partner._ems_convalidation_can_request). Always about the student resolved by
    get_portal_student(): no student id travels in a form, so nobody can file or cancel a request
    for someone else. New requests only during the yearly request period set in the EMS settings;
    answering and cancelling are always possible. sudo because portal users have no ACL on
    ems.convalidation - see docs/en/developers/grades/convalidation.md."""

    _redirect = '/my/convalidaciones'

    def _ems_convalidation_student(self):
        """The student the portal user may file and follow up requests for, or an empty
        recordset."""
        partner = request.env.user.partner_id
        student = partner.get_portal_student()
        return student if partner._ems_convalidation_can_request(student) else student.browse()

    def _ems_convalidation_company(self):
        return request.env.company.sudo()

    @http.route('/my/convalidaciones', type='http', auth='user', website=True)
    def portal_convalidations(self, **kwargs):
        partner = request.env.user.partner_id
        if not partner._ems_convalidation_portal_visible():
            return request.redirect('/my/home')
        viewed = partner.get_portal_student()
        student = self._ems_convalidation_student()
        company = self._ems_convalidation_company()
        Convalidation = request.env['ems.convalidation'].sudo()
        study = Convalidation._ems_portal_study(student) if student else request.env['ems.study']
        convalidations = Convalidation.search([('student_id', '=', viewed.id)])
        # fields_get(): selection labels in the visitor's language.
        selections = Convalidation.fields_get(['state', 'basis', 'prior_studies_origin'], ['selection'])
        line_states = request.env['ems.convalidation.line'].sudo().fields_get(['state'], ['selection'])
        values = self._prepare_portal_layout_values()
        values.update({
            'page_name': 'convalidations',
            'student': viewed,
            'can_request': bool(student),
            # A minor reading his own page: why he cannot file a request himself.
            'minor_without_family': not student and not viewed.is_adult and not viewed._ems_family_contacts(),
            'students': partner.get_portal_students(),
            'viewing_as_family': viewed != partner,
            'period_open': company._ems_convalidation_period_open(),
            'period_next_change': company._ems_convalidation_period_next_change(),
            # The period is the centre's local time: shown in it whatever the visitor's own tz.
            'period_tz': company.partner_id.tz,
            'study': study,
            'requestable_subjects': Convalidation._ems_portal_requestable_subjects(student, study)
            if study else request.env['ems.subject'],
            'convalidations': convalidations,
            'basis_options': selections['basis']['selection'],
            'origin_options': selections['prior_studies_origin']['selection'],
            'state_labels': dict(selections['state']['selection']),
            'line_state_labels': dict(line_states['state']['selection']),
            'error': kwargs.get('error'),
            'submitted': kwargs.get('submitted'),
            'replied': kwargs.get('replied'),
            # ?new=1 opens the (folded by default) new-request form, as a direct link to it.
            'open_new': bool(kwargs.get('new')),
        })
        return request.render('ems.portal_convalidations', values)

    @http.route('/my/convalidaciones/submit', type='http', auth='user', methods=['POST'], website=True)
    def portal_convalidation_submit(self, **post):
        student = self._ems_convalidation_student()
        if not student:
            return request.redirect(self._redirect)
        if not self._ems_convalidation_company()._ems_convalidation_period_open():
            return request.redirect(f'{self._redirect}?error=closed')
        Convalidation = request.env['ems.convalidation'].sudo()
        study = Convalidation._ems_portal_study(student)
        if not study:
            return request.redirect(f'{self._redirect}?error=no_study')

        requestable = Convalidation._ems_portal_requestable_subjects(student, study)
        requested_ids = set()
        for value in request.httprequest.form.getlist('subject_ids'):
            if value.isdigit():
                requested_ids.add(int(value))
        subjects = requestable.filtered(lambda subject: subject.id in requested_ids)
        if not subjects:
            return request.redirect(f'{self._redirect}?error=no_subjects')

        basis = post.get('basis')
        if basis not in dict(Convalidation._fields['basis'].selection):
            return request.redirect(f'{self._redirect}?error=no_basis')

        # Prior studies say where they were passed; nothing else does.
        origin = post.get('prior_studies_origin') if basis == 'prior_studies' else False
        if basis == 'prior_studies' and origin not in dict(Convalidation._fields['prior_studies_origin'].selection):
            return request.redirect(f'{self._redirect}?error=no_origin')

        # Supporting documents are mandatory unless the studies were passed here (issue #579): the
        # centre looks its own records up, and can always ask for more afterwards.
        files = [upload for upload in request.httprequest.files.getlist('documents') if upload.filename]
        if not files and Convalidation._ems_documents_required(basis, origin):
            return request.redirect(f'{self._redirect}?error=no_documents')

        requester = request.env.user.partner_id
        convalidation = Convalidation.create({
            'student_id': student.id,
            'requester_id': requester.id,
            'study_id': study.id,
            'basis': basis,
            'prior_studies_origin': origin,
            'student_notes': (post.get('student_notes') or '').strip()[:2000] or False,
            'line_ids': [(0, 0, {'subject_id': subject.id}) for subject in subjects],
        })
        attachments = self._ems_store_uploads(convalidation, files)
        convalidation.attachment_ids = [(6, 0, attachments.ids)]
        return request.redirect(f'{self._redirect}?submitted=1')

    def _ems_store_uploads(self, convalidation, files):
        """Uploaded files as attachments of the request itself, so they follow its access
        rights and show up in its Supporting documents."""
        return request.env['ir.attachment'].sudo().create([{
            'name': upload.filename,
            'datas': base64.b64encode(upload.read()),
            'res_model': convalidation._name,
            'res_id': convalidation.id,
        } for upload in files])

    @http.route('/my/convalidaciones/reply/<int:convalidation_id>', type='http', auth='user',
                methods=['POST'], website=True)
    def portal_convalidation_reply(self, convalidation_id, **post):
        """Answer a request for information: the files join the request's own documents and the
        text is posted where the Head of Studies reads it. Only while the request is still open."""
        student = self._ems_convalidation_student()
        convalidation = request.env['ems.convalidation'].sudo().browse(convalidation_id)
        if not (student and convalidation.exists() and convalidation.student_id == student
                and convalidation.state in REVIEW_STATES):
            return request.redirect(self._redirect)
        files = [upload for upload in request.httprequest.files.getlist('documents') if upload.filename]
        message = (post.get('message') or '').strip()[:2000]
        if not files and not message:
            return request.redirect(f'{self._redirect}?error=no_reply')
        convalidation._ems_portal_add_documents(self._ems_store_uploads(convalidation, files), message)
        return request.redirect(f'{self._redirect}?replied=1')

    @http.route('/my/convalidaciones/cancel/<int:convalidation_id>', type='http', auth='user',
                methods=['POST'], website=True)
    def portal_convalidation_cancel(self, convalidation_id, **post):
        student = self._ems_convalidation_student()
        convalidation = request.env['ems.convalidation'].sudo().browse(convalidation_id)
        if student and convalidation.exists() and convalidation.student_id == student \
                and convalidation._ems_is_cancellable():
            convalidation.action_cancel()
        return request.redirect(self._redirect)

    @http.route('/my/convalidaciones/resolution/<int:convalidation_id>', type='http', auth='user', website=True)
    def portal_convalidation_resolution(self, convalidation_id, **kwargs):
        """The official resolution of a closed request, for whoever sees the student's page."""
        partner = request.env.user.partner_id
        convalidation = request.env['ems.convalidation'].sudo().browse(convalidation_id)
        if not (partner._ems_convalidation_portal_visible() and convalidation.exists()
                and convalidation.student_id == partner.get_portal_student()
                and convalidation.state in ('completed', 'rejected')):
            return request.redirect(self._redirect)
        document = convalidation.resolution_pdf_id
        if not document:
            return request.redirect(self._redirect)
        return request.make_response(document.raw, headers=[
            ('Content-Type', document.mimetype or 'application/pdf'),
            ('Content-Disposition', http.content_disposition(document.name)),
        ])
