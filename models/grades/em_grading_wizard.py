# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

# Students do not finish their work placement (EM) at the same time, so the EM grade is
# closed per student, never as a group act. The wizard shows the selected group as a matrix
# (em_matrix widget, same shape as the group/subject evaluation screen): one row per student
# with a single EM grade — the normal case, the same grade for every module of that student —
# plus a "grade per module" switch that turns on one editable cell per module of the group
# carrying a placement weight. Only what the user fills in is written. Two destinations: the
# live ems.grade_subject_line of the current course (the grades model recomputes the final on
# its own) and the archived ems.student.year_record.subject of previous courses whose final is
# still pending (completed with the frozen weights).


class EmsEmGradingWizard(models.TransientModel):
    _name = 'ems.em_grading_wizard'
    _description = 'Work placement (EM) grading wizard: EM grade of a student, per module.'

    study_id = fields.Many2one(string="Study", comodel_name='ems.study')
    group_id = fields.Many2one(string="Group", comodel_name='ems.group')
    # Dynamic domain of group_id (the view points its domain at this field): a tutor may
    # only pick the groups it tutors. A default plus onchange, not a compute: the wizard is
    # always a new record, and a computed field with no field dependencies is not sent to
    # the client on a new record (the picker would receive a false domain).
    group_domain = fields.Char(string="Group domain",
                               default=lambda self: str(self._tutor_scope_domain()))
    # The matrix rows; line_ids holds their cells (one per module of the group).
    student_line_ids = fields.One2many(string="Students",
                                       comodel_name='ems.em_grading_wizard.student',
                                       inverse_name='wizard_id')
    line_ids = fields.One2many(string="Module grades",
                               comodel_name='ems.em_grading_wizard.line',
                               inverse_name='wizard_id')

    @api.depends('group_id')
    def _compute_display_name(self):
        # The wizard is a full page, so its name is what the breadcrumb shows: without this
        # the user reads the technical "ems.em_grading_wizard,278" after applying.
        for wizard in self:
            wizard.display_name = wizard.group_id.name or _("Work placement evaluation (EM)")

    @api.model
    def _tutor_scope_domain(self):
        if self._is_manager():
            return []
        return [('tutor_id.user_id', '=', self.env.uid)]

    def _is_manager(self):
        return self.env.user.has_group('ems.group_academic_admin') \
            or self.env.user.has_group('ems.group_secretary')

    def _user_can_manage_group(self, group):
        """Admin/secretary grade any group; a tutor only the group it tutors. The view
        already restricts the picker (group_domain); this is the defensive check."""
        if self._is_manager():
            return True
        return bool(group.tutor_id) and group.tutor_id.user_id.id == self.env.uid

    @api.onchange('study_id')
    def _onchange_study_id(self):
        for wizard in self:
            domain = wizard._tutor_scope_domain()
            if wizard.study_id:
                domain.append(('study_id', '=', wizard.study_id.id))
                if wizard.group_id.study_id != wizard.study_id:
                    wizard.group_id = False
            wizard.group_domain = str(domain)

    @api.onchange('group_id')
    def _onchange_group_id(self):
        for wizard in self:
            wizard._fill_lines()

    def _fill_lines(self):
        """(Re)build both grids from the group. Sudo: the grids must show the whole picture
        (grades and history the user may not read directly); who may grade which group is
        enforced by _user_can_manage_group."""
        self.ensure_one()
        module_vals = self._module_vals()
        student_vals = []
        for student in self.env['res.partner'].browse(
                dict.fromkeys(vals['student_id'] for vals in module_vals)):
            student_vals.append({
                'student_id': student.id,
                'student_name': student.display_name,
                'student_firstname': student.firstname,
                'student_lastname': student.lastname,
                'module_count': len([vals for vals in module_vals
                                     if vals['student_id'] == student.id]),
            })
        self.student_line_ids = [(5, 0, 0)] + [(0, 0, vals) for vals in student_vals]
        self.line_ids = [(5, 0, 0)] + [(0, 0, vals) for vals in module_vals]

    def _module_vals(self):
        """One dict per student of the group and module with an external weight."""
        self.ensure_one()
        if not self.group_id:
            return []
        vals_list = []
        students = self._group_students()
        for student in students.sorted(lambda student: student.display_name or ''):
            live_subjects = self.env['ems.subject']
            for subject_line in self._live_subject_lines(student):
                live_subjects |= subject_line.subject_id
                vals_list.append({
                    'student_id': student.id,
                    'student_name': student.display_name,
                    'subject_id': subject_line.subject_id.id,
                    'subject_name': subject_line.subject_id.name,
                    'subject_acronym': subject_line.subject_id.acronym,
                    'course_name': self.env.company.current_course_id.name,
                    'source': 'live',
                    'subject_line_id': subject_line.id,
                    'internal_grade': subject_line.internal_score,
                    'external_weight': subject_line.external_ponderation,
                    'already_scored': subject_line.external_is_scored,
                    'score': subject_line.external_score,
                })
            for subject_record in self._pending_subject_records(student):
                if subject_record.subject_id in live_subjects:
                    # Re-evaluated this course: the live line is the one that carries the EM.
                    continue
                vals_list.append(self._history_module_vals(subject_record))
        # Pending finals snapshotted to this group whose student is no longer enrolled in it
        # (the year record keeps the group of that year, so they stay reachable from here).
        # Still students only: an ex-student (withdrawal / alumni) has left the centre and
        # its history is closed — its pending finals are not graded any more.
        for subject_record in self.env['ems.student.year_record.subject'].sudo().search([
                ('final_pending', '=', True),
                ('record_id.group_id', '=', self.group_id.id),
                ('record_id.student_id.contact_type', '=', 'student'),
                ('record_id.student_id', 'not in', students.ids)]):
            vals_list.append(self._history_module_vals(subject_record))
        return vals_list

    def _history_module_vals(self, subject_record):
        student = subject_record.record_id.student_id
        return {
            'student_id': student.id,
            'student_name': student.display_name,
            'subject_id': subject_record.subject_id.id,
            'subject_name': subject_record.subject_id.name or subject_record.subject_name,
            'subject_acronym': subject_record.subject_id.acronym,
            'course_name': subject_record.record_id.course_id.name,
            'source': 'history',
            'subject_record_id': subject_record.id,
            'internal_grade': subject_record.internal_grade,
            'external_weight': subject_record.external_weight,
            'already_scored': subject_record.external_is_scored,
            'score': subject_record.external_grade,
        }

    def _group_students(self):
        """The students currently taking the group's subjects (ems.enrollment).

        Only actual students: a withdrawal keeps its ems.enrollment records (they are not
        deleted until the transition) even though the exit already detached the student from
        the group, so without this filter an ex-student would still be offered for grading.
        """
        return self.env['ems.enrollment'].sudo().search([
            ('group_id', '=', self.group_id.id),
            ('student_id.contact_type', '=', 'student'),
        ]).mapped('student_id')

    def _live_subject_lines(self, student):
        """The student's grade lines of the LAST round of each module of the group with an
        external weight — the round that carries the final grade of the course in progress."""
        lines = self.env['ems.grade_subject_line'].sudo().search([
            ('student_id', '=', student.id),
            ('grade_session_id.group_id', '=', self.group_id.id),
        ]).filtered(lambda line: line.external_ponderation > 0)
        last_lines = self.env['ems.grade_subject_line'].sudo()
        for subject in lines.mapped('subject_id'):
            subject_lines = lines.filtered(lambda line: line.subject_id == subject)
            # round is a single-digit selection, so a string comparison is enough.
            last_lines |= max(subject_lines, key=lambda line: line.grade_session_id.round)
        return last_lines

    def _pending_subject_records(self, student):
        """Archived subjects of previous courses waiting for their work placement grade
        (passed, external weight > 0, no final yet)."""
        return self.env['ems.student.year_record.subject'].sudo().search([
            ('record_id.student_id', '=', student.id),
            ('final_pending', '=', True)])

    def action_apply(self):
        """Write the EM grade of every module the user graded — the student's single grade
        (every module of theirs) or, when the student is graded per module, the grade of each
        cell. A grade below 5 means the placement is repeated, never the subject: the grade is
        kept but not marked as scored, so the subject stays passed with its final pending."""
        self.ensure_one()
        if not self._user_can_manage_group(self.group_id):
            raise UserError(_("You can only grade the work placement of a group you tutor."))
        by_student = {student_line.student_id: student_line
                      for student_line in self.student_line_ids}
        graded = 0
        to_repeat = 0
        for line in self.line_ids:
            student_line = by_student.get(line.student_id)
            if student_line and student_line.per_module:
                # Graded module by module: only the cells the user filled in.
                if not line.to_apply:
                    continue
                score = line.score
            elif student_line and student_line.to_apply:
                # The single grade of the student goes to every module of theirs.
                score = student_line.score
            else:
                continue
            self._check_line_in_scope(line)
            is_scored = score >= 5
            if line.subject_line_id:
                # Sudo (ACL: the secretary only reads grade lines) + the ems_em_grading key,
                # which lifts the session-state guard for the external fields only: the EM
                # arrives after the rounds are closed, which is exactly what that guard
                # blocks. The group ownership check above is what authorises the write.
                line.subject_line_id.sudo().with_context(ems_em_grading=True).write({
                    'external_score': score,
                    'external_is_scored': is_scored,
                })
            else:
                line.subject_record_id.sudo().apply_external_grade(score)
            if is_scored:
                graded += 1
            else:
                to_repeat += 1
        if not graded and not to_repeat:
            raise UserError(_("Enter the work placement grade of at least one student."))
        message = _("%s module(s) graded.") % graded
        if to_repeat:
            message += " " + _("%s placement(s) below 5: to be repeated (final still pending).") \
                % to_repeat
        # Refresh the grids so the applied grades show up as already graded, and stay on the
        # wizard: the tutor usually grades a few students, comes back and grades more.
        self._fill_lines()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Work placement (EM)"),
                'message': message,
                'type': 'warning' if to_repeat else 'success',
                'sticky': False,
                # Reopen the wizard on its refreshed lines. An act_window built by hand must
                # carry `views`: the web client reads action.views (view_mode alone is only
                # resolved for actions loaded from ir.actions.act_window records).
                'next': {
                    'type': 'ir.actions.act_window',
                    'name': _("Work placement evaluation (EM)"),
                    'res_model': self._name,
                    'res_id': self.id,
                    'views': [[self.env.ref('ems.view_em_grading_wizard_form').id, 'form']],
                    'target': 'current',
                },
            },
        }

    def _check_line_in_scope(self, line):
        """The apply runs with sudo, so never trust the line's target references coming
        back from the client: both must belong to the wizard's group."""
        if line.subject_line_id:
            if line.subject_line_id.sudo().grade_session_id.group_id != self.group_id:
                raise UserError(_("Invalid module line: it does not belong to the selected group."))
        elif line.subject_record_id:
            record = line.subject_record_id.sudo().record_id
            if record.group_id != self.group_id \
                    and record.student_id not in self._group_students():
                raise UserError(_("Invalid module line: it does not belong to the selected group."))
        else:
            raise UserError(_("Invalid module line: it does not belong to the selected group."))


