# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError

from .enrollment_slot import EMS_SKIP_SLOT_RESYNC


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

    # Issue #534: the exact weekly slots of a CUSTOM enrollment. Empty means the enrollment follows
    # its group - see '_ems_attends' and docs/en/developers/contacts/enrollment_slot.md.
    slot_ids = fields.One2many(string="Slots", comodel_name="ems.enrollment.slot", inverse_name="enrollment_id")
    is_custom_schedule = fields.Boolean(string="Custom", compute="_compute_is_custom_schedule")

    # NOTE: this field is used within ems.base.get_user_is_tutor, which is used to block the opening of the edit form if no permissions.
    #       BUT, at this moment, only admins and secretary are allowed to create manual enrollments.
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
        # so get_user_is_admin()/get_user_is_secretary() keep reflecting the real user behind
        # the request (the student confirming from the portal, the secretary confirming from
        # the backend) and the guard fired on them. env.su is what tells the two apart: a form
        # opened from the UI never carries it, a placement running on their behalf always does.
        if not self.env.su and "user_is_admin" in fields_list:
            # This happens when opening the form, when storing fires again but field per field
            if not (res["user_is_admin"] or self.get_user_is_secretary() or self.get_user_is_head_of_studies()):
                raise UserError(_("Only admins, secretary staff and Head of Studies can create manual enrollments."))
        return res

    @api.depends('student_id')
    def _compute_inuse_subject_ids(self):
        self.compute_exclusion_ids('inuse_subject_ids', lambda enrollment: enrollment.student_id,
                                    'student_id.enrollment_ids.subject_id')

    @api.onchange('subject_id')
    def _onchange_subject_id(self):
        """Default the group of a line added by hand on the student's form to the course the
        study's enrollment templates sell the subject for (a 1st-year module pending for a
        2nd-year student goes to the 1st-year group), the same group the enrollment placement
        would pick. A reinforcement group is a deliberate choice and is left alone."""
        for enrollment in self:
            main_group = enrollment.student_id.main_group_id
            if not (enrollment.subject_id and main_group) or enrollment.group_id.group_type == 'reinforcement':
                continue
            enrollment.group_id = main_group._ems_group_for_subject(enrollment.subject_id)

    @api.depends('slot_ids')
    def _compute_is_custom_schedule(self):
        for enrollment in self:
            enrollment.is_custom_schedule = bool(enrollment.slot_ids)

    @api.depends('subject_id')
    def _compute_display_name(self):
        for enrollment in self:
            enrollment.display_name = enrollment.subject_id.display_name

    @api.model_create_multi
    def create(self, vals_list):
        enrollments = super().create(vals_list)
        for enrollment in enrollments:
            self._ems_resync_student_lines(enrollment.student_id, enrollment.subject_id)
            enrollment._ems_sync_grade_session_add()
        return enrollments

    def write(self, vals):
        previous = self.env['ems.enrollment.slot']._ems_snapshot_lines(self) if 'group_id' in vals else {}
        res = super().write(vals)
        self.env['ems.enrollment.slot']._ems_resync(previous)
        return res

    def unlink(self):
        if not self.env.context.get('ems_bypass_grade_guard'):
            for enrollment in self:
                if self.env['ems.grade_session']._ems_has_scored_grades(
                    enrollment.student_id.id, enrollment.group_id.id, enrollment.subject_id.id
                ):
                    raise UserError(_("This enrollment cannot be deleted: the student already has grades assigned for this group and subject."))

        snapshots = [(enrollment.student_id.id, enrollment.group_id.id, enrollment.subject_id.id) for enrollment in self]
        previous = self.env['ems.enrollment.slot']._ems_snapshot_lines(self)
        # NOTE: the slots go first, through the ORM but without resyncing on their own - the
        # database-level cascade would delete them too, but '_ems_resync' below already covers
        # every line they made the student attend ('previous').
        self.slot_ids.with_context(**{EMS_SKIP_SLOT_RESYNC: True}).sudo().unlink()
        res = super().unlink()
        self.env['ems.enrollment.slot']._ems_resync(previous)
        for student_id, group_id, subject_id in snapshots:
            self._ems_sync_grade_session_remove(student_id, group_id, subject_id)
        return res

    def _ems_attends(self, group, weekday, start_time, end_time):
        """True if this enrollment makes its student attend the 'group' class at that weekday/time
        (issue #534): every class of its own group when it follows the group (no slot), only its
        stored slots when it is custom. THE rule every consumer goes through - schedule-line
        rosters ('_ems_attended_lines', 'ems.attendance_schedule._ems_expected_students') and the
        student's schedule tab ('res.partner._ems_teaching_attendances')."""
        self.ensure_one()
        if not self.slot_ids:
            return group == self.group_id
        return any(
            slot.group_id == group and slot.weekday == weekday
            and slot.start_time == start_time and slot.end_time == end_time
            for slot in self.slot_ids
        )

    def _ems_attends_line(self, line):
        """'_ems_attends' for an 'ems.attendance_schedule' line: its template must teach one of these
        enrollments' subjects, to one of its groups the enrollment attends at the line's time."""
        template = line.attendance_template_id
        return any(
            enrollment.subject_id == template.subject_id and any(
                enrollment._ems_attends(group, line.weekday, line.start_time, line.end_time)
                for group in template.group_ids
            )
            for enrollment in self
        )

    def _ems_attended_lines(self):
        """Every active schedule line these enrollments make their student attend."""
        # NOTE: sudo() - issue #435. Rosters are a system-level consequence of an already-authorized
        # enrollment change, not a separate action the acting user has to be entitled to perform on
        # the attendance side: a secretary is read-only on ems.attendance_schedule and a teacher only
        # sees the templates they teach, so without it the caller's own rights decided how much of the
        # roster got synced (seven ex-ESO students never reached SA1A's roll-call that way).
        # active_test=True forced: an action's own active_test=False context would otherwise leak in
        # and bring back archived lines.
        if not self:
            return self.env['ems.attendance_schedule']
        candidates = self.env['ems.attendance_schedule'].sudo().with_context(active_test=True).search([
            ('attendance_template_id.active', '=', True),
            ('attendance_template_id.subject_id', 'in', self.subject_id.ids),
            ('attendance_template_id.group_ids', 'in', (self.group_id | self.slot_ids.group_id).ids),
        ])
        return candidates.filtered(self._ems_attends_line)

    @api.model
    def _ems_student_subject_enrollments(self, student, subject):
        # sudo(): see '_ems_attended_lines' - a cascade must see every enrollment of the student.
        return self.sudo().search([('student_id', '=', student.id), ('subject_id', '=', subject.id)])

    @api.model
    def _ems_resync_student_lines(self, student, subject, previous_lines=None):
        """Puts 'student' in every active line their enrollments in 'subject' now make them attend,
        and takes them out of the lines in 'previous_lines' (what they attended before the change)
        that no longer apply. Only ever touches this student, so a teacher's own manual roster edits
        for anybody else survive. Shared by every enrollment/slot change (issue #534)."""
        current = self._ems_student_subject_enrollments(student, subject)._ems_attended_lines()
        current.student_ids = [(4, student.id)]
        if previous_lines:
            (previous_lines - current).sudo().student_ids = [(3, student.id)]

    def action_customize_slots(self):
        """Stores the slots the enrollment follows right now (its group's), so customizing starts
        from what the student already attends and no roster changes."""
        Slot = self.env['ems.enrollment.slot']
        for enrollment in self.filtered(lambda enrollment: not enrollment.slot_ids):
            lines = enrollment._ems_attended_lines()
            Slot.create([
                {'enrollment_id': enrollment.id, 'group_id': enrollment.group_id.id, **Slot._ems_key_vals(line)}
                for line in lines
                # one slot per key, even if several active lines share it (e.g. date-ranged templates)
                if line == lines.filtered(lambda other, line=line: Slot._ems_key_vals(other) == Slot._ems_key_vals(line))[:1]
            ])

    def action_follow_group(self):
        self.slot_ids.unlink()

    @api.model
    def _ems_move_group(self, student, old_group, new_group):
        """Repoints 'student's enrollments from 'old_group' to 'new_group' (same subject),
        called when their main group changes (see res.partner.write()). An enrollment
        already in a group other than 'old_group' is left untouched.

        Reuses plain create()/unlink() instead of writing 'group_id' directly, so the
        existing sync hooks (attendance schedule rosters, open grade session lines) still
        apply exactly as they already do for any other enrollment change. Runs entirely
        with sudo(): by the time this runs, 'student.main_group_id' already points at
        'new_group' (write() calls this AFTER super().write()), so a caller whose own
        access to the student/enrollment came from being the OLD group's tutor
        (rule_contact_tutor/rule_enrollment_tutor, both keyed off the student's CURRENT
        tutor_id) can lose that access mid-transaction the moment the group differs -
        most obviously when the destination group has a different tutor. The group change
        itself was already authorized at the point 'main_group_id' was written; this
        cascade is a system-level consequence of that authorized action, not a separate
        action needing its own re-check - the same reasoning
        _ems_apply_destination_placement() already applies to its own sudo()'d create().
        sudo() only bypasses ACL/record rules, not this method's own Python-level guard:
        unlink()'s scored-grades check still runs and still aborts the whole group change
        with a UserError if a subject already has scored grades in the old group.
        """
        Enrollment = self.sudo()
        for enrollment in Enrollment.search([('student_id', '=', student.id), ('group_id', '=', old_group.id)]):
            subject = enrollment.subject_id
            already_in_new_group = Enrollment.search_count([
                ('student_id', '=', student.id), ('group_id', '=', new_group.id), ('subject_id', '=', subject.id)])
            if not already_in_new_group:
                new_enrollment = Enrollment.create({'student_id': student.id, 'group_id': new_group.id, 'subject_id': subject.id})
                if enrollment.slot_ids:
                    # Issue #534: a custom enrollment keeps its slots - they don't depend on the
                    # student's main group.
                    previous = (enrollment | new_enrollment)._ems_attended_lines()
                    enrollment.slot_ids.with_context(**{EMS_SKIP_SLOT_RESYNC: True}).write({'enrollment_id': new_enrollment.id})
                    enrollment.with_context(**{EMS_SKIP_SLOT_RESYNC: True}).unlink()
                    self._ems_resync_student_lines(student, subject, previous)
                    continue
            enrollment.unlink()

    @api.model
    def _ems_still_enrolled(self, student_id, subject_id, group_ids):
        """True if an ems.enrollment row still exists for this student+subject in any
        of the given group_ids - the guard of '_ems_sync_grade_session_remove' below, and
        of any future caller needing the same "does a sibling enrollment still cover
        this student" check."""
        # sudo(): a guard protecting a system cascade must see every enrollment, not only the
        # ones the acting user is allowed to read - see _ems_attended_lines().
        return bool(self.sudo().search_count([
            ('student_id', '=', student_id),
            ('subject_id', '=', subject_id),
            ('group_id', 'in', group_ids),
        ]))

    def _ems_sync_grade_session_add(self):
        self.ensure_one()
        # sudo(): same reasoning as _ems_attended_lines() - a teacher only sees
        # their own grade sessions (rule_grade_session_teacher_own), so without it a session
        # belonging to a different teacher never got the new student's lines.
        sessions = self.env['ems.grade_session'].sudo().search([
            ('group_id', '=', self.group_id.id),
            ('subject_id', '=', self.subject_id.id),
            ('state', '=', 'open'),
        ])
        for session in sessions:
            session._ems_add_student_lines(self.student_id)

    @api.model
    def _ems_sync_grade_session_remove(self, student_id, group_id, subject_id):
        # A sibling enrollment of the same group still covering the student keeps the lines - see
        # plans/grade_session_remove_missing_still_enrolled_guard.md.
        if self._ems_still_enrolled(student_id, subject_id, [group_id]):
            return
        sessions = self.env['ems.grade_session'].sudo().search([
            ('group_id', '=', group_id),
            ('subject_id', '=', subject_id),
            ('state', '=', 'open'),
        ])
        for session in sessions:
            session.grade_outcome_line_ids.filtered(lambda line: line.student_id.id == student_id).unlink()
            session.grade_subject_line_ids.filtered(lambda line: line.student_id.id == student_id).unlink()
