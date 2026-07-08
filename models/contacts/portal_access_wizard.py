# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api, _
from odoo.tools import email_normalize

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
        if self.env.user.has_group('ems.group_admin') or self.env.user.has_group('ems.group_secretary'):
            return True
        return bool(student.tutor_id) and student.tutor_id.user_id.id == self.env.uid

    def _resolve_recipients(self, student):
        """Partners that should get/lose portal access for this student.

        - Applicant -> the applicant himself (his personal `email`), regardless of
          age: at preinscription the family contacts are not known yet. Age and
          family are reviewed later, once admitted as a student.
        - Adult student -> the student himself (uses his main `email`).
        - Minor student -> his associated family contacts.
        """
        if student.contact_type == 'applicant':
            return student
        if student.is_adult:
            return student
        rels = self.env['res.partner.relation.all'].sudo().search([
            ('this_partner_id', '=', student.id),
            ('other_partner_id.contact_type', '=', 'family'),
        ])
        return rels.mapped('other_partner_id')

    def _build_lines(self, students):
        """Build the One2many command list for the recipient preview."""
        lines = []
        for student in students:
            recipients = self._resolve_recipients(student)
            if not recipients:
                lines.append((0, 0, {
                    'student_id': student.id,
                    'note': _('No family contact found'),
                }))
                continue
            for r in recipients:
                user = r.with_context(active_test=False).user_ids[:1]
                has_portal = bool(user) and user._is_portal()
                connected = has_portal and bool(user.login_date)
                note = '' if r.email else _('Recipient without email')
                lines.append((0, 0, {
                    'student_id': student.id,
                    'recipient_id': r.id,
                    'recipient_email': r.email,
                    'has_portal': has_portal,
                    'connected': connected,
                    'note': note,
                }))
        return lines

    def _sync_user_login(self, wu):
        """Sync a (re)granted portal user's login/email with the partner's current email.

        Revoking access archives the res.users instead of deleting it, keeping the old
        login/email. When access is later granted again, Odoo reactivates that archived
        user without refreshing its login, so a changed email never takes effect. We
        realign it here, unless another user already owns that login (in which case the
        native _assert_user_email_uniqueness raises a clean "already registered" error).
        """
        user = wu.user_id.sudo()
        new_email = email_normalize(wu.partner_id.email)
        if not user or not new_email or email_normalize(user.login) == new_email:
            return
        conflict = self.env['res.users'].with_context(active_test=False).sudo().search_count(
            [('login', '=', new_email), ('id', '!=', user.id)])
        if not conflict:
            user.write({'login': new_email, 'email': new_email})

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
            self._sync_user_login(wu)
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
            recipients = self._resolve_recipients(student)
            if not recipients:
                issues.append(_("%s: no family contact to manage") % student.name)
                continue
            for r in recipients:
                if not r.email:
                    issues.append(_("%(student)s: recipient %(name)s has no email") % {
                        'student': student.name, 'name': r.name})
                    continue
                try:
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
