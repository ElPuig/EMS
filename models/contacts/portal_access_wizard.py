# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools import email_normalize
from ..shared import base

_logger = logging.getLogger(__name__)


class EmsPortalAccessWizard(models.TransientModel):
    _name = 'ems.portal.access.wizard'
    _description = 'Bulk portal access for students and families'

    mode = fields.Selection([
        ('grant',  'Grant access'),
        ('revoke', 'Revoke access'),
        ('regenerate', 'Regenerate credentials (send a new password link)'),
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
        res['line_ids'] = self._build_lines(students, res.get('mode', 'grant'))
        return res

    @api.onchange('mode')
    def _onchange_mode(self):
        """Rebuild the preview with the recipients each action applies to ticked by default
        (granting: those without access; regenerating or revoking: those with it); the user
        can untick any of them before applying."""
        # In an onchange the related records are virtual (NewId); use ._origin so the
        # relation search against res.partner.relation.all hits the real DB records.
        self.line_ids = [(5, 0, 0)] + self._build_lines(self.student_ids._origin, self.mode)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _user_can_manage(self, student):
        """Admin/secretary manage any student; a tutor only its own students."""
        if self.env.user.has_group('ems.group_academic_admin') or self.env.user.has_group('ems.group_secretary'):
            return True
        return base.EmsBase.user_acts_as_tutor(self, student.tutor_id)

    def _build_lines(self, students, mode='grant'):
        """Build the One2many command list for the recipient preview; each line starts ticked
        when `mode` has something to do for it."""
        lines = []
        for student in students:
            # A minor student with no family on file still gets his own, view-only account:
            # the missing family is flagged on his line instead of replacing it.
            no_family = not student._ems_notification_recipients()
            for r in student._ems_portal_access_recipients():
                # A revoked access leaves an archived portal user behind: it is not access.
                user = r.with_context(active_test=False).user_ids.filtered('active')[:1]
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
                    'selected': has_portal != (mode == 'grant'),
                }))
        return lines

    def _apply_one(self, partner, students=None):
        """Grant/revoke/regenerate the portal access of a single partner via the native portal
        wizard (`students`: the students it is acted for, to explain a login clash).

        Runs with sudo so tutors (who lack user-creation rights) can still grant
        access to their own students/families.
        Returns 'granted'/'revoked'/'regenerated'/'skipped'.
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
            conflict = partner._ems_portal_login_conflict(students)
            if conflict:
                raise PortalLoginTaken(conflict)
            wu.invalidate_recordset(['email_state'])
            wu.action_grant_access()
            return 'granted'
        elif self.mode == 'regenerate':
            # A new link to set the password, for whoever forgot it (or never used the first one).
            if not wu.is_portal:
                return 'skipped'
            wu.action_invite_again()
            return 'regenerated'
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
        counts = dict.fromkeys(('granted', 'revoked', 'regenerated', 'skipped'), 0)
        issues = []
        conflicts = []
        for student in self.student_ids:
            if not self._user_can_manage(student):
                issues.append(_("%s: not your student") % student.name)
                continue
            if student.contact_type != 'applicant' and student.is_adult and not student.email:
                issues.append(_("%s: adult student without main email") % student.name)
                continue
            if not student._ems_notification_recipients():
                issues.append(_("%s: no family contact to manage") % student.name)
            for line in self.line_ids.filtered(lambda l: l.selected and l.student_id == student):
                r = line.recipient_id
                if not r.email:
                    issues.append(_("%(student)s: recipient %(name)s has no email") % {
                        'student': student.name, 'name': r.name})
                    continue
                try:
                    with self.env.cr.savepoint():
                        result = self._apply_one(r, student)
                    counts[result] += 1
                except PortalLoginTaken as e:
                    conflicts.append(e.conflict)
                except Exception as e:
                    msg = e.args[0] if getattr(e, 'args', None) else str(e)
                    issues.append('%s: %s' % (r.name, msg))

        # Build the result notification
        parts = []
        if counts['granted']:
            parts.append(_("%s access(es) granted") % counts['granted'])
        if counts['revoked']:
            parts.append(_("%s access(es) revoked") % counts['revoked'])
        if counts['regenerated']:
            parts.append(_("%s password link(s) sent") % counts['regenerated'])
        if counts['skipped']:
            parts.append(_("%s skipped (already in the desired state)") % counts['skipped'])
        summary = ", ".join(parts) or _("Nothing to do")
        if issues:
            summary += "\n" + _("Issues:") + "\n- " + "\n- ".join(issues)
        if conflicts:
            return self.env['ems.portal.access.result']._open(summary, conflicts)

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


class PortalLoginTaken(UserError):
    """The portal login a partner needs already belongs to another contact (issue #842).
    `conflict` is the dict built by res.partner._ems_portal_login_conflict."""

    def __init__(self, conflict):
        super().__init__(conflict['message'])
        self.conflict = conflict


class EmsPortalAccessResult(models.TransientModel):
    """Popup listing the contacts that could not get portal access because another contact
    already holds their login, with what to do about each (issue #842)."""
    _name = 'ems.portal.access.result'
    _description = 'Portal access result'

    summary = fields.Text(readonly=True)
    conflict_ids = fields.One2many('ems.portal.access.result.line', 'result_id', readonly=True)

    @api.model
    def _open(self, summary, conflicts):
        result = self.create({
            'summary': summary,
            'conflict_ids': [(0, 0, {key: conflict[key] for key in (
                'contact_id', 'login', 'holder_id', 'holder_type', 'holder_active', 'related',
                'advice')}) for conflict in conflicts],
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _("Portal access"),
            'res_model': self._name,
            'res_id': result.id,
            'view_mode': 'form',
            'target': 'new',
        }


class EmsPortalAccessResultLine(models.TransientModel):
    _name = 'ems.portal.access.result.line'
    _description = 'Portal access login clash'

    result_id = fields.Many2one('ems.portal.access.result', ondelete='cascade')
    contact_id = fields.Many2one('res.partner', string="Contact without access", readonly=True)
    login = fields.Char(string="Login in use", readonly=True)
    holder_id = fields.Many2one('res.partner', string="Contact holding it", readonly=True)
    holder_type = fields.Char(string="Contact type", readonly=True)
    holder_active = fields.Boolean(string="Active", readonly=True)
    related = fields.Boolean(string="Related to the student", readonly=True)
    advice = fields.Text(string="What to do", readonly=True)


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
    selected = fields.Boolean(string='Apply')


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
