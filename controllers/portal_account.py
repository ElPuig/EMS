# -*- coding: utf-8 -*-

from odoo.http import request, route
from odoo.addons.portal.controllers.portal import CustomerPortal


class EMSPortalAccount(CustomerPortal):
    """Make the portal profile (/my/account) read-only for portal users.

    Portal users (students and families) must not be able to change their own
    personal data (a student could rename themselves to a nickname, etc.).
    The standard controller writes the partner with sudo() over a whitelist of
    fields, so the protection MUST live in the backend: simply hiding the inputs
    in the template would still let a crafted POST go through. Here we never
    process the write for portal users and render a read-only variant instead.

    The contact details are corrected through the review page of issue #507
    (controllers/portal_contact_data.py), which the read-only template links to.
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

        response = request.render("portal.portal_my_details", values)
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['Content-Security-Policy'] = "frame-ancestors 'self'"
        return response
