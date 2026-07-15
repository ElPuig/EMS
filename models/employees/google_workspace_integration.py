# -*- coding: utf-8 -*-
import base64
import logging

from odoo import SUPERUSER_ID, _, api, fields, models
from odoo.exceptions import UserError

from ..shared.google_workspace_mixin import HttpError

_logger = logging.getLogger(__name__)


class HrEmployeeGoogleWorkspace(models.Model):
    # NOTE: we do NOT add 'google.workspace.mixin' to _inherit here. hr.employee
    # (via ems.employee.base) declares role_ids as a Many2many with a manual
    # relation table shared with hr.employee.public; mixing an extra abstract
    # model into hr.employee's inheritance re-triggers that shared-table check
    # and Odoo refuses to load. Instead we reach the shared helpers through
    # self.env['google.workspace.mixin'] (see _gw()).
    _inherit = 'hr.employee'

    google_ws_login = fields.Char(
        string="Suggested Google username", copy=False,
        help="Preferred username (the part before @domain) tried first when creating the "
             "corporate account. If it is already taken in Google, an alternative is "
             "generated automatically from the name.")
    google_ws_suspended = fields.Boolean(
        string="Google account suspended", default=False, copy=False,
        help="True when the employee's Google Workspace account is suspended (former staff).")
    google_ws_manual_email = fields.Boolean(
        string="Assign corporate email manually", copy=False,
        help="Tick to edit the Work Email by hand instead of letting EMS generate it "
             "when creating the Google account. For exceptional cases only.")
    google_ws_domain = fields.Char(
        related='company_id.google_ws_domain', readonly=True,
        string="Google Workspace domain")
    google_ws_missing_notice_sent = fields.Boolean(
        copy=False, default=False,
        help="Internal flag: a chatter note about missing required data was already "
             "posted, to avoid repeating it on every write.")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _gw(self):
        """Shared Google Workspace helpers (normalize / service / password / phone)."""
        return self.env['google.workspace.mixin']

    def _gw_split_name(self):
        """Split the single ``name`` field into (given name, family names).

        Best-effort heuristic: first token is the given name, the rest are the
        surnames. The suggested login (``google_ws_login``) is the intended
        primary path, so this only feeds the fallback and the Google name.
        """
        self.ensure_one()
        parts = (self.name or '').strip().split()
        if not parts:
            return '', ''
        return parts[0], ' '.join(parts[1:])

    def _gw_login_candidates(self):
        """Ordered list of login prefixes (without domain).

        The suggested login goes first; the rest are generated from the name
        (initial + surnames) with numeric differentiators, since employees have
        no birth date or IDALU to disambiguate.
        """
        self.ensure_one()
        gw = self._gw()
        candidates = []

        # Accept the suggested username with or without domain (keep the local part).
        raw_login = self.google_ws_login or ''
        if '@' in raw_login:
            raw_login = raw_login.split('@', 1)[0]
        suggested = gw._gw_normalize(raw_login)
        if suggested:
            candidates.append(suggested)

        given, family = self._gw_split_name()
        first = gw._gw_normalize(given)
        fam_parts = family.split()
        apellido1 = gw._gw_normalize(fam_parts[0]) if fam_parts else ''
        apellido2 = gw._gw_normalize(fam_parts[1]) if len(fam_parts) > 1 else ''
        ini_nombre = first[0] if first else ''
        ini_ape2 = apellido2[0] if apellido2 else ''

        base1 = '%s%s' % (ini_nombre, apellido1)          # jmorote
        base2 = '%s%s' % (base1, ini_ape2)                # jmorotep
        num_base = base2 if ini_ape2 else base1

        if base1:
            candidates.append(base1)
        if base2 and base2 != base1:
            candidates.append(base2)
        if num_base:
            for i in range(1, 6):
                candidates.append('%s%02d' % (num_base, i))
            nif = ''.join(c for c in (self.sudo().identification_id or '') if c.isdigit())
            if nif:
                candidates.append('%s%s' % (num_base, nif[-2:]))
                candidates.append('%s%s' % (num_base, nif[-4:]))

        # Dedup preserving order
        seen, result = set(), []
        for c in candidates:
            if c and c not in seen:
                seen.add(c)
                result.append(c)
        return result

    def _gw_email_used_in_ems(self, email):
        """True if the email is already assigned to another employee or a student."""
        emp = self.sudo().search_count([
            ('work_email', '=', email), ('id', '!=', self.id),
        ])
        student = self.env['res.partner'].sudo().search_count([
            ('student_email', '=', email),
        ])
        return bool(emp or student)

    def _gw_email_full_candidates(self):
        """Full corporate email candidates (with domain) not yet used in EMS."""
        domain = self.env.company.google_ws_domain or 'elpuig.xeill.net'
        candidates = ['%s@%s' % (p, domain) for p in self._gw_login_candidates()]
        return [e for e in candidates if not self._gw_email_used_in_ems(e)]

    # ------------------------------------------------------------------
    # Readiness checks
    # ------------------------------------------------------------------
    def _gw_missing_fields(self):
        """Return the labels of the required fields that are still empty."""
        self.ensure_one()
        emp = self.sudo()
        required = [
            ('name',          _("Name")),
            ('private_email', _("Personal email")),
        ]
        return [label for fname, label in required if not emp[fname]]

    def _gw_ready(self):
        """True if the employee has all the data required to create the account."""
        self.ensure_one()
        emp = self.sudo()
        return (
            emp.employee_type in ('teacher', 'asp')
            and not emp.work_email
            and not emp.google_ws_manual_email
            and not self._gw_missing_fields()
        )

    def _gw_enqueue_if_ready(self):
        """Enqueue the async account creation for staff that are ready.

        Deduplicated via identity_key so repeated writes (autosave) do not
        enqueue several jobs for the same employee.
        """
        if not self.env.company.google_ws_enabled:
            return
        for employee in self:
            if employee._gw_ready():
                employee.with_delay(
                    identity_key='gw_emp_create_%s' % employee.id,
                    description="Create Google Workspace account: %s" % employee.name,
                ).action_create_google_account()
            else:
                employee._gw_notify_missing_fields()

    def _gw_notify_missing_fields(self):
        """Post a one-off chatter note when the account cannot be created yet
        because required data is missing, so the reason is not silently lost.

        Deduplicated via ``google_ws_missing_notice_sent``: once posted, it is
        not repeated on further writes while the data is still missing.
        """
        self.ensure_one()
        emp = self.sudo()
        if emp.employee_type not in ('teacher', 'asp') or emp.work_email or emp.google_ws_manual_email:
            return
        if emp.google_ws_missing_notice_sent:
            return
        missing = self._gw_missing_fields()
        if not missing:
            return
        self.message_post(body=_(
            "Google Workspace: the corporate account was not created automatically. "
            "Missing required data: %s."
        ) % ", ".join(missing))
        emp.google_ws_missing_notice_sent = True

    def _gw_enqueue_suspend(self):
        """Enqueue account suspension for staff with a corporate email (deduplicated)."""
        if not self.env.company.google_ws_enabled:
            return
        for employee in self.sudo().filtered(
            lambda e: e.employee_type in ('teacher', 'asp') and e.work_email and not e.google_ws_suspended
        ):
            employee.with_delay(
                identity_key='gw_emp_suspend_%s' % employee.id,
                description="Suspend Google Workspace account: %s" % employee.name,
            ).action_suspend_google_account()

    def _gw_enqueue_reactivate(self):
        """Enqueue account reactivation for staff with a corporate email (deduplicated)."""
        if not self.env.company.google_ws_enabled:
            return
        for employee in self.sudo().filtered(
            lambda e: e.employee_type in ('teacher', 'asp') and e.work_email
        ):
            employee.with_delay(
                identity_key='gw_emp_reactivate_%s' % employee.id,
                description="Reactivate Google Workspace account: %s" % employee.name,
            ).action_reactivate_google_account()

    # ------------------------------------------------------------------
    # Main action (queue_job target / manual button)
    # ------------------------------------------------------------------
    def action_create_google_account(self):
        """Create the employee's Google Workspace account and deliver credentials.

        Idempotent: does nothing if the employee already has a corporate email.
        """
        self.ensure_one()
        company = self.env.company
        if not company.google_ws_enabled:
            return
        if self.employee_type not in ('teacher', 'asp'):
            return

        emp = self.sudo()
        domain = company.google_ws_domain or 'elpuig.xeill.net'

        # Already has a work email: adopt if corporate, warn otherwise.
        if emp.work_email:
            if emp.work_email.endswith('@%s' % domain):
                # Corporate account already exists / is managed (manual email,
                # pre-integration staff): make sure the EMS user exists too.
                if not emp.user_id:
                    self._ems_create_user(google_id=self._gw_google_user_id())
                return
            self.message_post(body=_(
                "Google Workspace: the employee already has a non-corporate work email "
                "(%s); the corporate account was NOT created to avoid overwriting it.")
                % emp.work_email)
            return

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
        ou = company.google_ws_ou_asp if emp.employee_type == 'asp' else company.google_ws_ou_teacher

        given, family = self._gw_split_name()
        base_body = {
            'name': {'givenName': given or '', 'familyName': family or ''},
            'password': password,
            'changePasswordAtNextLogin': True,
            'orgUnitPath': ou,
        }
        recovery_email = emp.private_email or False
        if recovery_email:
            base_body['recoveryEmail'] = recovery_email
        recovery_phone = gw._gw_format_phone(emp.mobile_phone or emp.private_phone)
        if recovery_phone:
            base_body['recoveryPhone'] = recovery_phone

        # Pick the first candidate that Google accepts. Existence is resolved on
        # insert() via the 409 conflict (the suggested login falls back to the
        # generated candidates when it is already taken).
        email = None
        google_id = False
        if dry_run:
            email = candidates[0]
            _logger.info("[GW dry-run] users().insert payload: %s",
                         dict(base_body, primaryEmail=email, password='***'))
        else:
            for cand in candidates:
                body = dict(base_body, primaryEmail=cand)
                try:
                    created = service.users().insert(body=body).execute()
                    email = cand
                    google_id = created.get('id')
                    break
                except HttpError as e:
                    status = getattr(getattr(e, 'resp', None), 'status', None)
                    if status == 409:
                        # Email already taken in Google: try the next candidate.
                        continue
                    _logger.exception("Google Workspace account creation failed for %s", self.name)
                    if status == 403:
                        raise UserError(_(
                            "Google Workspace: not authorized to create accounts in OU "
                            "%(ou)s. The service account's custom admin role must be "
                            "granted access to this Organizational Unit in Google Admin."
                        ) % {'ou': ou}) from e
                    raise
            if not email:
                self.message_post(body=_(
                    "Google Workspace: all candidate emails already exist in Google."))
                return

        # Save the corporate email on the employee
        emp.write({'work_email': email, 'google_ws_missing_notice_sent': False})

        # Create the EMS user (login = corporate email, Google sign-in pre-linked)
        self._ems_create_user(google_id=google_id)

        # Deliver credentials: PDF attachment (always) + email (if personal email exists)
        pdf_saved, emailed = self._gw_deliver_credentials(email, password)

        self.message_post(body=_(
            "Google Workspace account created: %(email)s (OU %(ou)s)%(dry)s. "
            "%(pdf)s%(mail)s."
        ) % {
            'email': email,
            'ou': ou,
            'dry': _(" [dry-run]") if dry_run else '',
            'pdf': _("Credentials PDF saved as attachment")
                   if pdf_saved else _("Credentials PDF could NOT be generated (see logs)"),
            'mail': _("; sent by email to %s") % recovery_email if emailed else _("; no personal email on file"),
        })

    def _gw_deliver_credentials(self, email, password):
        """Generate the credentials PDF (attachment) and send the welcome email (if any).

        Returns (pdf_saved, emailed).
        """
        self.ensure_one()
        pdf_saved = False
        # 1) PDF -> ir.attachment on the employee record
        try:
            pdf, _ct = self.env['ir.actions.report'].sudo()._render_qweb_pdf(
                'ems.report_google_credentials_employee', [self.id],
                data={'gw_email': email, 'gw_password': password},
            )
            self.env['ir.attachment'].sudo().create({
                'name': 'Credencials_Google_%s.pdf' % self.id,
                'type': 'binary',
                'datas': base64.b64encode(pdf),
                'res_model': 'hr.employee',
                'res_id': self.id,
                'mimetype': 'application/pdf',
            })
            pdf_saved = True
        except Exception:
            _logger.exception("Could not generate Google credentials PDF for %s", self.name)

        # 2) Welcome email to the personal address (if any)
        emailed = False
        recovery_email = self.sudo().private_email
        if recovery_email:
            template = self.env.ref('ems.mail_template_google_welcome_employee', raise_if_not_found=False)
            if template:
                template.sudo().with_context(
                    gw_email=email, gw_password=password,
                ).send_mail(self.id, force_send=True)
                emailed = True
        return pdf_saved, emailed

    # ------------------------------------------------------------------
    # EMS user (res.users)
    # ------------------------------------------------------------------
    def _gw_google_user_id(self):
        """Numeric Google user id of ``work_email`` via the Directory API.

        Returns False when it cannot be resolved (dry-run, API error, libs
        missing): the EMS user is then created without the OAuth pre-link.
        Note that the OU-scoped admin role answers 403 - not 404 - for unknown
        users, so errors are swallowed here, never re-raised.
        """
        self.ensure_one()
        emp = self.sudo()
        if not emp.work_email or self.env.company.google_ws_dry_run:
            return False
        try:
            service = self._gw()._gw_get_service()
            info = service.users().get(userKey=emp.work_email).execute()
            return info.get('id') or False
        except Exception:
            _logger.warning(
                "Google Workspace: could not resolve the Google user id for %s",
                emp.work_email, exc_info=True)
            return False

    def _ems_user_groups(self):
        """Security groups granted to the auto-created EMS user.

        ems.group_teacher does not imply base.group_user, so the internal-user
        group is always granted explicitly. ASP staff only become internal
        users; their department groups arrive later via roles/job
        (_sync_security_groups).
        """
        self.ensure_one()
        groups = self.env.ref('base.group_user')
        if self.sudo().employee_type == 'teacher':
            groups |= self.env.ref('ems.group_teacher')
        return groups

    def _ems_link_google_signin(self, user, google_id):
        """Pre-link "Sign in with Google" on the user (oauth_uid + provider).

        Skipped when the id is unknown, or already taken by another user
        (auth_oauth unique constraint). Returns True when the user ends up
        linked to Google sign-in.
        """
        user = user.sudo()
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

    def _ems_create_user(self, google_id=False):
        """Create (or re-link) the employee's EMS user for the corporate account.

        Called right after the Google Workspace account exists so staff can log
        into EMS with "Sign in with Google" (no password/invitation email is
        sent). Idempotent. Returns the linked res.users record (empty recordset
        when not applicable).
        """
        self.ensure_one()
        emp = self.sudo()
        Users = self.env['res.users'].sudo()
        domain = emp.company_id.google_ws_domain or 'elpuig.xeill.net'
        if (emp.employee_type not in ('teacher', 'asp') or not emp.work_email
                or not emp.work_email.endswith('@%s' % domain)):
            return Users

        if emp.user_id:
            # Already linked: only backfill the Google sign-in if missing.
            self._ems_link_google_signin(emp.user_id, google_id)
            return emp.user_id

        login = emp.work_email.lower()
        user = Users.with_context(active_test=False).search(
            [('login', 'in', [emp.work_email, login])], limit=1)
        if user:
            if self.sudo().with_context(active_test=False).search_count(
                    [('user_id', '=', user.id), ('id', '!=', emp.id)]):
                self.message_post(body=_(
                    "EMS user not linked: %s already belongs to another employee.")
                    % user.login)
                return Users
            vals = {}
            if not user.active:
                vals['active'] = True
            # Keep login/email aligned with the corporate address so the
            # work_email stored compute (work_contact_id.email) survives the link.
            if user.login != login:
                vals['login'] = login
            if user.email != emp.work_email:
                vals['email'] = emp.work_email
            missing_groups = self._ems_user_groups() - user.groups_id
            if missing_groups:
                vals['groups_id'] = [(4, group.id) for group in missing_groups]
            if vals:
                user.write(vals)
            created = False
        else:
            given, family = self._gw_split_name()
            user = Users.with_context(no_reset_password=True).create({
                'login': login,
                # email is load-bearing: linking user_id swaps work_contact_id
                # to the user's partner and work_email recomputes from its email.
                'email': emp.work_email,
                'firstname': given or emp.name,
                'lastname': family or False,
                'mobile': emp.mobile_phone or emp.private_phone or False,
                'tz': emp.tz or self.env.user.tz or False,
                'company_id': emp.company_id.id,
                'company_ids': [(4, emp.company_id.id)],
                'groups_id': [(6, 0, self._ems_user_groups().ids)],
            })
            created = True

        signin_linked = self._ems_link_google_signin(user, google_id)
        emp.write({'user_id': user.id})
        # The write() trigger only syncs role/job groups on role_ids/job_id
        # changes, so apply them explicitly now that the user exists.
        emp._sync_security_groups()
        action_msg = (_("EMS user created: %s.") if created
                      else _("EMS user re-linked: %s.")) % user.login
        signin_msg = (_("Sign in with Google is pre-linked.") if signin_linked
                      else _("Sign in with Google is not pre-linked (Google user id unavailable)."))
        self.message_post(body=f"{action_msg} {signin_msg}")
        return user

    def _ems_sync_user_active(self, active):
        """Mirror the employee's active flag on the linked EMS user.

        Synchronous and independent of google_ws_enabled: a former employee
        must lose EMS access immediately even when the Google integration is
        disabled or the job queue is down.
        """
        for employee in self.sudo():
            user = employee.user_id
            if (employee.employee_type not in ('teacher', 'asp') or not user
                    or user.id == SUPERUSER_ID or user == self.env.user
                    or user.active == active):
                continue
            user.sudo().write({'active': active})

    # ------------------------------------------------------------------
    # Deactivation / reactivation (former staff)
    # ------------------------------------------------------------------
    def action_suspend_google_account(self):
        """Suspend the employee's Google account and move it to the suspended OU.

        Triggered when an employee is archived. Idempotent.
        """
        self.ensure_one()
        company = self.env.company
        if not company.google_ws_enabled:
            return
        emp = self.sudo()
        if emp.employee_type not in ('teacher', 'asp') or not emp.work_email:
            return
        if emp.google_ws_suspended:
            return

        ou = company.google_ws_ou_staff_suspended or '/claustro/bajas'
        if company.google_ws_dry_run:
            _logger.info("[GW dry-run] suspend %s -> suspended=True, OU=%s", emp.work_email, ou)
        else:
            service = self._gw()._gw_get_service()
            try:
                service.users().patch(
                    userKey=emp.work_email,
                    body={'suspended': True, 'orgUnitPath': ou},
                ).execute()
            except HttpError as e:
                status = getattr(getattr(e, 'resp', None), 'status', None)
                if status in (404, 403):
                    # Account no longer exists in Google: nothing to suspend.
                    emp.google_ws_suspended = True
                    self.message_post(body=_(
                        "Google Workspace: account %s no longer exists; marked as suspended.")
                        % emp.work_email)
                    return
                _logger.exception("Could not suspend Google account for %s", self.name)
                self.message_post(body=_(
                    "Google Workspace: could not suspend %(email)s. Check that the OU "
                    "%(ou)s exists in Admin. Error: %(err)s") % {
                        'email': emp.work_email, 'ou': ou, 'err': str(e)[:200]})
                raise

        emp.google_ws_suspended = True
        self.message_post(body=_(
            "Google Workspace account suspended: %(email)s (moved to OU %(ou)s)%(dry)s.") % {
                'email': emp.work_email, 'ou': ou,
                'dry': _(" [dry-run]") if company.google_ws_dry_run else ''})

    def action_reactivate_google_account(self):
        """Reactivate a suspended account; if it was deleted in Admin, recreate it.

        Triggered when a former employee is unarchived. Idempotent.
        """
        self.ensure_one()
        company = self.env.company
        if not company.google_ws_enabled:
            return
        emp = self.sudo()
        if emp.employee_type not in ('teacher', 'asp') or not emp.work_email:
            return

        ou = company.google_ws_ou_asp if emp.employee_type == 'asp' else company.google_ws_ou_teacher
        if company.google_ws_dry_run:
            _logger.info("[GW dry-run] reactivate %s -> suspended=False, OU=%s", emp.work_email, ou)
            emp.google_ws_suspended = False
            self.message_post(body=_(
                "Google Workspace account reactivated: %s [dry-run].") % emp.work_email)
            return

        service = self._gw()._gw_get_service()
        try:
            service.users().patch(
                userKey=emp.work_email,
                body={'suspended': False, 'orgUnitPath': ou},
            ).execute()
        except HttpError as e:
            status = getattr(getattr(e, 'resp', None), 'status', None)
            if status in (404, 403):
                # The account was deleted in Admin: recreate it from scratch.
                self.message_post(body=_(
                    "Google Workspace: account %s no longer exists; recreating it.")
                    % emp.work_email)
                emp.write({'work_email': False, 'google_ws_suspended': False})
                self.action_create_google_account()
                return
            _logger.exception("Could not reactivate Google account for %s", self.name)
            raise

        emp.google_ws_suspended = False
        self.message_post(body=_(
            "Google Workspace account reactivated: %(email)s (moved to OU %(ou)s).") % {
                'email': emp.work_email, 'ou': ou})

    # ------------------------------------------------------------------
    # CRUD overrides (triggers)
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        employees = super().create(vals_list)
        employees._gw_enqueue_if_ready()
        return employees

    def write(self, vals):
        res = super().write(vals)
        self._gw_enqueue_if_ready()
        if 'active' in vals:
            if vals.get('active'):
                self._gw_enqueue_reactivate()
            else:
                self._gw_enqueue_suspend()
            self._ems_sync_user_active(bool(vals.get('active')))
        return res

    def unlink(self):
        # Hard deletion bypasses write() (no 'active' flip), so the Google account
        # would otherwise stay active forever. Suspend synchronously (not queued)
        # since the employee record - and its work_email - won't exist anymore
        # once this method returns.
        if self.env.company.google_ws_enabled:
            for employee in self.filtered(
                lambda e: e.employee_type in ('teacher', 'asp')
                and e.work_email and not e.google_ws_suspended
            ):
                try:
                    employee.action_suspend_google_account()
                except Exception:
                    _logger.exception(
                        "Could not suspend Google Workspace account for %s before deletion",
                        employee.name)
        # The linked EMS user must not stay active once its employee is gone.
        self._ems_sync_user_active(False)
        return super().unlink()
