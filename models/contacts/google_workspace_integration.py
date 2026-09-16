# -*- coding: utf-8 -*-
import base64
import logging

from odoo import models, fields, api, _
from odoo.exceptions import AccessError, UserError

from ..shared.google_workspace_mixin import (
    GW_DEACTIVATION_DELAY_DAYS,
    GW_DELETION_DELAY_DAYS,
    HttpError,
)

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
    google_ws_deactivation_date = fields.Date(
        string="Scheduled Google deactivation", copy=False, readonly=True,
        help="Date the corporate account is due to be suspended, set when the student "
             "leaves. Until then the account keeps working; coming back cancels it.")
    google_ws_deletion_date = fields.Date(
        string="Scheduled Google deletion", copy=False, readonly=True,
        help="Date the suspended corporate account is due to be deleted for good. Set "
             "when the account is suspended; reactivating it cancels the deletion.")
    google_ws_deleted = fields.Boolean(
        string="Google account deleted", default=False, copy=False, readonly=True,
        help="True once the corporate account has been deleted in Google. The address is "
             "kept on the record so it is never handed to a different student.")
    google_ws_state = fields.Selection(
        selection=[
            ('none', 'No Google account'),
            ('active', 'Google account active'),
            ('suspended', 'Google account suspended'),
        ],
        string="Google account status", compute='_compute_google_ws_state', store=True,
        help="Single source of truth for the header buttons: which Google Workspace "
             "action, if any, applies to this student right now.")

    # ------------------------------------------------------------------
    # Compute
    # ------------------------------------------------------------------
    @api.depends('contact_type', 'student_email', 'google_ws_suspended')
    def _compute_google_ws_state(self):
        for partner in self:
            if partner.contact_type != 'student' or not partner.student_email:
                partner.google_ws_state = 'none'
            elif partner.google_ws_suspended:
                partner.google_ws_state = 'suspended'
            else:
                partner.google_ws_state = 'active'

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
        domain = self._gw()._gw_domain()
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
        # birth_date is intentionally NOT required: the account must be created as
        # soon as the student is admitted (matriculation), even with only the GEDAC
        # data, which has no birth date. Without it the student is treated as a minor
        # (is_adult is False) and placed in the minors OU; when the birth date later
        # arrives and reveals an adult, the account is relocated (see write override).
        required = [
            ('firstname',  _("First name")),
            ('lastname',   _("Last name")),
            ('student_id', _("IDALU")),
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
        for partner in self:
            if partner._gw_ready():
                partner.with_delay(
                    identity_key='gw_create_account_%s' % partner.id,
                    description="Create Google Workspace account: %s" % partner.name,
                ).action_create_google_account()

    def _gw_enqueue_relocate(self):
        """Enqueue an OU relocation for students that already have an account, used
        when their birth date is filled in later and changes their minor/adult status
        (accounts created at matriculation from GEDAC data start in the minors OU)."""
        if not self.env.company.google_ws_enabled:
            return
        for partner in self.filtered(
            lambda r: r.contact_type == 'student' and r.student_email
            and not r.google_ws_suspended
        ):
            partner.with_delay(
                identity_key='gw_relocate_%s' % partner.id,
                description="Relocate Google Workspace account: %s" % partner.name,
            ).action_relocate_google_account()

    def _gw_schedule_deactivation(self):
        """Open the grace period instead of suspending the account right away.

        Called when a student is archived or converted to an ex-student
        (withdrawal/graduation/expulsion). Sets the due date, warns the student and posts
        a chatter note; the daily cron does the actual suspension once the date arrives,
        so a student who comes back within the month never loses anything. A student
        whose deactivation is already scheduled keeps the original date - archiving an
        already-archived record must not push the deadline back.
        """
        if not self.env.company.google_ws_enabled:
            return
        for partner in self.filtered(
            lambda p: p.contact_type in ('student', 'alumni', 'withdrawal', 'expelled')
            and p.student_email and not p.google_ws_suspended
            and not p.google_ws_deactivation_date
        ):
            due = self._gw()._gw_schedule_date(GW_DEACTIVATION_DELAY_DAYS)
            partner.sudo().google_ws_deactivation_date = due
            self._gw()._gw_send_lifecycle_warning(
                partner, 'ems.mail_template_google_deactivation_student',
                [partner.email, partner.student_email],
                extra_context={'gw_deletion_date': self._gw()._gw_schedule_date(
                    GW_DEACTIVATION_DELAY_DAYS + GW_DELETION_DELAY_DAYS)})
            partner.message_post(body=_(
                "Google Workspace: the corporate account %(email)s will be suspended on "
                "%(date)s and deleted %(days)s days later. Bringing this student back "
                "before then cancels it.") % {
                    'email': partner.student_email, 'date': due,
                    'days': GW_DELETION_DELAY_DAYS})

    def _gw_cancel_scheduled_deactivation(self):
        """Call off a pending deactivation (the student is back before the deadline)."""
        for partner in self.filtered('google_ws_deactivation_date'):
            partner.sudo().google_ws_deactivation_date = False
            partner.message_post(body=_(
                "Google Workspace: the scheduled suspension of %s has been cancelled.")
                % partner.student_email)

    def action_cancel_scheduled_deactivation(self):
        """Header button: keep the account even though the student is no longer here."""
        self._gw_cancel_scheduled_deactivation()

    @api.model
    def _gw_cron_process_lifecycle(self):
        """Daily cron: run whichever lifecycle step has fallen due.

        Two independent stages - suspension after the first grace period, deletion after
        the second - both of which only enqueue the existing job, so a slow or failing
        Directory API call never blocks the cron. Every candidate is archived by
        definition, hence active_test=False. Students suspended before this feature
        existed have no google_ws_deletion_date and are therefore never deleted.
        """
        if not self.env.company.google_ws_enabled:
            return
        today = fields.Date.context_today(self)
        partners = self.with_context(active_test=False)
        partners.search([
            ('active', '=', False),
            ('google_ws_deactivation_date', '<=', today),
            ('google_ws_suspended', '=', False),
            ('student_email', '!=', False),
        ])._gw_enqueue_suspend()
        partners.search([
            ('active', '=', False),
            ('google_ws_deletion_date', '<=', today),
            ('google_ws_suspended', '=', True),
            ('google_ws_deleted', '=', False),
        ])._gw_enqueue_delete()

    def _gw_enqueue_delete(self):
        """Enqueue the permanent deletion of already-suspended accounts (deduplicated)."""
        if not self.env.company.google_ws_enabled:
            return
        for partner in self.filtered(
            lambda p: p.student_email and p.google_ws_suspended and not p.google_ws_deleted
        ):
            partner.with_delay(
                identity_key='gw_delete_%s' % partner.id,
                description="Delete Google Workspace account: %s" % partner.name,
            ).action_delete_google_account()

    def _gw_enqueue_suspend(self):
        """Enqueue account suspension for students/ex-students with a corporate email
        (deduplicated). Covers archiving and the withdrawal/graduation conversion."""
        if not self.env.company.google_ws_enabled:
            return
        for rec in self.filtered(
            lambda r: r.contact_type in ('student', 'alumni', 'withdrawal', 'expelled')
            and r.student_email and not r.google_ws_suspended
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

        Idempotent: does nothing if the student already has a corporate email. Chatter notes go
        through sudo() because the TAC team, who may press the button, only reads students.
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
            self.sudo().message_post(body=_("Google Workspace: could not generate a free email address."))
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
                self.sudo().message_post(body=_(
                    "Google Workspace: all candidate emails already exist in Google."))
                return

        # Save the corporate email on the student
        self.sudo().student_email = email

        # Deliver credentials: PDF (always) + email (if personal email exists)
        pdf_saved, emailed = self._gw_deliver_credentials(email, password)

        self.sudo().message_post(body=_(
            "Google Workspace account created: %(email)s (OU %(ou)s)%(dry)s. "
            "%(pdf)s%(mail)s."
        ) % {
            'email': email,
            'ou': ou,
            'dry': _(" [dry-run]") if dry_run else '',
            **self._gw_delivery_note(pdf_saved, emailed),
        })

    def _gw_delivery_note(self, pdf_saved, emailed):
        """The 'pdf'/'mail' parts of the chatter note that follows a credentials delivery."""
        return {
            'pdf': _("Credentials PDF saved in the student documentation")
                   if pdf_saved else _("Credentials PDF could NOT be generated (see logs)"),
            'mail': _("; sent by email to %s") % self.email if emailed else _("; no personal email on file"),
        }

    def action_reset_google_password(self):
        """Give the student's Google account a new random password and deliver it like a new
        account's (issue #478). Academic admin and TAC only: the button's groups only hide it,
        so the check is repeated here. TAC merely reads students, hence the sudo() writes."""
        self.ensure_one()
        user = self.env.user
        if not (user.has_group('ems.group_academic_admin') or user.has_group('ems.group_tac')):
            raise AccessError(_("Only administrators and the TAC team can reset a Google password."))
        if self.google_ws_state != 'active':
            raise UserError(_("%s has no active Google account.") % self.name)
        company = self.env.company
        if not company.google_ws_enabled:
            raise UserError(_("The Google Workspace integration is not enabled."))

        email = self.student_email
        password = self._gw()._gw_random_password()
        if company.google_ws_dry_run:
            _logger.info("[GW dry-run] reset password of %s", email)
        else:
            service = self._gw()._gw_get_service()
            try:
                service.users().patch(
                    userKey=email,
                    body={'password': password, 'changePasswordAtNextLogin': True},
                ).execute()
            except HttpError as e:
                _logger.exception("Could not reset the Google password of %s", self.name)
                raise UserError(_(
                    "Google refused to reset the password of %(email)s. Check that the service "
                    "account's admin role has the \"Reset password\" privilege. Error: %(err)s") % {
                        'email': email, 'err': str(e)[:200]}) from e

        # The previous PDFs hold a password that no longer works.
        self.env['ems.student.document'].sudo().search([
            ('partner_id', '=', self.id),
            ('doc_type', '=', 'google_credentials'),
            ('status', '!=', 'cancelled'),
        ]).write({'status': 'cancelled'})
        pdf_saved, emailed = self._gw_deliver_credentials(email, password)
        self.sudo().message_post(body=_(
            "Google Workspace password reset: %(email)s%(dry)s. %(pdf)s%(mail)s.") % {
                'email': email,
                'dry': _(" [dry-run]") if company.google_ws_dry_run else '',
                **self._gw_delivery_note(pdf_saved, emailed),
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
    # Bulk credentials download (issue #478)
    # ------------------------------------------------------------------
    def _get_google_credentials_documents(self):
        """Latest Google credentials PDF of each partner in self, as far as the current user may
        read it (a tutor only reaches their own students' - see rule_ems_student_document_tutor)."""
        documents = self.env['ems.student.document'].search([
            ('partner_id', 'in', self.ids),
            ('doc_type', '=', 'google_credentials'),
            ('doc_file_name', '!=', False),
        ], order='upload_date desc, id desc')
        latest = self.env['ems.student.document']
        for document in documents:
            if document.partner_id not in latest.partner_id:
                latest |= document
        return latest

    def action_download_google_credentials(self):
        """"Download Google credentials" on the students list: one ZIP with the selected
        students' PDFs, served by EmsGoogleCredentialsController. Lives here rather than inline
        in the server action for the same reason as action_portal_access_bulk()."""
        documents = self._get_google_credentials_documents()
        if not documents:
            raise UserError(_("None of the selected students has Google credentials you can download."))
        partner_ids = ','.join(str(partner_id) for partner_id in documents.partner_id.ids)
        return {
            'type': 'ir.actions.act_url',
            'url': f'/ems/google_credentials/download?partner_ids={partner_ids}',
            'target': 'download',
        }

    # ------------------------------------------------------------------
    # Deactivation / reactivation (former students)
    # ------------------------------------------------------------------
    def action_suspend_google_account(self):
        """Suspend the student's Google account and move it to the suspended OU.

        Triggered when a student is archived or converted to an ex-student
        (withdrawal/graduation). Idempotent. Every write, chatter notes included, goes through
        sudo(): the TAC team, who may press the button, only reads students.
        """
        self.ensure_one()
        company = self.env.company
        if not company.google_ws_enabled:
            return
        if self.contact_type not in ('student', 'alumni', 'withdrawal', 'expelled') or not self.student_email:
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
                    # Account no longer exists in Google: nothing to suspend, and nothing
                    # left to delete either - no deletion date is scheduled.
                    self.sudo().write({
                        'google_ws_suspended': True,
                        'google_ws_deactivation_date': False,
                        'google_ws_deleted': True,
                    })
                    self.sudo().message_post(body=_(
                        "Google Workspace: account %s no longer exists; marked as suspended.")
                        % self.student_email)
                    return
                _logger.exception("Could not suspend Google account for %s", self.name)
                self.sudo().message_post(body=_(
                    "Google Workspace: could not suspend %(email)s. Check that the OU "
                    "%(ou)s exists in Admin. Error: %(err)s") % {
                        'email': self.student_email, 'ou': ou, 'err': str(e)[:200]})
                raise

        deletion_due = self._gw()._gw_schedule_date(GW_DELETION_DELAY_DAYS)
        self.sudo().write({
            'google_ws_suspended': True,
            'google_ws_deactivation_date': False,
            'google_ws_deletion_date': deletion_due,
        })
        self.sudo().message_post(body=_(
            "Google Workspace account suspended: %(email)s (moved to OU %(ou)s)%(dry)s. "
            "It will be deleted for good on %(date)s unless the student comes back.") % {
                'email': self.student_email, 'ou': ou, 'date': deletion_due,
                'dry': _(" [dry-run]") if company.google_ws_dry_run else ''})

    def action_delete_google_account(self):
        """Delete the ex-student's Google account for good (queue job / manual button).

        The last stage of the leaving lifecycle: the account has already been suspended
        for a full grace period and the student never came back. This is irreversible -
        the mailbox and Drive content are gone - so it only ever runs on an account that
        went through the whole warned-and-suspended path. Idempotent.

        ``student_email`` is deliberately kept on the record: it is what makes
        ``_gw_email_used_in_ems()`` still consider the address taken, so it is never
        handed to a different student later on.
        """
        self.ensure_one()
        company = self.env.company
        if not company.google_ws_enabled:
            return
        if not self.student_email or not self.google_ws_suspended or self.google_ws_deleted:
            return

        if company.google_ws_dry_run:
            _logger.info("[GW dry-run] delete %s", self.student_email)
        else:
            service = self._gw()._gw_get_service()
            try:
                service.users().delete(userKey=self.student_email).execute()
            except HttpError as e:
                status = getattr(getattr(e, 'resp', None), 'status', None)
                if status not in (404, 403):
                    _logger.exception("Could not delete Google account for %s", self.name)
                    self.message_post(body=_(
                        "Google Workspace: could not delete %(email)s. Error: %(err)s") % {
                            'email': self.student_email, 'err': str(e)[:200]})
                    raise
                # Already gone in Admin: the end state is the one we wanted anyway.

        self.sudo().write({'google_ws_deleted': True, 'google_ws_deletion_date': False})
        self.message_post(body=_(
            "Google Workspace account deleted for good: %(email)s%(dry)s.") % {
                'email': self.student_email,
                'dry': _(" [dry-run]") if company.google_ws_dry_run else ''})

    def action_relocate_google_account(self):
        """Move the account to the OU matching the current age (minor/adult).

        Used when the birth date arrives after the account was created (an account
        created at matriculation from GEDAC data has no birth date, so the student is
        provisionally placed in the minors OU). Idempotent: patching to the same OU
        is a no-op on Google's side. Skips suspended accounts (they live in the
        suspended OU; reactivation re-derives their OU).
        """
        self.ensure_one()
        company = self.env.company
        if not company.google_ws_enabled:
            return
        if self.contact_type != 'student' or not self.student_email or self.google_ws_suspended:
            return

        ou = company.google_ws_ou_adult if self.is_adult else company.google_ws_ou_minor
        if company.google_ws_dry_run:
            _logger.info("[GW dry-run] relocate %s -> OU=%s", self.student_email, ou)
            return

        service = self._gw()._gw_get_service()
        try:
            service.users().patch(
                userKey=self.student_email, body={'orgUnitPath': ou},
            ).execute()
        except HttpError:
            _logger.exception("Could not relocate Google account for %s", self.name)
            raise
        self.message_post(body=_(
            "Google Workspace account moved to OU %(ou)s.") % {'ou': ou})

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
        if self.google_ws_deleted:
            # The grace period ran out and the account is gone for good: there is nothing
            # to reactivate, so a brand-new one is created (new address, new credentials).
            self.message_post(body=_(
                "Google Workspace: account %s was deleted; creating a new one.")
                % self.student_email)
            self.sudo().write({
                'student_email': False, 'google_ws_suspended': False,
                'google_ws_deleted': False, 'google_ws_deletion_date': False,
            })
            self.action_create_google_account()
            return

        ou = company.google_ws_ou_adult if self.is_adult else company.google_ws_ou_minor
        if company.google_ws_dry_run:
            _logger.info("[GW dry-run] reactivate %s -> suspended=False, OU=%s", self.student_email, ou)
            self.sudo().write({
                'google_ws_suspended': False, 'google_ws_deletion_date': False})
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
                self.sudo().write({
                    'student_email': False, 'google_ws_suspended': False,
                    'google_ws_deletion_date': False,
                })
                self.action_create_google_account()
                return
            _logger.exception("Could not reactivate Google account for %s", self.name)
            raise

        self.sudo().write({'google_ws_suspended': False, 'google_ws_deletion_date': False})
        self.message_post(body=_(
            "Google Workspace account reactivated: %(email)s (moved to OU %(ou)s).") % {
                'email': self.student_email, 'ou': ou})

    # ------------------------------------------------------------------
    # CRUD override (trigger)
    # ------------------------------------------------------------------
    def unlink(self):
        # Hard deletion bypasses write() (no 'active' flip), so the Google account
        # would otherwise stay active forever. Suspend synchronously (not queued)
        # since the partner record — and its student_email — won't exist anymore
        # once this method returns. Mirrors HrEmployeeGoogleWorkspace.unlink().
        if self.env.company.google_ws_enabled:
            for partner in self.filtered(
                lambda p: p.contact_type in ('student', 'alumni', 'withdrawal', 'expelled')
                and p.student_email and not p.google_ws_suspended
            ):
                try:
                    partner.action_suspend_google_account()
                except Exception:
                    _logger.exception(
                        "Could not suspend Google Workspace account for %s before deletion",
                        partner.name)
        return super().unlink()
