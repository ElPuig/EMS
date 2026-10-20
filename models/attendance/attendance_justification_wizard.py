# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from ..shared import base


class EmsAttendanceJustificationWizard(models.TransientModel):
    """Justify the absences of several students, or of whole groups, at once (issue #656).

    Creates one ems.attendance_justification per student: everything else (overlaps, previsions,
    record rules, reports) relies on a justification covering one student.
    """
    _name = 'ems.attendance_justification_wizard'
    _description = 'Justify the absences of several students or groups'

    mode = fields.Selection([
        ('students', 'Students'),
        ('groups', 'Groups'),
    ], string='Mode', default='students', required=True)
    start_date = fields.Datetime(string='Start date', required=True)
    end_date = fields.Datetime(string='End date', required=True)
    teacher_id = fields.Many2one(
        'hr.employee', string='Teacher', required=True,
        domain="[('employee_type', '=', 'teacher')]",
        default=lambda self: self.env['ems.attendance_justification']._default_teacher_id())
    student_ids = fields.Many2many('res.partner', string='Students')
    group_ids = fields.Many2many('ems.group', string='Groups')
    notes = fields.Text(string='Notes')
    attachment_ids = fields.Many2many(
        'ir.attachment', relation='ems_attendance_justification_wizard_attachment_rel',
        column1='wizard_id', column2='attachment_id', string='Attached files')

    # The pickers' domains (the view's domain="student_domain"), as text: for an administrator the
    # allowed students are the whole centre, too many ids to send to the browser.
    student_domain = fields.Char(compute='_compute_domains')
    group_domain = fields.Char(compute='_compute_domains')
    target_student_ids = fields.Many2many(
        'res.partner', relation='ems_attendance_justification_wizard_target_rel',
        column1='wizard_id', column2='partner_id', string='Students to justify',
        compute='_compute_target_student_ids')
    overlap_student_ids = fields.Many2many(
        'res.partner', relation='ems_attendance_justification_wizard_overlap_rel',
        column1='wizard_id', column2='partner_id', string='Already justified',
        compute='_compute_overlap_student_ids')
    user_is_admin = fields.Boolean(default=lambda self: base.EmsBase.get_user_is_admin(self), store=False)

    @api.depends('teacher_id')
    def _compute_domains(self):
        # The students (and main groups) of every group the justifying teacher acts as tutor of:
        # their own, or those of the tutors below them (hr.employee.tutor_scope_user_ids, issue
        # #483). The same rule as ems.attendance_justification.allowed_student_ids.
        is_admin = base.EmsBase.get_user_is_admin(self)
        for wizard in self:
            student_domain = [('contact_type', '=', 'student')]
            group_domain = [('group_type', '=', 'main')]
            if not is_admin:
                user_id = wizard.teacher_id.user_id.id
                student_domain.append(('main_group_id.tutor_id.tutor_scope_user_ids', '=', user_id))
                group_domain.append(('tutor_id.tutor_scope_user_ids', '=', user_id))
            wizard.student_domain = str(student_domain)
            wizard.group_domain = str(group_domain)

    @api.depends('mode', 'student_ids', 'group_ids')
    def _compute_target_student_ids(self):
        for wizard in self:
            wizard.target_student_ids = wizard._resolve_students()

    @api.depends('target_student_ids', 'start_date', 'end_date')
    def _compute_overlap_student_ids(self):
        for wizard in self:
            wizard.overlap_student_ids = wizard._overlapping_students(wizard.target_student_ids._origin)

    @api.model
    def default_get(self, fields_list):
        if not (base.EmsBase.get_user_is_admin(self) or base.EmsBase.get_user_is_tutor(self)):
            raise UserError(_("Only tutors can justify student's attendances."))
        return super().default_get(fields_list)

    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for wizard in self:
            if wizard.start_date >= wizard.end_date:
                raise ValidationError(_("The completion date must be later than the start date."))

    def _resolve_students(self):
        """The students the selection stands for: the ones picked, or every active student whose
        main group is one of the groups picked."""
        self.ensure_one()
        if self.mode == 'students':
            return self.student_ids._origin
        if not self.group_ids:
            return self.env['res.partner']
        return self.env['res.partner'].search([
            ('contact_type', '=', 'student'), ('main_group_id', 'in', self.group_ids._origin.ids)])

    def _overlapping_students(self, students):
        """The students already holding a justification that overlaps the period: skipped, as
        ems.attendance_justification._check_time_overlap would refuse them. sudo: an overlap the
        user cannot read (another tutor's) still counts."""
        self.ensure_one()
        if not (students and self.start_date and self.end_date):
            return self.env['res.partner']
        return self.env['ems.attendance_justification'].sudo().search([
            ('student_id', 'in', students.ids),
            ('start_date', '<', self.end_date),
            ('end_date', '>', self.start_date),
        ]).student_id.sudo(False)

    def action_justify(self):
        self.ensure_one()
        students = self._resolve_students()
        if not students:
            raise UserError(_("Choose at least one student or group."))
        Justification = self.env['ems.attendance_justification']
        if not base.EmsBase.get_user_is_admin(self):
            refused = students.filtered(lambda student: not base.EmsBase.user_acts_as_tutor(self, student.tutor_id))
            if refused:
                raise UserError(_(
                    "Only the student's tutor can justify its attendances: %(students)s",
                    students=", ".join(refused.mapped('name'))))

        skipped = self._overlapping_students(students)
        students -= skipped
        lines = Justification._justifiable_lines(students, self.start_date, self.end_date)
        attachments = self.attachment_ids
        justifications = Justification.create([{
            'teacher_id': self.teacher_id.id,
            'student_id': student.id,
            'start_date': self.start_date,
            'end_date': self.end_date,
            'notes': self.notes,
            'attendance_session_line_ids': [(6, 0, lines[student.id].ids)],
            # Every justification its own copy (the filestore keeps the content once): a file
            # follows the access rights of the one record it is tied to (ems.attachment_mixin).
            'attachment_ids': [(6, 0, [attachment.copy({
                'res_model': Justification._name, 'res_id': 0}).id for attachment in attachments])],
        } for student in students])
        attachments.unlink()

        message = _("%s student(s) justified.", len(justifications))
        if skipped:
            message += "\n" + _(
                "Skipped, they already have a justification overlapping this period: %s",
                ", ".join(skipped.mapped('name')))
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Justify absences"),
                'message': message,
                'type': 'warning' if skipped else 'success',
                'sticky': bool(skipped),
                'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
            },
        }
