# -*- coding: utf-8 -*-
import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class EmsAuthorizationSendWizard(models.TransientModel):
    _name = 'ems.authorization.send.wizard'
    _description = 'Send authorizations to students during the course'

    template_ids = fields.Many2many(
        'ems.authorization.template',
        string='Authorizations to send',
        help="Templates of either kind can be sent: a template meant for the enrollment "
             "process is still the right thing to send by hand to a student who enrolled "
             "before it existed.",
    )
    course_id = fields.Many2one(
        'ems.course',
        string='Academic Year',
        required=True,
        default=lambda self: self.env['res.partner']._ems_running_course(),
    )
    target = fields.Selection([
        ('students', 'Selected students'),
        ('scope', 'Groups / studies / levels'),
        ('template_scope', "Each template's own scope"),
    ], string='Send to', default='students', required=True)
    student_ids = fields.Many2many(
        'res.partner', string='Students',
        domain=[('contact_type', 'in', ('student', 'applicant'))],
    )
    group_ids = fields.Many2many('ems.group', string='Groups', domain=[('group_type', '=', 'main')])
    ems_study_ids = fields.Many2many('ems.study', string='Studies')
    ems_level_ids = fields.Many2many('ems.level', string='Levels')
    notify = fields.Boolean(
        string='Send notification email', default=True,
        help="One email per student listing every authorization sent in this batch. A "
             "minor's family is emailed instead of the student.",
    )
    line_ids = fields.One2many(
        'ems.authorization.send.wizard.line', 'wizard_id', string='Recipients',
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_ids = self.env.context.get('active_ids') or []
        students = self.env['res.partner'].browse(active_ids).filtered(
            lambda p: p.contact_type in ('student', 'applicant'))
        if students:
            res.setdefault('target', 'students')
            res['student_ids'] = [(6, 0, students.ids)]
        return res

    @api.onchange('target', 'student_ids', 'group_ids', 'ems_study_ids', 'ems_level_ids',
                  'template_ids', 'course_id')
    def _onchange_selection(self):
        """Rebuild the recipient preview.

        ._origin belongs on the RELATED records (see _resolve_students), never on the wizard
        itself: an unsaved wizard's _origin is an empty recordset, and building the lines off
        that reads empty template_ids and silently produces no preview at all.
        """
        self.line_ids = [(5, 0, 0)] + self._build_lines(self._resolve_students())

    # ------------------------------------------------------------------
    # Resolving students
    # ------------------------------------------------------------------
    def _check_rights(self):
        """Secretary, academic admin and head of studies send authorizations. A plain
        teacher (or tutor) may read them but never create them - the record rules say the
        same thing, this is the early, legible error."""
        user = self.env.user
        if not (user.has_group('ems.group_academic_admin')
                or user.has_group('ems.group_secretary')
                or user.has_group('ems.group_head_of_studies')):
            raise UserError(_(
                "Only the secretary's office, the academic administration and the head of "
                "studies can send authorizations."))

    def _enrolled_students(self):
        """Students holding a live (not cancelled) enrollment for the selected academic year.

        Every scope target starts here rather than from ems.group's own student list: a group
        record still holds students who have since left, and asking an ex-student to sign
        anything is exactly the mistake this avoids.
        """
        enrollments = self.env['sale.order'].search([
            ('ems_course_id', '=', self.course_id.id),
            ('state', '!=', 'cancel'),
        ])
        return enrollments.mapped('partner_id')

    def _students_from_scope(self):
        candidates = self._enrolled_students()
        if not (self.group_ids or self.ems_study_ids or self.ems_level_ids):
            return candidates
        return candidates.filtered(lambda student: (
            (self.group_ids and student.main_group_id in self.group_ids)
            or (self.ems_study_ids and student._ems_level_study_in_force()[1] in self.ems_study_ids)
            or (self.ems_level_ids and student._ems_level_study_in_force()[0] in self.ems_level_ids)
        ))

    def _students_for_template(self, template):
        """Enrolled students whose own level/study the template's scope matches - the same
        AND-of-scopes predicate the enrollment route uses, read from the student side."""
        return self._enrolled_students().filtered(
            lambda student: template._matches_scope(*student._ems_level_study_in_force()))

    def _resolve_students(self):
        """The students this wizard would act on, deduplicated."""
        self.ensure_one()
        if self.target == 'students':
            # ._origin: in an onchange these are virtual records, and everything downstream
            # (searches, _ems_level_study_in_force) needs the persisted ones.
            return self.student_ids._origin
        if self.target == 'scope':
            return self._students_from_scope()
        students = self.env['res.partner']
        for template in self.template_ids:
            students |= self._students_for_template(template)
        return students

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
            ('course_id', '=', self.course_id.id),
            ('template_id', 'in', self.template_ids.ids),
            ('partner_id', 'in', students.ids),
        ])
        return {(auth.partner_id.id, auth.template_id.id) for auth in existing}

    def _templates_for(self, student, existing_pairs):
        """Templates still to send to this student."""
        if self.target == 'template_scope':
            candidates = self.template_ids.filtered(
                lambda t: t._matches_scope(*student._ems_level_study_in_force()))
        else:
            candidates = self.template_ids
        return candidates.filtered(lambda t: (student.id, t.id) not in existing_pairs)

    def _build_lines(self, students):
        """One line per student - the preview answers "who gets mailed", which a line per
        (student x template) would bury."""
        if not students or not self.template_ids:
            return []
        existing_pairs = self._existing_pairs(students)
        lines = []
        for student in students:
            templates = self._templates_for(student, existing_pairs)
            recipients = student._ems_notification_recipients()
            notes = []
            if not templates:
                notes.append(_("Already requested"))
            if not recipients:
                notes.append(_("No family contact found"))
            elif not any(recipients.mapped('email')):
                notes.append(_("Recipient without email"))
            lines.append((0, 0, {
                'student_id': student.id,
                'template_ids': [(6, 0, templates.ids)],
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
        students = self._resolve_students()
        if not students:
            raise UserError(_("No student matches the selection."))

        existing_pairs = self._existing_pairs(students)
        created = skipped = mailed = 0
        issues = []
        for student in students:
            templates = self._templates_for(student, existing_pairs)
            skipped += len(self.template_ids) - len(templates)
            if not templates:
                continue
            authorizations = self.env['ems.authorization'].create([{
                'partner_id': student.id,
                'course_id': self.course_id.id,
                'template_id': template.id,
                'status': 'pending',
            } for template in templates])
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
