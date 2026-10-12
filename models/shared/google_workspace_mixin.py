# -*- coding: utf-8 -*-
import json
import logging
import secrets
import string
import unicodedata

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import SQL

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

# Grace periods, in days, between archiving someone and the Google account actually
# changing (issue #388). Archiving warns and schedules; a daily cron does the work once
# the date arrives. Deliberately fixed constants rather than company settings: the centre
# states a single policy, and a per-centre knob would only add a way to get it wrong.
GW_DEACTIVATION_DELAY_DAYS = 30  # archive -> suspension (staff and students)
GW_DELETION_DELAY_DAYS = 30      # suspension -> deletion (students only)


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
    def _gw_schedule_date(self, days):
        """The date, `days` days from today, a scheduled lifecycle step falls due on."""
        return fields.Date.context_today(self) + relativedelta(days=days)

    @api.model
    def _gw_creation_job_running(self, identity_key):
        """True while the account-creation job with this key waits in the queue or runs.

        queue_job's identity_key only deduplicates jobs that are still waiting, not one
        already started, so the "Create Google account" button reads this to stay hidden
        until the job is over (issue #582).
        """
        return bool(self.env['queue.job'].sudo().search_count([
            ('identity_key', '=', identity_key),
            ('state', 'in', ('wait_dependencies', 'pending', 'enqueued', 'started')),
        ], limit=1))

    @api.model
    def _gw_creation_queued_notification(self):
        """What the "Create Google account" button answers once the creation is queued."""
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'info',
                'message': _("The Google account is being created. The result will appear "
                             "in the record's history in a few moments."),
                'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
            },
        }

    @api.model
    def _gw_lock_for_creation(self, record):
        """Lock `record`'s row before any Google call that creates its account (issue #582).

        Two creations for the same person (the header button and the automatic job) used
        to run side by side: both saw no corporate email, the loser got a 409 from Google,
        created the next candidate address and then rolled back on the database, leaving
        an orphan account in Google. With the row locked first, the second one fails here,
        before touching Google, with an error queue_job and Odoo's HTTP layer both retry,
        and the retry finds the address the first one saved. NOWAIT so a retry never sits
        blocked; under REPEATABLE READ a row changed since the snapshot also fails here.
        """
        self.env.cr.execute(SQL(
            "SELECT 1 FROM %s WHERE id = %s FOR UPDATE NOWAIT",
            SQL.identifier(record._table), record.id))
        record.invalidate_recordset()

    @api.model
    def _gw_send_lifecycle_warning(self, record, template_xmlid, recipients,
                                   extra_context=None):
        """Warn `record`'s known addresses that its Google account is about to change.

        Sent to every address given (personal *and* corporate): the corporate mailbox is
        still alive during the grace period and is the one actually read day to day.
        Returns whether an email was actually sent - a record with no address at all only
        gets the chatter note its caller posts.
        """
        addresses = [address for address in recipients if address]
        if not addresses:
            return False
        template = self.env.ref(template_xmlid, raise_if_not_found=False)
        if not template:
            _logger.warning("Google Workspace: mail template %s not found", template_xmlid)
            return False
        template.sudo().with_context(
            gw_recipients=','.join(addresses), **(extra_context or {}),
        ).send_mail(record.id, force_send=True)
        return True

    @api.model
    def _gw_reset_password(self, email):
        """Give the Google account `email` a new random password, to be changed at next login,
        and return it. Shared by students (#478) and staff (#595). A refusal from Google is
        raised as a UserError before the caller delivers anything, so the previous credentials
        stay in place."""
        password = self._gw_random_password()
        if self.env.company.google_ws_dry_run:
            _logger.info("[GW dry-run] reset password of %s", email)
            return password
        service = self._gw_get_service()
        try:
            service.users().patch(
                userKey=email,
                body={'password': password, 'changePasswordAtNextLogin': True},
            ).execute()
        except HttpError as e:
            _logger.exception("Could not reset the Google password of %s", email)
            raise UserError(_(
                "Google refused to reset the password of %(email)s. Check that the service "
                "account's admin role has the \"Reset password\" privilege. Error: %(err)s") % {
                    'email': email, 'err': str(e)[:200]}) from e
        return password

    @api.model
    def _gw_sync_account_name(self, record, email, given, family):
        """Copy a name onto the Google account `email` belongs to (issue #542).

        Shared by staff (``hr.employee``) and students (``res.partner``); `record` gets
        the chatter note. Idempotent: patching the same name again is a no-op on
        Google's side. A 403/404 (account deleted, or outside the managed OUs - the
        OU-scoped role answers 403 for both) is reported instead of raised, since a
        retry could never succeed; any other error is raised so the job shows as failed.
        """
        body = {'name': {'givenName': given or '', 'familyName': family or ''}}
        if self._gw_patch_account(record, email, body, _(
                "Google Workspace: the account %s could not be renamed because it "
                "no longer exists or is outside the managed organizational units.") % email):
            record.sudo().message_post(body=_(
                "Google Workspace account %(email)s renamed to %(name)s.") % {
                    'email': email, 'name': record.name})

    @api.model
    def _gw_patch_account(self, record, email, body, unreachable_note):
        """Patch the Google account `email` with `body`; True once Google has it.

        Dry-run only logs it. A 403/404 (account deleted, or outside the managed OUs - the
        OU-scoped role answers 403 for both) posts `unreachable_note` on `record` instead of
        raising, since a retry could never succeed; any other error is raised so the job
        shows as failed.
        """
        if self.env.company.google_ws_dry_run:
            _logger.info("[GW dry-run] patch %s -> %s", email, body)
            return False
        service = self._gw_get_service()
        try:
            service.users().patch(userKey=email, body=body).execute()
        except HttpError as e:
            status = getattr(getattr(e, 'resp', None), 'status', None)
            if status in (404, 403):
                record.sudo().message_post(body=unreachable_note)
                return False
            _logger.exception("Could not patch Google account %s", email)
            raise
        return True

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
