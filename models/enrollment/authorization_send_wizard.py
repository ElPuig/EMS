# -*- coding: utf-8 -*-
import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class EmsAuthorizationSendWizard(models.TransientModel):
    _name = 'ems.authorization.send.wizard'
    _inherit = 'ems.student.scope.mixin'
    _description = 'Send authorizations to students during the course'

    template_ids = fields.Many2many(
        'ems.authorization.template',
        string='Authorizations to send',
        domain=[('sendable_during_course', '=', True)],
        help="Only the authorization forms marked as 'Can be sent during the course'.",
    )
    # What the sender may pick stays inside the scope of the forms being sent: a form limited
    # to vocational training never offers an ESO group. Plain fields filled by default_get() and
    # kept up to date by _onchange_selection(), not computes: the web client gets a new record's
    # values from the onchange's default phase, which left these computes out entirely, so the
    # group picker came up empty until the chosen forms changed - even with a form preloaded
    # from its own "Send to Students" button. They only drive the pickers; which students
    # receive which form is decided per student on the server (_templates_for).
    allowed_group_ids = fields.Many2many(
        'ems.group', relation='ems_auth_send_allowed_group_rel',
        column1='wizard_id', column2='group_id')
    allowed_study_ids = fields.Many2many(
        'ems.study', relation='ems_auth_send_allowed_study_rel',
        column1='wizard_id', column2='study_id')
    allowed_level_ids = fields.Many2many(
        'ems.level', relation='ems_auth_send_allowed_level_rel',
        column1='wizard_id', column2='level_id')
    notify = fields.Boolean(
        string='Send notification email', default=True,
        help="One email per student listing every authorization sent in this batch. A "
             "minor's family is emailed instead of the student.",
    )
    line_ids = fields.One2many(
        'ems.authorization.send.wizard.line', 'wizard_id', string='Recipients',
    )

    @api.model
    def _allowed_scope(self, templates):
        """(levels, studies, groups) the sender may pick for `templates`: the ones inside the
        scope of at least one of them, through the same predicates the enrollment route uses,
        and for a tutor only their own groups. No form chosen yet restricts nothing but that."""
        levels = self.env['ems.level'].search([])
        studies = self.env['ems.study'].search([])
        groups = self._scope_allowed_groups()
        if not templates:
            return levels, studies, groups
        return (
            levels.filtered(lambda level: any(template._matches_level(level) for template in templates)),
            studies.filtered(lambda study: any(template._matches_scope(study.level_id, study)
                                               for template in templates)),
            groups.filtered(lambda group: any(template._matches_scope(group.level_id, group.study_id)
                                              for template in templates)),
        )

    @api.model
    def _templates_from_context(self):
        """The forms preloaded through default_template_ids, e.g. from a form's own button."""
        ids = []
        for command in self.env.context.get('default_template_ids') or []:
            if isinstance(command, (list, tuple)) and command and command[0] == 6:
                ids.extend(command[2])
            elif isinstance(command, int):
                ids.append(command)
        return self.env['ems.authorization.template'].browse(ids).exists()

    @api.model
    def default_get(self, fields_list):
        """Preload the students selected in a list (see _scope_students_from_context)."""
        res = super().default_get(fields_list)
        if {'allowed_group_ids', 'allowed_study_ids', 'allowed_level_ids'} & set(fields_list):
            levels, studies, groups = self._allowed_scope(self._templates_from_context())
            res.update({
                'allowed_level_ids': [(6, 0, levels.ids)],
                'allowed_study_ids': [(6, 0, studies.ids)],
                'allowed_group_ids': [(6, 0, groups.ids)],
            })
        students = self._scope_students_from_context()
        if students:
            res.setdefault('target', 'students')
            res['student_ids'] = [(6, 0, students.ids)]
        return res

    @api.onchange('target', 'student_ids', 'group_ids', 'ems_study_ids', 'ems_level_ids',
                  'template_ids', 'course_id')
    def _onchange_selection(self):
        """Drop scope choices the chosen forms no longer allow, then rebuild the preview.

        In an onchange every relational value is a virtual record wrapping the real one
        (NewId origin=34), and it never compares equal to a persisted record - so ._origin
        goes on the RELATED records wherever they are compared or searched with, never on the
        wizard itself, whose own _origin is an empty recordset while unsaved.
        """
        levels, studies, groups = self._allowed_scope(self.template_ids._origin)
        self.allowed_level_ids = levels
        self.allowed_study_ids = studies
        self.allowed_group_ids = groups
        for field_name, allowed in (('group_ids', groups), ('ems_study_ids', studies),
                                    ('ems_level_ids', levels)):
            chosen = self[field_name]._origin
            kept = chosen & allowed
            if kept != chosen:
                self[field_name] = [(6, 0, kept.ids)]
        students = self._resolve_students()
        lines = self._build_lines(students)
        lines += [(0, 0, {'student_id': student.id, 'note': _("Not one of your students")})
                  for student in self._scope_foreign_students(students)]
        self.line_ids = [(5, 0, 0)] + lines

    # ------------------------------------------------------------------
    # Resolving students
    # ------------------------------------------------------------------
    def _check_rights(self):
        """Secretary, academic admin and head of studies send authorizations to anyone; a
        tutor to their own students (enforced in _resolve_students). A plain teacher may read
        them but never create them - the record rules say the same thing, this is the early,
        legible error."""
        if not (self._scope_sees_every_student() or self.env.user.has_group('ems.group_tutor')):
            raise UserError(_(
                "Only the secretary's office, the academic administration, the head of studies "
                "and tutors can send authorizations."))

    # ------------------------------------------------------------------
    # Preview
    # ------------------------------------------------------------------
    def _existing_pairs(self, students):
        """(student, template) pairs already on file for this academic year, by either route.

        One search covers both because course_id is stored on every authorization, whether it
        came from an enrollment or was sent standalone. A student is never asked the same
        thing twice, and an already-answered authorization is never reset.
        """
        existing = self.env['ems.authorization'].search([
            ('course_id', '=', self.course_id._origin.id),
            ('template_id', 'in', self.template_ids._origin.ids),
            ('partner_id', 'in', students.ids),
        ])
        return {(auth.partner_id.id, auth.template_id.id) for auth in existing}

    def _templates_for(self, student, existing_pairs):
        """(in_scope, to_send) for this student.

        Each form only reaches the students its own level/study scope covers, however they were
        picked - a student added by hand outside it is reported, not sent to - and a form already
        on file for the student is never sent again.
        """
        level, study = student._ems_level_study_in_force()
        in_scope = self.template_ids._origin.filtered(
            lambda template: template._matches_scope(level, study))
        to_send = in_scope.filtered(
            lambda template: (student.id, template.id) not in existing_pairs)
        return in_scope, to_send

    def _build_lines(self, students):
        """One line per student - the preview answers "who gets mailed", which a line per
        (student x template) would bury."""
        if not students or not self.template_ids:
            return []
        existing_pairs = self._existing_pairs(students)
        lines = []
        for student in students:
            in_scope, to_send = self._templates_for(student, existing_pairs)
            recipients = student._ems_notification_recipients()
            notes = []
            if not in_scope:
                notes.append(_("Outside the scope of these authorizations"))
            elif not to_send:
                notes.append(_("Already requested"))
            if not recipients:
                notes.append(_("No family contact found"))
            elif not any(recipients.mapped('email')):
                notes.append(_("Recipient without email"))
            lines.append((0, 0, {
                'student_id': student.id,
                'template_ids': [(6, 0, to_send.ids)],
                'recipient_emails': ', '.join(recipients.filtered('email').mapped('email')),
                'note': ' - '.join(notes),
            }))
        return lines

    # ------------------------------------------------------------------
    # Main action
    # ------------------------------------------------------------------
    def action_apply(self):
        self.ensure_one()
        self._check_rights()
        if not self.template_ids:
            raise UserError(_("Select at least one authorization to send."))
        if self.target == 'scope' and not (self.group_ids or self.ems_study_ids or self.ems_level_ids):
            raise UserError(_(
                "Choose at least one group, study or level to send the authorizations to."))
        students = self._resolve_students()
        if not students:
            raise UserError(_("No student matches the selection."))

        existing_pairs = self._existing_pairs(students)
        created = skipped = mailed = out_of_scope = 0
        issues = []
        for student in students:
            in_scope, to_send = self._templates_for(student, existing_pairs)
            if not in_scope:
                out_of_scope += 1
                continue
            skipped += len(in_scope) - len(to_send)
            if not to_send:
                continue
            authorizations = self.env['ems.authorization'].create([{
                'partner_id': student.id,
                'course_id': self.course_id.id,
                'template_id': template.id,
                'status': 'pending',
            } for template in to_send])
            created += len(authorizations)
            if not self.notify:
                continue
            sent, issue = self._send_notification(student, authorizations)
            mailed += sent
            if issue:
                issues.append(issue)

        parts = []
        if created:
            parts.append(_("%s authorization(s) sent") % created)
        if mailed:
            parts.append(_("%s email(s) queued") % mailed)
        if skipped:
            parts.append(_("%s skipped (already requested)") % skipped)
        if out_of_scope:
            parts.append(_("%s student(s) outside the scope of these authorizations") % out_of_scope)
        summary = ", ".join(parts) or _("Nothing to do")
        if issues:
            summary += "\n" + _("Issues:") + "\n- " + "\n- ".join(issues)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Send authorizations"),
                'message': summary,
                'type': 'warning' if issues else 'success',
                'sticky': bool(issues),
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }

    def _send_notification(self, student, authorizations):
        """One email per student listing every authorization just sent to them.

        Not one per authorization: a Departament d'Educació batch is routinely three or four
        forms at once, and that is how a family starts ignoring the channel. The recipient is
        the student himself when adult and his family when he is a minor
        (res.partner._ems_notification_recipients(), shared with the portal access wizard).

        Returns (emails queued, issue message or None).
        """
        template = self.env.ref('ems.email_template_authorization_send', raise_if_not_found=False)
        if not template:
            return 0, None
        recipients = student._ems_notification_recipients()
        if not recipients:
            return 0, _("%s: no family contact to notify") % student.name
        addressable = recipients.filtered('email')
        if not addressable:
            return 0, _("%(student)s: %(names)s has no email") % {
                'student': student.name, 'names': ', '.join(recipients.mapped('name'))}
        for recipient in addressable:
            # force_send=False: a whole-level batch must not be sent inline, it goes out
            # through the regular mail queue.
            template.with_context(
                lang=recipient.lang or student.lang,
                authorization_names=authorizations.mapped('template_id.name'),
                course_name=self.course_id.name,
                student_name=student.name,
            ).sudo().send_mail(
                student.id, force_send=False,
                email_values={'email_to': recipient.email},
            )
        return len(addressable), None


class EmsAuthorizationSendWizardLine(models.TransientModel):
    _name = 'ems.authorization.send.wizard.line'
    _description = 'Authorization recipient (preview)'

    wizard_id = fields.Many2one('ems.authorization.send.wizard', ondelete='cascade')
    student_id = fields.Many2one('res.partner', string='Student')
    # Explicit relation table: the auto-generated name
    # (ems_authorization_send_wizard_line_ems_authorization_template_rel) is over
    # PostgreSQL's 63-character identifier limit and Odoo refuses to build the registry.
    template_ids = fields.Many2many(
        'ems.authorization.template', string='Authorizations',
        relation='ems_auth_send_line_template_rel',
        column1='line_id', column2='template_id',
    )
    recipient_emails = fields.Char(string='Notified at')
    note = fields.Char(string='Note')
