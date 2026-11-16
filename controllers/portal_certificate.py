# -*- coding: utf-8 -*-

from odoo import http
from odoo.exceptions import AccessError, MissingError
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal


class EmsPortalCertificateController(CustomerPortal):
    """Issue #835 - certificate requests on the portal.

    - /my/certificats: a current student's requests, and a new one, for whoever may file requests
      for him (res.partner._ems_can_file_requests_for, the same rule as convalidations).
    - /my/certificats/<id>?access_token=...: one request, through the link its emails carry
      (portal.mixin). A former student, who has no portal, fills in the form the secretariat sent
      him there, answers requests for documentation and downloads the certificate, without logging
      in. Current students reach their requests the same way from the list.

    sudo because portal and public users have no ACL on ems.certificate: the student comes from
    get_portal_student(), never from the form, and a single request only opens with its token."""

    _certificate_redirect = '/my/certificats'

    def _ems_certificate_student(self):
        """The student the portal user may file requests for, or an empty recordset."""
        partner = request.env.user.partner_id
        student = partner.get_portal_student()
        return student if partner._ems_can_file_requests_for(student) else student.browse()

    def _ems_certificate_files(self):
        return [upload for upload in request.httprequest.files.getlist('documents') if upload.filename]

    def _ems_certificate_studies(self, certificate_type, current_study):
        """The studies to choose from: those of the type's levels, the student's own first."""
        Study = request.env['ems.study'].sudo()
        studies = Study.search([('level_id', 'in', certificate_type.level_ids.ids)]) \
            if certificate_type.level_ids else Study.search([])
        return current_study | studies

    def _ems_certificate_values(self, **extra):
        Certificate = request.env['ems.certificate'].sudo()
        values = self._prepare_portal_layout_values()
        values.update({
            'page_name': 'certificates',
            'state_labels': dict(Certificate.fields_get(['state'], ['selection'])['state']['selection']),
            **extra,
        })
        return values

    @http.route('/my/certificats', type='http', auth='user', website=True)
    def portal_certificates(self, **kwargs):
        partner = request.env.user.partner_id
        if not partner._ems_certificate_portal_visible():
            return request.redirect('/my/home')
        viewed = partner.get_portal_student()
        student = self._ems_certificate_student()
        Certificate = request.env['ems.certificate'].sudo()
        types = Certificate._ems_portal_types(viewed)
        defaults = Certificate._ems_student_defaults(viewed)
        current_study = request.env['ems.study'].sudo().browse(defaults['study_id'])
        return request.render('ems.portal_certificates', self._ems_certificate_values(
            student=viewed,
            can_request=bool(student),
            viewing_as_family=viewed != partner,
            types=types,
            defaults=defaults,
            studies=self._ems_certificate_studies(types[:1], current_study),
            certificates=Certificate.search([('student_id', '=', viewed.id)]),
            error=kwargs.get('error'),
            submitted=kwargs.get('submitted'),
            open_new=bool(kwargs.get('new')),
        ))

    @http.route('/my/certificats/submit', type='http', auth='user', methods=['POST'], website=True)
    def portal_certificate_submit(self, **post):
        student = self._ems_certificate_student()
        if not student:
            return request.redirect(self._certificate_redirect)
        Certificate = request.env['ems.certificate'].sudo()
        types = Certificate._ems_portal_types(student)
        type_id = post.get('type_id')
        certificate_type = types.filtered(lambda t: str(t.id) == type_id) if type_id else types[:1]
        if not certificate_type:
            return request.redirect(self._certificate_redirect)
        values, missing = Certificate._ems_parse_portal_form(post)
        if missing:
            return request.redirect(f'{self._certificate_redirect}?error=missing')
        certificate = Certificate.create({
            'type_id': certificate_type.id,
            'student_id': student.id,
            'requester_id': request.env.user.partner_id.id,
            'origin': 'portal',
            **values,
        })
        certificate._ems_portal_attach(self._ems_certificate_files())
        certificate._ems_submit()
        return request.redirect(f'{self._certificate_redirect}?submitted=1')

    # --- one request, by its token ---------------------------------------------

    def _ems_certificate_access(self, certificate_id, access_token):
        try:
            return self._document_check_access('ems.certificate', certificate_id, access_token=access_token)
        except (AccessError, MissingError):
            return None

    def _ems_certificate_url(self, certificate, query=None):
        return certificate.get_portal_url(query_string=f'&{query}' if query else None)

    @http.route('/my/certificats/<int:certificate_id>', type='http', auth='public', website=True)
    def portal_certificate(self, certificate_id, access_token=None, **kwargs):
        certificate = self._ems_certificate_access(certificate_id, access_token)
        if certificate is None:
            return request.redirect('/my')
        current_study = certificate.study_id or certificate.student_id.sudo().main_group_id.study_id
        return request.render('ems.portal_certificate', self._ems_certificate_values(
            certificate=certificate,
            access_token=certificate.access_token,
            studies=self._ems_certificate_studies(certificate.type_id, current_study),
            defaults={name: certificate[name].id if name == 'study_id' else certificate[name]
                      for name in ('student_name', 'student_document', 'study_id', 'fct_school_year',
                                   'company_name', 'company_vat', 'agreement_reference')},
            error=kwargs.get('error'),
            submitted=kwargs.get('submitted'),
            replied=kwargs.get('replied'),
        ))

    @http.route('/my/certificats/<int:certificate_id>/submit', type='http', auth='public', methods=['POST'],
                website=True)
    def portal_certificate_fill(self, certificate_id, access_token=None, **post):
        certificate = self._ems_certificate_access(certificate_id, access_token)
        if certificate is None or certificate.state != 'draft':
            return request.redirect('/my')
        values, missing = certificate._ems_parse_portal_form(post)
        if missing:
            return request.redirect(self._ems_certificate_url(certificate, 'error=missing'))
        certificate._ems_portal_fill(values, self._ems_certificate_files())
        return request.redirect(self._ems_certificate_url(certificate, 'submitted=1'))

    @http.route('/my/certificats/<int:certificate_id>/reply', type='http', auth='public', methods=['POST'],
                website=True)
    def portal_certificate_reply(self, certificate_id, access_token=None, **post):
        certificate = self._ems_certificate_access(certificate_id, access_token)
        if certificate is None or certificate.state != 'documentation':
            return request.redirect('/my')
        files = self._ems_certificate_files()
        message = (post.get('message') or '').strip()[:2000]
        if not files and not message:
            return request.redirect(self._ems_certificate_url(certificate, 'error=reply'))
        certificate._ems_portal_answer(message, files)
        return request.redirect(self._ems_certificate_url(certificate, 'replied=1'))

    @http.route('/my/certificats/<int:certificate_id>/cancel', type='http', auth='public', methods=['POST'],
                website=True)
    def portal_certificate_cancel(self, certificate_id, access_token=None, **post):
        certificate = self._ems_certificate_access(certificate_id, access_token)
        if certificate is None:
            return request.redirect('/my')
        if certificate._ems_is_cancellable():
            certificate._ems_cancel()
        return request.redirect(self._ems_certificate_url(certificate))

    @http.route('/my/certificats/<int:certificate_id>/pdf', type='http', auth='public', website=True)
    def portal_certificate_pdf(self, certificate_id, access_token=None, **kwargs):
        certificate = self._ems_certificate_access(certificate_id, access_token)
        document = certificate.certificate_pdf_id if certificate is not None and certificate.state == 'issued' else None
        if not document:
            return request.redirect('/my')
        return request.make_response(document.raw, headers=[
            ('Content-Type', 'application/pdf'),
            ('Content-Disposition', http.content_disposition(document.name)),
        ])
