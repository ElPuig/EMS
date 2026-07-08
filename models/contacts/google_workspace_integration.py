# -*- coding: utf-8 -*-
import base64
import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError

from ..shared.google_workspace_mixin import HttpError

_logger = logging.getLogger(__name__)


class ResPartnerGoogleWorkspace(models.Model):
    # NOTE: 'google.workspace.mixin' is NOT added to _inherit. Mixing an extra
    # abstract model into res.partner's inheritance re-triggers the shared-table
    # check on inherited Many2many fields (channel_ids) and Odoo refuses to load.
    # We reach the shared helpers through self.env['google.workspace.mixin'].
    _inherit = 'res.partner'

    google_ws_suspended = fields.Boolean(
        string="Google account suspended", default=False, copy=False,
        help="True when the student's Google Workspace account is suspended (former student).")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _gw(self):
        """Shared Google Workspace helpers (normalize / service / password / phone)."""
        return self.env['google.workspace.mixin']

    def _gw_email_candidates(self):
        """Ordered list of email prefixes (without domain) following the fixed strategy.

        Example (Juan Morote Puente, born 2006, IDALU 123456789):
            1. jmorote         inicial(nombre) + apellido1
            2. jmorotep        + inicial(apellido2)
            3. jmorotep06      base + 2 últimas cifras del año de nacimiento
            4. jmorotep89      base + 2 últimas cifras del IDALU
            5. jmorotep6789    base + 4 últimas cifras del IDALU
        """
        self.ensure_one()
        gw = self._gw()
        first = gw._gw_normalize(self.firstname or '')
        last_parts = (self.lastname or '').strip().split()
        apellido1 = gw._gw_normalize(last_parts[0]) if last_parts else ''
        apellido2 = gw._gw_normalize(last_parts[1]) if len(last_parts) > 1 else ''
        ini_nombre = first[0] if first else ''
        ini_ape2 = apellido2[0] if apellido2 else ''

        base1 = '%s%s' % (ini_nombre, apellido1)          # jmorote
        base2 = '%s%s' % (base1, ini_ape2)                # jmorotep (si hay 2º apellido)
        # Base sobre la que se aplican los diferenciadores numéricos
        num_base = base2 if ini_ape2 else base1

        candidates = []
        if base1:
            candidates.append(base1)
        if base2 and base2 != base1:
            candidates.append(base2)
        if num_base and self.birth_date:
            candidates.append('%s%02d' % (num_base, self.birth_date.year % 100))
        idalu = ''.join(c for c in (self.student_id or '') if c.isdigit())
        if num_base and idalu:
            candidates.append('%s%s' % (num_base, idalu[-2:]))
            candidates.append('%s%s' % (num_base, idalu[-4:]))

        # Dedup preserving order
        seen, result = set(), []
        for c in candidates:
            if c and c not in seen:
                seen.add(c)
                result.append(c)
        return result

    def _gw_email_used_in_ems(self, email):
        """True if the email is already assigned to another student in EMS."""
        return bool(self.sudo().search_count([
            ('student_email', '=', email), ('id', '!=', self.id),
        ]))

    def _gw_email_full_candidates(self):
        """Full corporate email candidates (with domain) not yet used in EMS.

        We do NOT pre-check existence against Google with users().get(): with a
        custom admin role scoped to the students OU, get() on a non-existent user
        returns 403 (not 404). Existence in Google is handled on insert() via the
        409 conflict, trying the next candidate.
        """
        domain = self.env.company.google_ws_domain or 'elpuig.xeill.net'
        candidates = ['%s@%s' % (p, domain) for p in self._gw_email_candidates()]
        return [e for e in candidates if not self._gw_email_used_in_ems(e)]

    def _gw_format_mobile(self):
        """Return the student's mobile in E.164 (+34...) or False."""
        return self._gw()._gw_format_phone(self.mobile or self.phone)

    # ------------------------------------------------------------------
    # Readiness checks
    # ------------------------------------------------------------------
    def _gw_missing_fields(self):
        """Return the labels of the required fields that are still empty."""
        self.ensure_one()
        required = [
            ('firstname',  _("First name")),
            ('lastname',   _("Last name")),
            ('student_id', _("IDALU")),
            ('birth_date', _("Birth date")),
            ('email',      _("Personal email")),
        ]
        return [label for fname, label in required if not self[fname]]

    def _gw_ready(self):
        """True if the student has all the data required to create the account."""
        self.ensure_one()
        return (
            self.contact_type == 'student'
            and not self.student_email
            and not self._gw_missing_fields()
        )

    def _gw_enqueue_if_ready(self):
        """Enqueue the async account creation for students that are ready.

        Deduplicated via identity_key so repeated writes (autosave) do not
        enqueue several jobs for the same student.
        """
        if not self.env.company.google_ws_enabled:
            return
        for rec in self:
            if rec._gw_ready():
                rec.with_delay(
                    identity_key='gw_create_account_%s' % rec.id,
                    description="Create Google Workspace account: %s" % rec.name,
                ).action_create_google_account()

    def _gw_enqueue_suspend(self):
        """Enqueue account suspension for students with a corporate email (deduplicated)."""
        if not self.env.company.google_ws_enabled:
            return
        for rec in self.filtered(
            lambda r: r.contact_type == 'student' and r.student_email and not r.google_ws_suspended
        ):
            rec.with_delay(
                identity_key='gw_suspend_%s' % rec.id,
                description="Suspend Google Workspace account: %s" % rec.name,
            ).action_suspend_google_account()

    def _gw_enqueue_reactivate(self):
        """Enqueue account reactivation for students with a corporate email (deduplicated)."""
        if not self.env.company.google_ws_enabled:
            return
        for rec in self.filtered(
            lambda r: r.contact_type == 'student' and r.student_email
        ):
            rec.with_delay(
                identity_key='gw_reactivate_%s' % rec.id,
                description="Reactivate Google Workspace account: %s" % rec.name,
            ).action_reactivate_google_account()

    # ------------------------------------------------------------------
    # Main action (queue_job target / manual button)
    # ------------------------------------------------------------------
    def action_create_google_account(self):
        """Create the student's Google Workspace account and deliver credentials.

        Idempotent: does nothing if the student already has a corporate email.
        """
        self.ensure_one()
        company = self.env.company
        if not company.google_ws_enabled:
            return
        if self.contact_type != 'student':
            return
        if self.student_email:
            return

        # Required data must be complete (Google rejects empty givenName/familyName,
        # and we need IDALU, birth date and personal email).
        missing = self._gw_missing_fields()
        if missing:
            raise UserError(_(
                "Cannot create the Google Workspace account for %(name)s.\n"
                "The following required data is missing: %(fields)s."
            ) % {'name': self.name, 'fields': ", ".join(missing)})

        gw = self._gw()
        dry_run = company.google_ws_dry_run
        service = None if dry_run else gw._gw_get_service()

        candidates = self._gw_email_full_candidates()
        if not candidates:
            self.message_post(body=_("Google Workspace: could not generate a free email address."))
            return

        password = gw._gw_random_password()
        ou = company.google_ws_ou_adult if self.is_adult else company.google_ws_ou_minor

        base_body = {
            'name': {'givenName': self.firstname or '', 'familyName': self.lastname or ''},
            'password': password,
            'changePasswordAtNextLogin': True,
            'orgUnitPath': ou,
        }
        if self.student_id:
            # IDALU stored in the GWS custom schema "IDALU", field "IDALU".
            base_body['customSchemas'] = {'IDALU': {'IDALU': self.student_id}}
        recovery_email = self.email or False
        if recovery_email:
            base_body['recoveryEmail'] = recovery_email
        recovery_phone = self._gw_format_mobile()
        if recovery_phone:
            base_body['recoveryPhone'] = recovery_phone

        # Pick the first candidate that Google accepts. Existence is resolved on
        # insert() via the 409 conflict (we cannot rely on users().get() because a
        # role scoped to the OU returns 403 for non-existent users).
        email = None
        if dry_run:
            email = candidates[0]
            _logger.info("[GW dry-run] users().insert payload: %s",
                         dict(base_body, primaryEmail=email, password='***'))
        else:
            for cand in candidates:
                body = dict(base_body, primaryEmail=cand)
                try:
                    service.users().insert(body=body).execute()
                    email = cand
                    break
                except HttpError as e:
                    status = getattr(getattr(e, 'resp', None), 'status', None)
                    if status == 409:
                        # Email already taken in Google: try the next candidate.
                        continue
                    _logger.exception("Google Workspace account creation failed for %s", self.name)
                    raise
            if not email:
                self.message_post(body=_(
                    "Google Workspace: all candidate emails already exist in Google."))
                return

        # Save the corporate email on the student
        self.sudo().student_email = email

        # Deliver credentials: PDF (always) + email (if personal email exists)
        pdf_saved, emailed = self._gw_deliver_credentials(email, password)

        self.message_post(body=_(
            "Google Workspace account created: %(email)s (OU %(ou)s)%(dry)s. "
            "%(pdf)s%(mail)s."
        ) % {
            'email': email,
            'ou': ou,
            'dry': _(" [dry-run]") if dry_run else '',
            'pdf': _("Credentials PDF saved in the student documentation")
                   if pdf_saved else _("Credentials PDF could NOT be generated (see logs)"),
            'mail': _("; sent by email to %s") % recovery_email if emailed else _("; no personal email on file"),
        })

    def _gw_deliver_credentials(self, email, password):
        """Generate the credentials PDF (always) and send the welcome email (if any).

        Returns (pdf_saved, emailed).
        """
        self.ensure_one()
        pdf_saved = False
        # 1) PDF -> ems.student.document (doc_type google_credentials, approved)
        try:
            pdf, _ct = self.env['ir.actions.report'].sudo()._render_qweb_pdf(
                'ems.report_google_credentials', [self.id],
                data={'gw_email': email, 'gw_password': password},
            )
            self.env['ems.student.document'].sudo().create({
                'partner_id': self.id,
                'doc_type': 'google_credentials',
                'status': 'approved',
                'doc_file': base64.b64encode(pdf),
                'doc_file_name': 'Credencials_Google_%s.pdf' % (self.student_id or self.id),
            })
            pdf_saved = True
        except Exception:
            _logger.exception("Could not generate Google credentials PDF for %s", self.name)

        # 2) Welcome email to the personal address (if any)
        emailed = False
        if self.email:
            template = self.env.ref('ems.mail_template_google_welcome', raise_if_not_found=False)
            if template:
                template.sudo().with_context(
                    gw_email=email, gw_password=password,
                ).send_mail(self.id, force_send=True)
                emailed = True
        return pdf_saved, emailed

    # ------------------------------------------------------------------
    # Deactivation / reactivation (former students)
    # ------------------------------------------------------------------
    def action_suspend_google_account(self):
        """Suspend the student's Google account and move it to the suspended OU.

        Triggered when a student is archived. Idempotent.
        """
        self.ensure_one()
        company = self.env.company
        if not company.google_ws_enabled:
            return
        if self.contact_type != 'student' or not self.student_email:
            return
        if self.google_ws_suspended:
            return

        ou = company.google_ws_ou_suspended or '/alumnos/bajas'
        if company.google_ws_dry_run:
            _logger.info("[GW dry-run] suspend %s -> suspended=True, OU=%s", self.student_email, ou)
        else:
            service = self._gw()._gw_get_service()
            try:
                service.users().patch(
                    userKey=self.student_email,
                    body={'suspended': True, 'orgUnitPath': ou},
                ).execute()
            except HttpError as e:
                status = getattr(getattr(e, 'resp', None), 'status', None)
                if status in (404, 403):
                    # Account no longer exists in Google: nothing to suspend.
                    self.sudo().google_ws_suspended = True
                    self.message_post(body=_(
                        "Google Workspace: account %s no longer exists; marked as suspended.")
                        % self.student_email)
                    return
                _logger.exception("Could not suspend Google account for %s", self.name)
                self.message_post(body=_(
                    "Google Workspace: could not suspend %(email)s. Check that the OU "
                    "%(ou)s exists in Admin. Error: %(err)s") % {
                        'email': self.student_email, 'ou': ou, 'err': str(e)[:200]})
                raise

        self.sudo().google_ws_suspended = True
        self.message_post(body=_(
            "Google Workspace account suspended: %(email)s (moved to OU %(ou)s)%(dry)s.") % {
                'email': self.student_email, 'ou': ou,
                'dry': _(" [dry-run]") if company.google_ws_dry_run else ''})

    def action_reactivate_google_account(self):
        """Reactivate a suspended account; if it was deleted in Admin, recreate it.

        Triggered when a former student is unarchived. Idempotent.
        """
        self.ensure_one()
        company = self.env.company
        if not company.google_ws_enabled:
            return
        if self.contact_type != 'student' or not self.student_email:
            return

        ou = company.google_ws_ou_adult if self.is_adult else company.google_ws_ou_minor
        if company.google_ws_dry_run:
            _logger.info("[GW dry-run] reactivate %s -> suspended=False, OU=%s", self.student_email, ou)
            self.sudo().google_ws_suspended = False
            self.message_post(body=_(
                "Google Workspace account reactivated: %s [dry-run].") % self.student_email)
            return

        service = self._gw()._gw_get_service()
        try:
            service.users().patch(
                userKey=self.student_email,
                body={'suspended': False, 'orgUnitPath': ou},
            ).execute()
        except HttpError as e:
            status = getattr(getattr(e, 'resp', None), 'status', None)
            if status in (404, 403):
                # The account was deleted in Admin: recreate it from scratch.
                self.message_post(body=_(
                    "Google Workspace: account %s no longer exists; recreating it.")
                    % self.student_email)
                self.sudo().write({'student_email': False, 'google_ws_suspended': False})
                self.action_create_google_account()
                return
            _logger.exception("Could not reactivate Google account for %s", self.name)
            raise

        self.sudo().google_ws_suspended = False
        self.message_post(body=_(
            "Google Workspace account reactivated: %(email)s (moved to OU %(ou)s).") % {
                'email': self.student_email, 'ou': ou})
