# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)


class EmsPortalAccessWizard(models.TransientModel):
    _name = 'ems.portal.access.wizard'
    _description = 'Bulk portal access for students and families'

    mode = fields.Selection([
        ('grant',  'Grant access'),
        ('revoke', 'Revoke access'),
    ], string='Action', default='grant', required=True)
    student_ids = fields.Many2many(
        'res.partner', string='Students',
        domain=[('contact_type', '=', 'student')],
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
            lambda p: p.contact_type == 'student')
        res['student_ids'] = [(6, 0, students.ids)]
        res['line_ids'] = self._build_lines(students)
        return res

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

        - Adult student -> the student himself (uses his main `email`).
        - Minor student -> his associated family contacts.
        """
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
                note = '' if r.email else _('Recipient without email')
                lines.append((0, 0, {
                    'student_id': student.id,
                    'recipient_id': r.id,
                    'recipient_email': r.email,
                    'has_portal': has_portal,
                    'note': note,
                }))
        return lines

    def _apply_one(self, partner):
        """Grant/revoke portal access for a single partner via the native portal wizard.

        Runs with sudo so tutors (who lack user-creation rights) can still grant
        access to their own students/families. Returns 'granted'/'revoked'/'skipped'.
        """
        wizard = self.env['portal.wizard'].with_context(active_ids=partner.ids).sudo().create({})
        wu = wizard.user_ids.filtered(lambda u: u.partner_id.id == partner.id)[:1]
        if not wu:
            return 'skipped'
        if self.mode == 'grant':
            if wu.is_portal or wu.is_internal:
                return 'skipped'
            wu.action_grant_access()
            return 'granted'
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
        granted = revoked = skipped = 0
        issues = []
        for student in self.student_ids:
            if not self._user_can_manage(student):
                issues.append(_("%s: not your student") % student.name)
                continue
            if student.is_adult and not student.email:
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
    note = fields.Char(string='Note')
