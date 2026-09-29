# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class EmsContactDataRequestSendWizard(models.TransientModel):
    """Ask students and families to review their contact data from the portal (issue #507).

    Picks the students the same way the authorization send assistant does (ems.student.scope.mixin):
    by hand, or by groups, studies and levels, and a tutor only their own.
    """
    _name = 'ems.contact.data.request.send.wizard'
    _inherit = 'ems.student.scope.mixin'
    _description = 'Request contact data update'

    allowed_group_ids = fields.Many2many(
        'ems.group', relation='ems_cdr_send_allowed_group_rel',
        column1='wizard_id', column2='group_id')
    allowed_study_ids = fields.Many2many(
        'ems.study', relation='ems_cdr_send_allowed_study_rel',
        column1='wizard_id', column2='study_id')
    allowed_level_ids = fields.Many2many(
        'ems.level', relation='ems_cdr_send_allowed_level_rel',
        column1='wizard_id', column2='level_id')
    only_incomplete = fields.Boolean(
        string='Only students with incomplete data', default=True,
        help="Skip the students whose contact data already has everything required.")
    grant_portal = fields.Boolean(
        string='Grant portal access to whoever lacks it', default=True,
        help="The request is answered from the portal: recipients with an email but no portal "
             "access get their portal invitation too.")
    line_ids = fields.One2many(
        'ems.contact.data.request.send.wizard.line', 'wizard_id', string='Recipients')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if {'allowed_group_ids', 'allowed_study_ids', 'allowed_level_ids'} & set(fields_list):
            res.update({
                'allowed_level_ids': [(6, 0, self.env['ems.level'].search([]).ids)],
                'allowed_study_ids': [(6, 0, self.env['ems.study'].search([]).ids)],
                'allowed_group_ids': [(6, 0, self._scope_allowed_groups().ids)],
            })
        students = self._scope_students_from_context()
        if students:
            res['target'] = 'students'
            res['student_ids'] = [(6, 0, students.ids)]
        return res

    @api.onchange('target', 'student_ids', 'group_ids', 'ems_study_ids', 'ems_level_ids',
                  'course_id', 'only_incomplete')
    def _onchange_selection(self):
        students = self._resolve_students()
        lines = self._build_lines(students)
        lines += [(0, 0, {'student_id': student.id, 'note': _("Not one of your students")})
                  for student in self._scope_foreign_students(students)]
        self.line_ids = [(5, 0, 0)] + lines

    def _existing_requests(self, students):
        requests = self.env['ems.contact.data.request'].search([
            ('course_id', '=', self.course_id._origin.id),
            ('student_id', 'in', students.ids),
        ])
        return {request.student_id.id: request for request in requests}

    def _build_lines(self, students):
        existing = self._existing_requests(students)
        lines = []
        for student in students:
            missing = student._ems_contact_data_missing()
            recipients = student._ems_notification_recipients()
            notes = []
            request = existing.get(student.id)
            if self.only_incomplete and not missing:
                notes.append(_("Data complete"))
            elif request and request.state in ('pending', 'submitted'):
                notes.append(_("Already requested"))
            if not recipients.filtered('email'):
                notes.append(_("Nobody reachable by email: contact them by phone"))
            lines.append((0, 0, {
                'student_id': student.id,
                'missing': '\n'.join(missing),
                'recipient_emails': ', '.join(recipients.filtered('email').mapped('email')),
                'note': ' - '.join(notes),
            }))
        return lines

    def action_apply(self):
        self.ensure_one()
        Request = self.env['ems.contact.data.request']
        if not Request._ems_user_can_request():
            raise UserError(_(
                "Only the secretary's office, the academic administration, the head of studies "
                "and tutors can request contact data."))
        if self.target == 'scope' and not (self.group_ids or self.ems_study_ids or self.ems_level_ids):
            raise UserError(_("Choose at least one group, study or level."))
        students = self._resolve_students()
        if not students:
            raise UserError(_("No student matches the selection."))

        existing = self._existing_requests(students)
        sent = complete = already = mailed = granted = 0
        unreachable = []
        for student in students:
            if self.only_incomplete and not student._ems_contact_data_missing():
                complete += 1
                continue
            request = existing.get(student.id)
            if request and request.state in ('pending', 'submitted'):
                already += 1
                continue
            request = request or Request.create({'student_id': student.id, 'course_id': self.course_id.id})
            request._ems_mark_sent()
            sent += 1
            if self.grant_portal:
                granted += self._grant_portal(student)
            queued, issue = request._ems_send_request_email()
            mailed += queued
            if issue:
                unreachable.append(issue)

        parts = [_("%s request(s) sent", sent)]
        if mailed:
            parts.append(_("%s email(s) queued", mailed))
        if granted:
            parts.append(_("%s portal invitation(s) sent", granted))
        if complete:
            parts.append(_("%s student(s) with complete data skipped", complete))
        if already:
            parts.append(_("%s already requested", already))
        message = ", ".join(parts)
        if unreachable:
            message += "\n" + _("Nobody reachable by email - contact them by phone:") + "\n- " + "\n- ".join(unreachable)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Request contact data"),
                'message': message,
                'type': 'warning' if unreachable else 'success',
                'sticky': bool(unreachable),
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }

    def _grant_portal(self, student):
        """Grant portal access to the recipients that have an email but no access yet, through the
        portal access assistant's own path (sudo, so a tutor can too). Returns how many."""
        access = self.env['ems.portal.access.wizard'].sudo().new({'mode': 'grant'})
        granted = 0
        for recipient in student._ems_notification_recipients().filtered('email'):
            if recipient._has_active_portal_user():
                continue
            try:
                with self.env.cr.savepoint():
                    granted += access._apply_one(recipient) == 'granted'
            except Exception:
                # A login already taken by another user, for instance: the request still goes
                # out by email, and the portal access assistant reports it in detail.
                continue
        return granted


class EmsContactDataRequestSendWizardLine(models.TransientModel):
    _name = 'ems.contact.data.request.send.wizard.line'
    _description = 'Contact data request recipient (preview)'

    wizard_id = fields.Many2one('ems.contact.data.request.send.wizard', ondelete='cascade')
    student_id = fields.Many2one('res.partner', string='Student')
    missing = fields.Text(string='Missing')
    recipient_emails = fields.Char(string='Notified at')
    note = fields.Char(string='Note')