class EmsEmGradingWizardStudent(models.TransientModel):
    _name = 'ems.em_grading_wizard.student'
    _description = 'Work placement (EM) grading wizard: one student of the group.'
    _order = 'student_name asc'

    wizard_id = fields.Many2one(comodel_name='ems.em_grading_wizard', ondelete='cascade')
    student_id = fields.Many2one(string="Student", comodel_name='res.partner')
    student_name = fields.Char(string="Student name")
    student_firstname = fields.Char(string="First name")
    student_lastname = fields.Char(string="Last name")
    module_count = fields.Integer(string="Modules")
    score = fields.Integer(string="EM grade")
    # Only the students the user actually graded are written: with the whole group on
    # screen, an untouched student must never receive a grade (0 is a real grade).
    to_apply = fields.Boolean(string="Apply")
    # The exception: this student's placement is graded module by module (the cells of the
    # matrix row), instead of one grade for all of them.
    per_module = fields.Boolean(string="Grade per module")

    @api.constrains('score')
    def _check_score(self):
        for student_line in self:
            if student_line.score < 0 or student_line.score > 10:
                raise ValidationError(_("The work placement grade must be within the range [0, 10]."))


class EmsEmGradingWizardLine(models.TransientModel):
    _name = 'ems.em_grading_wizard.line'
    _description = 'Work placement (EM) grading wizard line: one module of a student.'
    _order = 'student_name asc, course_name asc, subject_name asc'

    wizard_id = fields.Many2one(comodel_name='ems.em_grading_wizard', ondelete='cascade')
    student_id = fields.Many2one(string="Student", comodel_name='res.partner')
    student_name = fields.Char(string="Student name")
    subject_id = fields.Many2one(string="Subject", comodel_name='ems.subject')
    subject_name = fields.Char(string="Subject name")
    subject_acronym = fields.Char(string="Subject code")
    course_name = fields.Char(string="Course")
    source = fields.Selection(string="Source", selection=[
        ('live', 'Current course'),
        ('history', 'Previous course'),
    ])
    # Exactly one of the two is set, depending on the source.
    subject_line_id = fields.Many2one(string="Grade line", comodel_name='ems.grade_subject_line')
    subject_record_id = fields.Many2one(string="History line",
                                        comodel_name='ems.student.year_record.subject')
    internal_grade = fields.Integer(string="Internal grade")
    external_weight = fields.Float(string="EM weight (%)")
    already_scored = fields.Boolean(string="Already graded")
    score = fields.Integer(string="EM grade")
    # Set by the matrix when the cell is filled in: only those cells are written (and only
    # for the students graded per module).
    to_apply = fields.Boolean(string="Apply")

    @api.constrains('score')
    def _check_score(self):
        for line in self:
            if line.score < 0 or line.score > 10:
                raise ValidationError(_("The work placement grade must be within the range [0, 10]."))
