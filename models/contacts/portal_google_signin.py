# -*- coding: utf-8 -*-

import logging

from odoo import api, models
from odoo.exceptions import AccessDenied
from odoo.tools import email_normalize

_logger = logging.getLogger(__name__)


class ResUsersPortalGoogleSignin(models.Model):
    """Students sign into the portal with their corporate Google account as well as with
    their personal email and password. The portal user keeps its personal-email login (it
    exists before the corporate account does); "Sign in with Google" is linked to it lazily,
    on the first Google sign-in whose verified email is the student's student_email. auth_oauth
    keeps password login working on a linked user, so both ways in coexist on one account. See
    docs/en/developers/contacts/google_workspace_student.md."""
    _inherit = 'res.users'

    @api.model
    def _auth_oauth_signin(self, provider, validation, params):
        login = super(ResUsersPortalGoogleSignin, self.with_context(no_user_creation=True)) \
            ._auth_oauth_signin(provider, validation, params)
        if login:
            return login
        user = self._ems_student_for_google_signin(provider, validation)
        if not user or not user._ems_link_google_signin(validation['user_id']):
            raise AccessDenied()
        user.write({'oauth_access_token': params['access_token']})
        _logger.info("Google sign-in linked to portal user %s (student %s)",
                     user.id, user.partner_id.id)
        return user.login

    @api.model
    def _ems_student_for_google_signin(self, provider, validation):
        """The portal user of the student whose corporate email Google just vouched for, or an
        empty recordset. The email is only trusted when Google says it is verified and it
        belongs to the centre's own Workspace domain; internal users are never matched here
        (staff are linked when their account is created, hr.employee._ems_create_user)."""
        users = self.browse()
        google = self.env.ref('auth_oauth.provider_google', raise_if_not_found=False)
        domain = self.env.company.sudo().google_ws_domain
        email = email_normalize(validation.get('email'))
        if not (google and provider == google.id and domain and email
                and validation.get('email_verified') is True
                and email.endswith(f'@{domain.lower()}')):
            return users
        users = self.sudo().search([
            ('share', '=', True),
            ('partner_id.student_email', '=ilike', email),
        ]).filtered(lambda user: email_normalize(user.partner_id.student_email) == email)
        return users if len(users) == 1 else self.browse()


class ResPartnerPortalGoogleSignin(models.Model):
    _inherit = 'res.partner'

    def write(self, vals):
        """A changed corporate email unlinks Google sign-in from the student's portal user: the
        link points at the old Google account, which must not keep opening this portal."""
        changed = self.browse()
        if 'student_email' in vals:
            new_email = email_normalize(vals['student_email'])
            changed = self.filtered(lambda p: email_normalize(p.student_email) != new_email)
        result = super().write(vals)
        google = self.env.ref('auth_oauth.provider_google', raise_if_not_found=False)
        if changed and google:
            changed.sudo().with_context(active_test=False).user_ids.filtered(
                lambda user: user.share and user.oauth_provider_id == google
            ).write({'oauth_uid': False, 'oauth_provider_id': False, 'oauth_access_token': False})
        return result
