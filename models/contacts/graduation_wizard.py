# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class EmsGraduationWizard(models.TransientModel):
    _name = 'ems.graduation_wizard'
    _description = 'Graduation wizard (deferred exit mark)'

    line_ids = fields.One2many(
        'ems.graduation_wizard.line', 'wizard_id', string='Students')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_ids = self.env.context.get('active_ids') or []
        students = self.env['res.partner'].browse(active_ids).filtered(
            lambda p: p.contact_type == 'student')
        students = students.filtered(self._user_can_manage)
        res['line_ids'] = [(0, 0, self._line_vals(s)) for s in students]
        return res

    def _user_can_manage(self, student):
        """Admin/secretary manage any student; a tutor only its own students."""
        if self.env.user.has_group('ems.group_academic_admin') or self.env.user.has_group('ems.group_secretary'):
            return True
        return bool(student.tutor_id) and student.tutor_id.user_id.id == self.env.uid

    def _next_course(self):
        return self.env['ems.course'].search([('is_enrollment_default', '=', True)], limit=1)

    def _current_course(self):
        return self.env.company.current_course_id \
            or self.env['ems.course'].search([('is_current', '=', True)], limit=1)

    def _is_last_course(self, student):
        """Only students in the last course of their study can graduate (e.g. 2nd in
        CFGM/CFGS/Bachillerato, 4th in ESO). The last course is derived from the highest
        group course of the study."""
        last = student.study_id._ems_last_course()
        return bool(last) and bool(student.main_group_id) and student.main_group_id.course >= last

    def _line_vals(self, student):
        blocked = not self._is_last_course(student)
        if blocked:
            warning = _("Not in the last course of the study — cannot graduate")
        else:
            next_course = self._next_course()
            has_next = bool(next_course) and bool(self.env['sale.order'].search_count([
                ('partner_id', '=', student.id),
                ('ems_course_id', '=', next_course.id),
                ('state', '!=', 'cancel')]))
            # Not a contradiction: a graduate moving up to another study at the centre
            # is graduated AND placed by the transition, never converted nor archived.
            warning = _("Enrolled for the next course — will be graduated and placed, not archived") \
                if has_next else ''
        return {
            'student_id': student.id,
            # Shown for confirmation (D2): a student only ever has one study, through its
            # main group, so there is nothing to pick — but the operator has to see which
            # one the graduation is being recorded against.
            'study_id': student.study_id.id,
            'already_marked': student.exit_type == 'graduation',
            'blocked': blocked,
            'warning': warning,
        }

    def action_apply(self):
        """Deferred mark: writes has_graduated=True + exit_type/exit_course_id.
        Does NOT convert to alumni nor touch the portal (that runs at the
        transition wizard, at the end of the evaluations)."""
        self.ensure_one()
        course = self._current_course()
        done = 0
        skipped = 0
        for line in self.line_ids:
            student = line.student_id
            if not self._user_can_manage(student):
                continue
            # Only students in the last course of their study can graduate.
            if not self._is_last_course(student):
                skipped += 1
                continue
            student.write({
                'exit_type': 'graduation',
                'exit_course_id': course.id if course else False,
                'has_graduated': True,
            })
            done += 1
        message = _("%s student(s) marked as graduated.") % done
        if skipped:
            message += " " + _("%s skipped (not in the last course).") % skipped
        return self._notify(message)

    def action_unmark(self):
        """Reverse the deferred mark (exit_type/exit_course_id). has_graduated is a
        permanent mark and is intentionally NOT reset."""
        self.ensure_one()
        done = 0
        for line in self.line_ids:
            student = line.student_id
            if not self._user_can_manage(student):
                continue
            if student.exit_type == 'graduation':
                student.write({'exit_type': False, 'exit_course_id': False})
                done += 1
        return self._notify(_("%s graduation mark(s) removed.") % done)

    def _notify(self, message):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Graduation"),
                'message': message,
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }


class EmsGraduationWizardLine(models.TransientModel):
    _name = 'ems.graduation_wizard.line'
    _description = 'Graduation wizard line (preview)'

    wizard_id = fields.Many2one('ems.graduation_wizard', ondelete='cascade')
    student_id = fields.Many2one('res.partner', string='Student')
    study_id = fields.Many2one('ems.study', string='Study')
    already_marked = fields.Boolean(string='Already marked')
    blocked = fields.Boolean(string='Blocked')
    warning = fields.Char(string='Warning')


