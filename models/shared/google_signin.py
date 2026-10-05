# -*- coding: utf-8 -*-

from odoo import models


class ResUsersGoogleSignin(models.Model):
    _inherit = 'res.users'

    def _ems_link_google_signin(self, google_id):
        """Pre-link "Sign in with Google" on this user (oauth_uid + provider).

        Shared by staff (linked when their corporate account is created, see
        hr.employee._ems_create_user) and students (linked on their first Google sign-in, see
        res.users._auth_oauth_signin in models/contacts/portal_google_signin.py). Skipped when
        the id is unknown, or already taken by another user (auth_oauth unique constraint).
        Returns True when the user ends up linked to Google sign-in.
        """
        self.ensure_one()
        user = self.sudo()
        if user.oauth_uid:
            return True
        provider = self.env.ref('auth_oauth.provider_google', raise_if_not_found=False)
        if not google_id or not provider:
            return False
        taken = user.with_context(active_test=False).search_count([
            ('oauth_provider_id', '=', provider.id),
            ('oauth_uid', '=', str(google_id)),
        ])
        if taken:
            return False
        user.write({'oauth_provider_id': provider.id, 'oauth_uid': str(google_id)})
        return True
