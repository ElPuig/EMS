# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class EmsEnrollment(models.Model):
    _name = "ems.enrollment"
    _description = "Enrollment: ternary relation between student-group-uf."
    _order = 'student_id, subject_id, group_id'
    _inherit = ['ems.base']
    _sql_constraints = [
        ('unique_student_group_subject', 'UNIQUE(student_id, group_id, subject_id)',
         'This student is already enrolled in this subject for this group.'),
    ]

    student_id = fields.Many2one(string="Student", comodel_name="res.partner", required=True, ondelete='cascade', domain="[('contact_type', '=', 'student')]")
    group_id = fields.Many2one(string="Group", comodel_name="ems.group", ondelete='cascade', required=True)
    subject_id = fields.Many2one(string="Subject", comodel_name="ems.subject", ondelete='cascade', required=True)

    # NOTE: this field is used to filter the availabe subjects within the view (avoiding the selection of repeated subject in enrolling form).
    inuse_subject_ids = fields.Many2many('ems.subject', compute='_compute_inuse_subject_ids', store=False)

    # NOTE: this field is used within ems.base.get_user_is_tutor, which is used to block the opening of the edit form if no permissions.
    #       BUT, at this moment, only admins are allowed to create manual enrollments.
    # tutor_id = fields.Many2one(string='Tutor', related="student_id.tutor_id")

    @api.model
    def default_get(self, fields_list):
        # TODO: unable to hide the "NEW" button based for only tutors...
        res = super().default_get(fields_list)
        # Only MANUAL creation is blocked. create() itself goes through default_get
        # (_add_missing_default_values), so without the sudo escape hatch this guard also
        # blocked every programmatic caller - sale.order._ems_apply_destination_placement()
        # above all, which materializes the subject enrollments when an enrollment is
        # confirmed. sudo() does NOT turn env.user into the superuser, it only sets env.su,
        # so get_user_is_admin() keeps reflecting the real user behind the request (the
        # student confirming from the portal, the secretary confirming from the backend) and
        # the guard fired on them. env.su is what tells the two apart: a form opened from the
        # UI never carries it, a placement running on their behalf always does.
        if not self.env.su and "user_is_admin" in fields_list:
            # This happens when opening the form, when storing fires again but field per field
            if not (res["user_is_admin"]):
                raise UserError(_("Only admins can create manual enrollments. If you're a group's tutor, you can enroll students using the student's form."))
        return res

    @api.depends('student_id')
    def _compute_inuse_subject_ids(self):
        self.compute_exclusion_ids('inuse_subject_ids', lambda enrollment: enrollment.student_id,
                                    'student_id.enrollment_ids.subject_id')

    @api.depends('subject_id')
    def _compute_display_name(self):
        for enrollment in self:
            enrollment.display_name = enrollment.subject_id.display_name

    @api.model_create_multi
    def create(self, vals_list):
        enrollments = super().create(vals_list)
        for enrollment in enrollments:
            enrollment._ems_sync_attendance_template_add()
            enrollment._ems_sync_grade_session_add()
        return enrollments

    def unlink(self):
        if not self.env.context.get('ems_bypass_grade_guard'):
            for enrollment in self:
                if self.env['ems.grade_session']._ems_has_scored_grades(
                    enrollment.student_id.id, enrollment.group_id.id, enrollment.subject_id.id
                ):
                    raise UserError(_("This enrollment cannot be deleted: the student already has grades assigned for this group and subject."))

        snapshots = [(enrollment.student_id.id, enrollment.group_id.id, enrollment.subject_id.id) for enrollment in self]
        res = super().unlink()
        for student_id, group_id, subject_id in snapshots:
            self._ems_sync_attendance_template_remove(student_id, group_id, subject_id)
            self._ems_sync_grade_session_remove(student_id, group_id, subject_id)
        return res

    def _ems_matching_attendance_schedules(self, subject_id, group_id):
        # NOTE: moved from matching ems.attendance_template directly to matching its
        # attendance_schedule_ids (2026-08-11, see plans/calendar_driven_attendance_templates.md,
        # point 1) - the roster now lives per schedule line, not per template, so a sync must reach
        # every one of a matching template's lines, not the template itself.
        return self.env['ems.attendance_template'].search([
            ('subject_id', '=', subject_id),
            ('group_ids', 'in', group_id),
        ]).attendance_schedule_ids

    @api.model
    def _ems_still_enrolled(self, student_id, subject_id, group_ids):
        """True if an ems.enrollment row still exists for this student+subject in any
        of the given group_ids. Shared by both unlink() sync hooks below (and any
        future caller needing the same "does a sibling enrollment still cover this
        student" check) so they can't drift apart on what "still enrolled" means."""
        return bool(self.search_count([
            ('student_id', '=', student_id),
            ('subject_id', '=', subject_id),
            ('group_id', 'in', group_ids),
        ]))

    def _ems_sync_attendance_template_add(self):
        self.ensure_one()
        schedules = self._ems_matching_attendance_schedules(self.subject_id.id, self.group_id.id)
        schedules.student_ids = [(4, self.student_id.id, 0)]

    @api.model
    def _ems_sync_attendance_template_remove(self, student_id, group_id, subject_id):
        schedules = self._ems_matching_attendance_schedules(subject_id, group_id)
        for schedule in schedules:
            template = schedule.attendance_template_id
            # A template can cover several 'group_ids' (co-teaching): only drop the student if no
            # other remaining enrollment still keeps them within this same template's scope.
            if not self._ems_still_enrolled(student_id, template.subject_id.id, template.group_ids.ids):
                schedule.student_ids = [(3, student_id)]

    def _ems_sync_grade_session_add(self):
        self.ensure_one()
        sessions = self.env['ems.grade_session'].search([
            ('group_id', '=', self.group_id.id),
            ('subject_id', '=', self.subject_id.id),
            ('state', '=', 'open'),
        ])
        for session in sessions:
            session._ems_add_student_lines(self.student_id)

    @api.model
    def _ems_sync_grade_session_remove(self, student_id, group_id, subject_id):
        # Mirrors _ems_sync_attendance_template_remove's guard - see
        # plans/grade_session_remove_missing_still_enrolled_guard.md.
        if self._ems_still_enrolled(student_id, subject_id, [group_id]):
            return
        sessions = self.env['ems.grade_session'].search([
            ('group_id', '=', group_id),
            ('subject_id', '=', subject_id),
            ('state', '=', 'open'),
        ])
        for session in sessions:
            session.grade_outcome_line_ids.filtered(lambda line: line.student_id.id == student_id).unlink()
            session.grade_subject_line_ids.filtered(lambda line: line.student_id.id == student_id).unlink()