class EmsWithdrawalWizard(models.TransientModel):
    _name = 'ems.withdrawal_wizard'
    _description = 'Withdrawal wizard (immediate exit)'

    exit_date = fields.Date(string='Exit date', required=True,
                            default=fields.Date.context_today)
    exit_reason = fields.Text(string='Exit reason')
    line_ids = fields.One2many(
        'ems.withdrawal_wizard.line', 'wizard_id', string='Students')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if not self._is_secretary_or_admin():
            raise UserError(_("Only the secretary or an administrator can register withdrawals."))
        active_ids = self.env.context.get('active_ids') or []
        students = self.env['res.partner'].browse(active_ids).filtered(
            lambda p: p.contact_type == 'student')
        res['line_ids'] = [(0, 0, self._line_vals(s)) for s in students]
        return res

    def _is_secretary_or_admin(self):
        return self.env.user.has_group('ems.group_academic_admin') or self.env.user.has_group('ems.group_secretary')

    def _current_course(self):
        return self.env.company.current_course_id \
            or self.env['ems.course'].search([('is_current', '=', True)], limit=1)

    def _line_vals(self, student):
        pending = self.env['sale.order'].search_count([
            ('partner_id', '=', student.id),
            ('state', 'in', ['draft', 'sent'])])
        note = _("%s pending enrolment(s) will be cancelled") % pending if pending else ''
        return {'student_id': student.id, 'note': note}

    def action_apply(self):
        """Immediate effect: writes the exit metadata, converts to alumni/withdrawal,
        cleans active attendance templates, cancels pending enrolments and revokes
        the portal (with sibling check)."""
        self.ensure_one()
        if not self._is_secretary_or_admin():
            raise UserError(_("Only the secretary or an administrator can register withdrawals."))
        course = self._current_course()
        done = 0
        revoked = skipped = 0
        issues = []
        for line in self.line_ids:
            student = line.student_id
            if student.contact_type != 'student':
                continue
            student.write({
                'exit_type': 'withdrawal',
                'exit_course_id': course.id if course else False,
                'exit_date': self.exit_date,
                'exit_reason': self.exit_reason,
            })
            # Cancel pending (draft/sent) enrolments.
            orders = self.env['sale.order'].search([
                ('partner_id', '=', student.id),
                ('state', 'in', ['draft', 'sent'])])
            if orders:
                orders.sudo()._action_cancel()
            # Freeze the academic history NOW, while the student still has its
            # group: the transition wizard captures by main_group_id, so without
            # this a mid-course withdrawal would never get a year record. Sudo:
            # the generator reads grade/attendance models the secretary cannot.
            if course:
                self.env['ems.student.year_record'].sudo().generate_for_students(
                    student, course)
            # The history is frozen: delete the operational records (subject enrollments,
            # grade lines, attendance lines and templates, group delegate). Must run BEFORE
            # the conversion, which detaches the student from its group.
            student._ems_clear_operational_records()
            # Convert to alumni/withdrawal (clears group/level/study).
            student._ems_convert_to_ex_student()
            # Revoke portal access (student + families without other enrolled child).
            summary = student._ems_revoke_student_portal()
            revoked += len(summary['revoked'])
            skipped += len(summary['skipped'])
            issues += summary['issues']
            done += 1

        parts = [_("%s student(s) withdrawn") % done]
        if revoked:
            parts.append(_("%s portal access(es) revoked") % revoked)
        if skipped:
            parts.append(_("%s kept (sibling still enrolled)") % skipped)
        message = ", ".join(parts)
        if issues:
            message += "\n" + _("Issues:") + "\n- " + "\n- ".join(issues)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Withdrawal"),
                'message': message,
                'type': 'warning' if issues else 'success',
                'sticky': bool(issues),
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }


class EmsWithdrawalWizardLine(models.TransientModel):
    _name = 'ems.withdrawal_wizard.line'
    _description = 'Withdrawal wizard line (preview)'

    wizard_id = fields.Many2one('ems.withdrawal_wizard', ondelete='cascade')
    student_id = fields.Many2one('res.partner', string='Student')
    note = fields.Char(string='Note')
