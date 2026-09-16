# -*- coding: utf-8 -*-

import base64

from markupsafe import Markup, escape

from odoo import _, http
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal


class EmsPortalConvalidationController(CustomerPortal):
    """Issue #276 - students (and the families of minors) request subject convalidations from
    the portal. Always about the student resolved by get_portal_student(): no student id travels
    in a form, so nobody can file or cancel a request for someone else. sudo because portal users
    have no ACL on ems.convalidation - see docs/en/developers/grades/convalidation.md."""

    _redirect = '/my/convalidaciones'

    def _ems_convalidation_student(self):
        student = request.env.user.partner_id.get_portal_student()
        return student if student.contact_type in ('student', 'applicant') else student.browse()

    @http.route('/my/convalidaciones', type='http', auth='user', website=True)
    def portal_convalidations(self, **kwargs):
        partner = request.env.user.partner_id
        student = self._ems_convalidation_student()
        Convalidation = request.env['ems.convalidation'].sudo()
        study = Convalidation._ems_portal_study(student) if student else request.env['ems.study']
        convalidations = Convalidation.search([('student_id', '=', student.id)]) \
            if student else Convalidation
        # fields_get(): selection labels in the visitor's language.
        selections = Convalidation.fields_get(['state', 'basis'], ['selection'])
        line_states = request.env['ems.convalidation.line'].sudo().fields_get(['state'], ['selection'])
        values = self._prepare_portal_layout_values()
        values.update({
            'page_name': 'convalidations',
            'student': student,
            'students': partner.get_portal_students(),
            'viewing_as_family': student != partner,
            'study': study,
            'requestable_subjects': Convalidation._ems_portal_requestable_subjects(student, study)
            if study else request.env['ems.subject'],
            'convalidations': convalidations,
            'basis_options': selections['basis']['selection'],
            'state_labels': dict(selections['state']['selection']),
            'line_state_labels': dict(line_states['state']['selection']),
            'error': kwargs.get('error'),
            'submitted': kwargs.get('submitted'),
        })
        return request.render('ems.portal_convalidations', values)

    @http.route('/my/convalidaciones/submit', type='http', auth='user', methods=['POST'], website=True)
    def portal_convalidation_submit(self, **post):
        student = self._ems_convalidation_student()
        Convalidation = request.env['ems.convalidation'].sudo()
        study = Convalidation._ems_portal_study(student) if student else request.env['ems.study']
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

        files = [upload for upload in request.httprequest.files.getlist('documents') if upload.filename]
        if not files:
            return request.redirect(f'{self._redirect}?error=no_documents')

        requester = request.env.user.partner_id
        convalidation = Convalidation.create({
            'student_id': student.id,
            'requester_id': requester.id,
            'study_id': study.id,
            'basis': basis,
            'student_notes': (post.get('student_notes') or '').strip()[:2000] or False,
            'line_ids': [(0, 0, {'subject_id': subject.id}) for subject in subjects],
        })
        attachments = request.env['ir.attachment'].sudo().create([{
            'name': upload.filename,
            'datas': base64.b64encode(upload.read()),
            'res_model': convalidation._name,
            'res_id': convalidation.id,
        } for upload in files])
        convalidation.attachment_ids = [(6, 0, attachments.ids)]
        convalidation.message_post(
            body=Markup(_("Request submitted from the portal by %s.")) % escape(requester.name),
            message_type='comment', subtype_xmlid='mail.mt_note')
        return request.redirect(f'{self._redirect}?submitted=1')

    @http.route('/my/convalidaciones/cancel/<int:convalidation_id>', type='http', auth='user',
                methods=['POST'], website=True)
    def portal_convalidation_cancel(self, convalidation_id, **post):
        student = self._ems_convalidation_student()
        convalidation = request.env['ems.convalidation'].sudo().browse(convalidation_id)
        if student and convalidation.exists() and convalidation.student_id == student \
                and convalidation.state == 'submitted':
            convalidation.action_cancel()
            convalidation.message_post(
                body=Markup(_("Request cancelled from the portal by %s."))
                % escape(request.env.user.partner_id.name),
                message_type='comment', subtype_xmlid='mail.mt_note')
        return request.redirect(self._redirect)
