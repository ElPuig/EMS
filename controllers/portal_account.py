# -*- coding: utf-8 -*-

from odoo.http import request, route
from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.tools.image import image_data_uri


class EMSPortalAccount(CustomerPortal):
    """Make the portal profile (/my/account) read-only for portal users.

    Portal users (students and families) must not be able to change their own
    personal data (a student could rename themselves to a nickname, etc.).
    The standard controller writes the partner with sudo() over a whitelist of
    fields, so the protection MUST live in the backend: simply hiding the inputs
    in the template would still let a crafted POST go through. Here we never
    process the write for portal users and render a read-only variant instead.

    The contact details are corrected through the review page of issue #507
    (controllers/portal_contact_data.py), which the read-only template links to. The page
    shows everything that review lets the account send, plus the school data only the
    secretary's office corrects (issue #736, see docs/en/developers/contacts/portal_profile.md).
    """

    def _prepare_portal_layout_values(self):
        # Ensure the flag always exists in the render context so the inherited
        # portal_my_details template can reference it for internal users too
        # (whose account() goes through super() and never sets it explicitly).
        values = super()._prepare_portal_layout_values()
        values.setdefault('ems_profile_readonly', False)
        return values

    def _ems_profile_is_locked(self):
        """True when the current user must not edit their own profile.

        Targets every portal user (students and families); internal users
        (teachers, secretariat, admin) keep the standard editable form.
        """
        return request.env.user.has_group('base.group_portal')

    @route(['/my/account'], type='http', auth='user', website=True)
    def account(self, redirect=None, **post):
        if not self._ems_profile_is_locked():
            return super().account(redirect=redirect, **post)

        # Portal user: never process the write, always render read-only.
        partner = request.env.user.partner_id
        values = self._prepare_portal_layout_values()
        values.update({
            'error': {},
            'error_message': [],
            'partner': partner,
            'countries': request.env['res.country'].sudo().search([]),
            'states': request.env['res.country.state'].sudo().search([]),
            'has_check_vat': hasattr(request.env['res.partner'], 'check_vat'),
            'partner_can_edit_vat': partner.can_edit_vat(),
            'redirect': redirect,
            'page_name': 'my_details',
            'ems_profile_readonly': True,
        })
        values.update(self._ems_profile_values(partner))

        response = request.render("portal.portal_my_details", values)
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['Content-Security-Policy'] = "frame-ancestors 'self'"
        return response

    def _ems_profile_values(self, partner):
        """What the read-only profile shows besides the account's own contact details: the
        student it looks at (the account itself for a student, the selected child for a family),
        with his school data and photo; his family contacts, on the student's own account; and,
        for whoever may send the student's contact details for review, that review's status this
        academic year. sudo: a portal user has no rights on the relations, the groups nor the
        tutor's employee record."""
        student = partner.get_portal_student().sudo()
        if student.contact_type not in ('student', 'applicant'):
            student = student.browse()
        contact_student = partner._ems_portal_contact_data_student()
        return {
            'ems_profile_partner': partner.sudo(),
            'ems_profile_address': ', '.join(filter(None, [
                partner.street, ' '.join(filter(None, [partner.zip, partner.city]))])),
            'ems_profile_student': student,
            'ems_profile_own': student == partner,
            'ems_profile_photo': student.image_256 and image_data_uri(student.image_256),
            'ems_profile_tutor': student.main_group_id.tutor_id,
            'ems_profile_family': student._ems_contact_data()['family'] if student == partner else [],
            'ems_profile_can_review': bool(contact_student),
            'ems_profile_request': contact_student and contact_student._ems_contact_data_running_request(),
        }
