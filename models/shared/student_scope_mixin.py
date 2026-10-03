# -*- coding: utf-8 -*-
from odoo import api, fields, models

from . import base


class EmsStudentScopeMixin(models.AbstractModel):
    """Picking the students a sending assistant acts on: by hand, or by groups, studies and levels
    of an academic year - and, for a tutor, only their own.

    Shared by ems.authorization.send.wizard and ems.contact.data.request.send.wizard (issue #507),
    which used to be one assistant's private code. The inheriting assistant declares the
    allowed_group_ids/allowed_study_ids/allowed_level_ids fields the pickers' domains read, each with
    an explicit relation table: two Many2many to the same comodel on one model would otherwise get
    the same auto-generated table name.
    """
    _name = 'ems.student.scope.mixin'
    _description = 'Students picked by hand or by group, study and level'

    course_id = fields.Many2one(
        'ems.course',
        string='Academic Year',
        required=True,
        default=lambda self: self.env['res.partner']._ems_running_course(),
    )
    target = fields.Selection([
        ('students', 'Selected students'),
        ('scope', 'Groups / studies / levels'),
    ], string='Send to', default='students', required=True)
    student_ids = fields.Many2many(
        'res.partner', string='Students',
        domain=[('contact_type', 'in', ('student', 'applicant'))],
    )
    # The student picker's domain (the view's domain="student_domain"): a tutor is only offered
    # the students they act on (issue #550). A default, not a compute: the assistant is always a
    # new record, and a computed field with no field dependencies is not sent to the client on a
    # new record - the same reason as ems.em_grading_wizard.group_domain.
    student_domain = fields.Char(default=lambda self: str(self._scope_student_domain()))
    group_ids = fields.Many2many(
        'ems.group', string='Groups', domain="[('id', 'in', allowed_group_ids)]")
    ems_study_ids = fields.Many2many(
        'ems.study', string='Studies', domain="[('id', 'in', allowed_study_ids)]")
    ems_level_ids = fields.Many2many(
        'ems.level', string='Levels', domain="[('id', 'in', allowed_level_ids)]")

    @api.model
    def _scope_sees_every_student(self):
        return base.EmsBase.get_user_sees_every_student(self)

    @api.model
    def _scope_student_domain(self):
        domain = [('contact_type', 'in', ('student', 'applicant'))]
        if not self._scope_sees_every_student():
            domain.append(('tutor_id.tutor_scope_user_ids', '=', self.env.uid))
        return domain

    @api.model
    def _scope_acts_on_student(self, student):
        """Whether the sender may act on this student: staff who see every student, or whoever
        acts as the student's tutor (the tutor, or a chief above them - issue #483). Also drives
        which entries a student's form offers (res.partner._compute_student_action_rights)."""
        return self._scope_sees_every_student() or base.EmsBase.user_acts_as_tutor(self, student.tutor_id)

    @api.model
    def _scope_allowed_groups(self):
        """The main groups the sender may pick: every one for the staff who see every student, and
        for a tutor the groups they act as tutor of - their own, or those of the tutors below them
        (hr.employee.tutor_scope_user_ids, issue #483)."""
        groups = self.env['ems.group'].search([('group_type', '=', 'main')])
        if self._scope_sees_every_student():
            return groups
        return groups.filtered(lambda group: base.EmsBase.user_acts_as_tutor(self, group.tutor_id))

    @api.model
    def _scope_students_from_context(self):
        """The students selected in a students list the assistant was opened from, the sender's own
        only (issue #550): a tutor selecting the whole list starts from their students, not from
        everyone else's flagged as left out. Only when the list really was a students list: opened
        from another record, active_ids carry that record's own id, which read as a res.partner id
        failed with "record does not exist"."""
        if self.env.context.get('active_model') != 'res.partner':
            return self.env['res.partner']
        return self.env['res.partner'].browse(self.env.context.get('active_ids') or []).filtered(
            lambda partner: partner.contact_type in ('student', 'applicant')
            and self._scope_acts_on_student(partner))

    def _enrolled_students(self):
        """Students holding a live (not cancelled) enrollment for the selected academic year.

        The scope target starts here rather than from ems.group's own student list: a group
        record still holds students who have since left, and asking an ex-student for anything
        is exactly the mistake this avoids.
        """
        enrollments = self.env['sale.order'].search([
            ('ems_course_id', '=', self.course_id._origin.id),
            ('state', '!=', 'cancel'),
        ])
        return enrollments.mapped('partner_id')

    def _students_from_scope(self):
        """Enrolled students in any of the chosen groups, studies or levels. Nothing chosen
        means nobody, never the whole centre."""
        groups = self.group_ids._origin
        studies = self.ems_study_ids._origin
        levels = self.ems_level_ids._origin
        if not (groups or studies or levels):
            return self.env['res.partner']

        def in_scope(student):
            level, study = student._ems_level_study_in_force()
            return student.main_group_id in groups or study in studies or level in levels

        return self._enrolled_students().filtered(in_scope)

    def _resolve_students(self):
        """The students this assistant would act on, deduplicated.

        For a tutor, only their own group's - whatever reached the assistant. The pickers only offer
        their own students and groups, and what a tutor can read of the enrollments behind the scope
        target is limited to them too, but this is the one place that decides, not the widgets.
        """
        self.ensure_one()
        if self.target == 'students':
            students = self.student_ids._origin
        else:
            students = self._students_from_scope()
        return students.filtered(self._scope_acts_on_student)
