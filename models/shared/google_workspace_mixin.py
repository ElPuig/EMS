# -*- coding: utf-8 -*-
import json
import logging
import secrets
import string
import unicodedata

from odoo import api, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Google client libraries are optional at import time so the module always loads.
# They are required only when actually creating accounts (non dry-run).
try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    GOOGLE_LIBS_AVAILABLE = True
except ImportError:
    service_account = None
    build = None
    HttpError = Exception
    GOOGLE_LIBS_AVAILABLE = False

try:
    import phonenumbers
except ImportError:
    phonenumbers = None

GW_SCOPES = ['https://www.googleapis.com/auth/admin.directory.user']


class GoogleWorkspaceMixin(models.AbstractModel):
    """Model-agnostic helpers shared by the Google Workspace integrations.

    Both the student integration (``res.partner``) and the staff integration
    (``hr.employee``) inherit this mixin so the Directory API client, password
    policy and text/phone normalisation live in a single place.
    """
    _name = 'google.workspace.mixin'
    _description = 'Google Workspace integration helpers'

    @api.model
    def _gw_normalize(self, text):
        """Lowercase, strip accents (ñ→n, ç→c, ü→u...) and keep only alphanumerics."""
        if not text:
            return ''
        text = text.strip().lower()
        nfkd = unicodedata.normalize('NFKD', text)
        text = ''.join(c for c in nfkd if not unicodedata.combining(c))
        return ''.join(c for c in text if c.isalnum())

    @api.model
    def _gw_random_password(self, length=12):
        alphabet = string.ascii_letters + string.digits
        while True:
            pwd = ''.join(secrets.choice(alphabet) for _ in range(length))
            if (any(c.islower() for c in pwd) and any(c.isupper() for c in pwd)
                    and any(c.isdigit() for c in pwd)):
                return pwd

    def _gw_get_service(self):
        """Build the Directory API client from the service account JSON.

        Uses a custom admin role scoped to the managed OUs (no domain-wide
        delegation, so NO .with_subject() impersonation).
        """
        if not GOOGLE_LIBS_AVAILABLE:
            raise UserError(_(
                "Google API libraries are not installed on the server "
                "(google-api-python-client, google-auth)."))
        raw = self.env.company.sudo().google_ws_sa_json
        if not raw:
            raise UserError(_("The Google Workspace Service Account JSON is not configured."))
        try:
            info = json.loads(raw)
        except Exception:
            raise UserError(_("The Google Workspace Service Account JSON is not valid."))
        creds = service_account.Credentials.from_service_account_info(info, scopes=GW_SCOPES)
        return build('admin', 'directory_v1', credentials=creds, cache_discovery=False)

    @api.model
    def _gw_domain(self):
        """The centre's configured Google Workspace domain (res.company.google_ws_domain),
        raising if it hasn't been set - every account/email flow needs a real domain, so
        there's no sensible literal to silently fall back to (data/main ships EMS-generic
        content, not any one centre's own domain)."""
        domain = self.env.company.google_ws_domain
        if not domain:
            raise UserError(_("Google Workspace domain is not configured (Settings > Company)."))
        return domain

    @api.model
    def _gw_format_phone(self, raw):
        """Return the given phone number in E.164 (+34...) or False."""
        if not raw:
            return False
        if phonenumbers:
            try:
                num = phonenumbers.parse(raw, 'ES')
                if phonenumbers.is_valid_number(num):
                    return phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.E164)
            except Exception:
                return False
            return False
        return raw
