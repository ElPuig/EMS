# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api, _
from odoo.tools import email_normalize
from ..shared import base

_logger = logging.getLogger(__name__)


class EmsPortalAccessWizard(models.TransientModel):
    _name = 'ems.portal.access.wizard'
    _description = 'Bulk portal access for students and families'

    mode = fields.Selection([
        ('grant',  'Grant access'),
        ('revoke', 'Revoke access'),
        ('resend', 'Resend portal invitation (users who never logged in)'),
    ], string='Action', default='grant', required=True)
    student_ids = fields.Many2many(
        'res.partner', string='Students',
        domain=[('contact_type', 'in', ('student', 'applicant'))],
    )
    line_ids = fields.One2many(
        'ems.portal.access.wizard.line', 'wizard_id',
        string='Recipients',
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_ids = self.env.context.get('active_ids') or []
        students = self.env['res.partner'].browse(active_ids).filtered(
            lambda p: p.contact_type in ('student', 'applicant'))
        # A tutor only manages its own students; admin/secretary manage any.
        students = students.filtered(self._user_can_manage)
        res['student_ids'] = [(6, 0, students.ids)]
        res['line_ids'] = self._build_lines(students)
        return res

    @api.onchange('mode')
    def _onchange_mode(self):
        """Rebuild the preview. In 'resend' mode keep only recipients with portal
        access that never logged in (the only ones that will actually be emailed)."""
        # In an onchange the related records are virtual (NewId); use ._origin so the
        # relation search against res.partner.relation.all hits the real DB records.
        lines = self._build_lines(self.student_ids._origin)
        if self.mode == 'resend':
            lines = [cmd for cmd in lines
                     if cmd[2].get('has_portal') and not cmd[2].get('connected')]
        self.line_ids = [(5, 0, 0)] + lines

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _user_can_manage(self, student):
        """Admin/secretary manage any student; a tutor only its own students."""
        if self.env.user.has_group('ems.group_academic_admin') or self.env.user.has_group('ems.group_secretary'):
            return True
        return base.EmsBase.user_acts_as_tutor(self, student.tutor_id)

    def _build_lines(self, students):
        """Build the One2many command list for the recipient preview."""
        lines = []
        for student in students:
            # A minor student with no family on file still gets his own, view-only account:
            # the missing family is flagged on his line instead of replacing it.
            no_family = not student._ems_notification_recipients()
            for r in student._ems_portal_access_recipients():
                user = r.with_context(active_test=False).user_ids[:1]
                has_portal = bool(user) and user._is_portal()
                connected = has_portal and bool(user.login_date)
                if not r.email:
                    note = _('Recipient without email')
                elif no_family:
                    note = _('No family contact found')
                elif r._ems_email_shared_with_family():
                    # Issue #833: the login with that email is the family's.
                    note = _('Same email as the family: signs in with the corporate email %s') % (
                        r.student_email) if r.student_email else _(
                        'Same email as the family: no access until the corporate email exists')
                else:
                    note = ''
                lines.append((0, 0, {
                    'student_id': student.id,
                    'recipient_id': r.id,
                    'recipient_email': r.email,
                    'has_portal': has_portal,
                    'connected': connected,
                    'note': note,
                }))
        return lines

    def _apply_one(self, partner):
        """Grant/revoke/resend portal access for a single partner via the native portal wizard.

        Runs with sudo so tutors (who lack user-creation rights) can still grant
        access to their own students/families.
        Returns 'granted'/'revoked'/'resent'/'skipped'.
        """
        wizard = self.env['portal.wizard'].with_context(active_ids=partner.ids).sudo().create({})
        wu = wizard.user_ids.filtered(lambda u: u.partner_id.id == partner.id)[:1]
        if not wu:
            return 'skipped'
        if self.mode == 'grant':
            if wu.is_portal or wu.is_internal:
                return 'skipped'
            partner._ems_check_portal_login()
            # Realign the login of a reactivated user, and take the family's email back from a
            # student who holds it as login (issue #833), before Odoo checks it is free.
            (partner._ems_students_sharing_email() | partner)._ems_sync_portal_login()
            wu.invalidate_recordset(['email_state'])
            wu.action_grant_access()
            return 'granted'
        elif self.mode == 'resend':
            # Only portal users that never logged in (expired invitation token).
            user = wu.partner_id.with_context(active_test=False).user_ids[:1]
            if not wu.is_portal or (user and user.login_date):
                return 'skipped'
            wu.action_invite_again()
            return 'resent'
        else:
            if not wu.is_portal:
                return 'skipped'
            wu.action_revoke_access()
            return 'revoked'

    # ------------------------------------------------------------------
    # Main action
    # ------------------------------------------------------------------
    def action_apply(self):
        self.ensure_one()
        granted = revoked = resent = skipped = 0
        issues = []
        for student in self.student_ids:
            if not self._user_can_manage(student):
                issues.append(_("%s: not your student") % student.name)
                continue
            if student.contact_type != 'applicant' and student.is_adult and not student.email:
                issues.append(_("%s: adult student without main email") % student.name)
                continue
            if not student._ems_notification_recipients():
                issues.append(_("%s: no family contact to manage") % student.name)
            for r in student._ems_portal_access_recipients():
                if not r.email:
                    issues.append(_("%(student)s: recipient %(name)s has no email") % {
                        'student': student.name, 'name': r.name})
                    continue
                try:
                    with self.env.cr.savepoint():
                        result = self._apply_one(r)
                    if result == 'granted':
                        granted += 1
                    elif result == 'revoked':
                        revoked += 1
                    elif result == 'resent':
                        resent += 1
                    else:
                        skipped += 1
                except Exception as e:
                    msg = e.args[0] if getattr(e, 'args', None) else str(e)
                    issues.append('%s: %s' % (r.name, msg))

        # Build the result notification
        parts = []
        if granted:
            parts.append(_("%s access(es) granted") % granted)
        if revoked:
            parts.append(_("%s access(es) revoked") % revoked)
        if resent:
            parts.append(_("%s invitation(s) resent") % resent)
        if skipped:
            parts.append(_("%s skipped (already in the desired state)") % skipped)
        summary = ", ".join(parts) or _("Nothing to do")
        if issues:
            summary += "\n" + _("Issues:") + "\n- " + "\n- ".join(issues)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Portal access"),
                'message': summary,
                'type': 'warning' if issues else 'success',
                'sticky': bool(issues),
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }


class EmsPortalAccessWizardLine(models.TransientModel):
    _name = 'ems.portal.access.wizard.line'
    _description = 'Portal access recipient (preview)'

    wizard_id = fields.Many2one('ems.portal.access.wizard', ondelete='cascade')
    student_id = fields.Many2one('res.partner', string='Student')
    recipient_id = fields.Many2one('res.partner', string='Recipient')
    recipient_email = fields.Char(string='Email')
    has_portal = fields.Boolean(string='Has portal access')
    connected = fields.Boolean(string='Connected')
    note = fields.Char(string='Note')


class PortalWizardUser(models.TransientModel):
    """Odoo's portal wizard line, with the login of issue #833: a student sharing the main email
    with the family gets the corporate email as login (res.partner._ems_portal_login), so both
    the "already registered" check and the user creation look at that login, not at the email.
    Every EMS grant goes through here (ems.portal.access.wizard._apply_one), and so does Odoo's
    own "Grant portal access" action."""
    _inherit = 'portal.wizard.user'

    def _ems_login(self):
        self.ensure_one()
        return self.partner_id._ems_portal_login(self.email)

    def _get_similar_users_domain(self, portal_users_with_email):
        return [('login', 'in', [portal_user._ems_login() for portal_user in portal_users_with_email])]

    def _is_portal_similar_than_user(self, user, portal_user):
        return user['login'] == portal_user._ems_login() and user['id'] != portal_user.user_id.id

    def _create_user(self):
        login = self._ems_login()
        if login == email_normalize(self.email):
            return super()._create_user()
        self.partner_id._ems_check_portal_login()
        return self.env['res.users'].with_context(no_reset_password=True)._create_user_from_template({
            'email': email_normalize(self.email),
            'login': login,
            'partner_id': self.partner_id.id,
            'company_id': self.env.company.id,
            'company_ids': [(6, 0, self.env.company.ids)],
        })
