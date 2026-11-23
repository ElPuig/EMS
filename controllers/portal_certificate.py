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
        """The uploaded files by document: `document_<id>` inputs for the required documents of the
        type (ems.certificate.type.document), `documents` (key None) for the optional ones."""
        files = {}
        for key in request.httprequest.files:
            uploads = [upload for upload in request.httprequest.files.getlist(key) if upload.filename]
            if not uploads:
                continue
            if key == 'documents':
                files[None] = uploads
            elif key.startswith('document_') and key[9:].isdigit():
                files[int(key[9:])] = uploads
        return files

    def _ems_certificate_portal_documents(self, certificate_type):
        """The required documents of the type the applicant may attach."""
        return certificate_type._ems_required_documents().filtered(lambda document: document._ems_applicant_may_upload())

    def _ems_certificate_studies(self, certificate_type, current_study):
        """The studies to choose from: those of the type's levels (any, for a type without levels),
        the student's own first when it is one of them."""
        Study = request.env['ems.study'].sudo()
        levels = certificate_type.level_ids
        studies = Study.search([('level_id', 'in', levels.ids)]) if levels else Study.search([])
        if current_study and (not levels or current_study.level_id in levels):
            return current_study | studies
        return studies

    def _ems_certificate_courses(self):
        """The courses EMS has, offered for a school year detail; the applicant may still write
        another one (an older year EMS never had)."""
        return request.env['ems.course'].sudo().search([], order='start desc').mapped('name')

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
        # One form per type, each with its own details, studies and documents. The one a submission
        # came back from with an error opens again.
        error_type = kwargs.get('type_id')
        forms = [{
            'type': certificate_type,
            'studies': self._ems_certificate_studies(certificate_type, current_study),
            'type_fields': certificate_type._ems_applicant_fields(),
            'portal_documents': self._ems_certificate_portal_documents(certificate_type),
            'open': (kwargs.get('error') == 'missing' and error_type == str(certificate_type.id))
                    or (bool(kwargs.get('new')) and len(types) == 1),
        } for certificate_type in types]
        return request.render('ems.portal_certificates', self._ems_certificate_values(
            student=viewed,
            can_request=bool(student),
            viewing_as_family=viewed != partner,
            forms=forms,
            defaults=defaults,
            courses=self._ems_certificate_courses(),
            certificates=Certificate.search([('student_id', '=', viewed.id)]),
            error=kwargs.get('error'),
            submitted=kwargs.get('submitted'),
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
        values, details, missing = Certificate._ems_parse_portal_form(post, certificate_type)
        if missing:
            return request.redirect(f'{self._certificate_redirect}?error=missing&type_id={certificate_type.id}')
        certificate = Certificate.create({
            'type_id': certificate_type.id,
            'student_id': student.id,
            'requester_id': request.env.user.partner_id.id,
            'origin': 'portal',
            # The applicant may complete or correct it until the centre starts working on it.
            'applicant_form_open': True,
            **values,
        })
        certificate._ems_set_values(details)
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
            courses=self._ems_certificate_courses(),
            type_fields=certificate.type_id._ems_applicant_fields(),
            portal_documents=certificate._ems_portal_documents().type_document_id,
            defaults=self._ems_certificate_defaults(certificate),
            error=kwargs.get('error'),
            submitted=kwargs.get('submitted'),
            updated=kwargs.get('updated'),
            replied=kwargs.get('replied'),
        ))

    def _ems_certificate_defaults(self, certificate):
        """The form's current values: the common details, and each detail of the type under its
        input's name (field_<id>, and field_<id>_vat for a company)."""
        defaults = {name: certificate[name] for name in ('student_name', 'student_document')}
        defaults['study_id'] = certificate.study_id.id
        for line in certificate.value_ids:
            name = f'field_{line.field_id.id}'
            if line.field_type == 'company':
                defaults[name] = line.value_char or line.value_company_id.name
                defaults[f'{name}_vat'] = line.value_vat or line.value_company_id.vat
            else:
                defaults[name] = line[line._ems_column()]
        return defaults

    @http.route('/my/certificats/<int:certificate_id>/submit', type='http', auth='public', methods=['POST'],
                website=True)
    def portal_certificate_fill(self, certificate_id, access_token=None, **post):
        certificate = self._ems_certificate_access(certificate_id, access_token)
        if certificate is None:
            return request.redirect('/my')
        if not certificate._ems_portal_can_edit():
            return request.redirect(self._ems_certificate_url(certificate))
        values, details, missing = certificate._ems_parse_portal_form(post)
        if missing:
            return request.redirect(self._ems_certificate_url(certificate, 'error=missing'))
        was_draft = certificate.state == 'draft'
        certificate._ems_portal_fill(values, details, self._ems_certificate_files())
        return request.redirect(self._ems_certificate_url(certificate, 'submitted=1' if was_draft else 'updated=1'))

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
