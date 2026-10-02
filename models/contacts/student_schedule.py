# -*- coding: utf-8 -*-

from odoo import api, fields, models


class ems_student_schedule(models.Model):
    # NOTE: an explicit '_name' is required here — a 2-item '_inherit' list without one would make
    # Odoo's metaclass define a brand-new model named after this Python class instead of extending
    # 'res.partner' in place (see MetaModel in odoo/models.py, and the same NOTE in
    # models/contacts/group_schedule.py).
    _name = 'res.partner'
    _inherit = ['res.partner', 'ems.schedule_report_mixin']

    # Union of two sources: every real teaching slot matching one of this student's own
    # (subject_id, group_id) enrollment pairs, aggregated across every teacher's calendar — and,
    # when derivable, the student's own MAIN group's break period (see '_get_break_entries').
    # Unlike ems.group's own version of this field (which aggregates a single group's WHOLE
    # schedule, any subject), a student only ever takes some of a group's subjects, so the search
    # is scoped per enrollment pair, not per group alone — a student enrolled through more than
    # one group (electives, reinforcement) can end up with entries from several groups at once,
    # including genuinely overlapping ones (see the OWL widget's column-split layout). Not stored,
    # same pattern already used for 'ems.group.schedule_attendance_ids'/'enrolled_student_ids'.
    schedule_attendance_ids = fields.Many2many(string="Schedule", comodel_name="resource.calendar.attendance",
        compute="_compute_schedule_attendance_ids")
    # A student has no shift of their own — only their main group does. Exposed as a plain related
    # field (read-only, invisible on the form) purely so the Schedule tab's widget can read
    # 'record.data.shift' exactly the way it already does for ems.group's own 'shift' field, with
    # no model-specific branching needed in the shared JS component (see
    # 'schedule_grid_readonly_field.js's 'bounds' getter) — the same "smuggle a helper field in via
    # an invisible view field" pattern already used for 'hr.employee.can_edit_schedule'.
    shift = fields.Selection(related="main_group_id.shift", string="Shift", readonly=True)

    # Issue #534: a student attending a subject split across several groups. The toggle only shows
    # the custom-schedule tools on the form; switching it off makes every enrollment follow its group
    # again (see 'write'). The slots themselves live on ems.enrollment.slot.
    custom_schedule = fields.Boolean(string="Custom schedule",
        help="Attend some subjects only in specific sessions, possibly with other groups of the same level.")
    enrollment_slot_ids = fields.One2many(string="Slots", comodel_name="ems.enrollment.slot", inverse_name="student_id")
    enrollment_slot_broken_count = fields.Integer(string="Slots no longer in the schedule",
        compute="_compute_enrollment_slot_broken_count")

    # A real dependency on 'resource.calendar.attendance' itself can't be expressed (it's a
    # cross-model search, same structural limitation ems.group._compute_schedule_attendance_ids
    # already has) - a web client request always computes this fresh anyway (a new transaction,
    # empty cache, every time). This @api.depends only matters for the SAME transaction re-reading
    # the field after one of these actually changes (a test's own setUpClass creating enrollments
    # right after the student, an admin editing main_group_id mid-session, ...) - without it nothing
    # tells Odoo to invalidate an earlier, now-stale cached value from before that change (found via
    # TestStudentSchedule's own break-derivation test: setUpClass creates the student, THEN its
    # enrollments, and an unrelated earlier field read on the student had already cached this field
    # as empty in between the two - with no @api.depends, the later enrollments never invalidated it).
    @api.depends('contact_type', 'main_group_id', 'enrollment_ids.subject_id', 'enrollment_ids.group_id',
                 'enrollment_ids.slot_ids.group_id', 'enrollment_ids.slot_ids.weekday',
                 'enrollment_ids.slot_ids.start_time', 'enrollment_ids.slot_ids.end_time')
    def _compute_schedule_attendance_ids(self):
        # 'active_test=True' forced explicitly in _ems_teaching_attendances(), not left to the
        # ORM's own default: this tab is opened from ems.action_student_kanban, whose own context
        # sets active_test=False so archived/withdrawn students still show up in that list - a
        # context that then leaks into
        # this compute too, since it's the same request. Without forcing it back on here, a stale/
        # archived calendar's own leftover attendance rows (never deleted, only archived, by course
        # transition's calendar rollover) resurface as if they were still part of the student's
        # CURRENT schedule - duplicated against, and often overlapping, the real one. Confirmed
        # live 2026-09-10 (issue #408 follow-up): a real student's Schedule tab showed a whole
        # extra, out-of-date copy of several subjects, each pair genuinely overlapping the real
        # one - traced to exactly this, not a data problem. See the identical fix on
        # ems.group._compute_schedule_attendance_ids and
        # ems.schedule_report_mixin._get_level_break_entries.
        for student in self:
            if student.contact_type != 'student':
                student.schedule_attendance_ids = self.env['resource.calendar.attendance']
                continue
            student.schedule_attendance_ids = student._ems_teaching_attendances() | student._get_break_entries()

    def _compute_enrollment_slot_broken_count(self):
        for student in self:
            student.enrollment_slot_broken_count = len(
                student.enrollment_slot_ids.filtered(lambda slot: slot.state == 'broken'))

    def write(self, vals):
        res = super().write(vals)
        if 'custom_schedule' in vals and not vals['custom_schedule']:
            self.enrollment_slot_ids.unlink()
        return res

    def action_drop_custom_schedule(self):
        self.write({'custom_schedule': False})

    def _ems_teaching_attendances(self):
        """The teaching periods of the student's own schedule (breaks excluded): every period of
        a subject they are enrolled in, in the group they are enrolled through - so a student
        taking a subject in another group (e.g. a 2nd-year one repeating a 1st-year subject)
        gets that group's period, not their main group's. Also used by the tutor's attendance
        report to know when their students' day ends (attendance_report_schedule.py). A custom
        enrollment (issue #534) only contributes its own slots, possibly from other groups -
        'ems.enrollment._ems_attends' decides, the same rule the attendance rosters follow."""
        self.ensure_one()
        Attendance = self.env['resource.calendar.attendance'].with_context(active_test=True)
        teaching = Attendance
        for enrollment in self.enrollment_ids:
            teaching |= Attendance.search([
                ('subject_id', '=', enrollment.subject_id.id),
                ('group_ids', 'in', (enrollment.group_id | enrollment.slot_ids.group_id).ids),
            ]).filtered(lambda block, enrollment=enrollment: any(
                enrollment._ems_attends(group, block.dayofweek, block.hour_from, block.hour_to)
                for group in block.group_ids
            ))
        return teaching

    def _get_break_entries(self):
        """The student's break/patio period, derived from their MAIN group's level/shift — a
        student can be enrolled through several groups (electives, reinforcement), but only ever
        has one homeroom/main group whose break applies to them; see
        'ems.schedule_report_mixin._get_level_break_entries' for the actual derivation."""
        self.ensure_one()
        return self._get_level_break_entries(self.main_group_id.level_id, self.shift)

    # No '_schedule_report_shift' override needed: 'ems.schedule_report_mixin''s default (a plain
    # 'self.shift' read) already resolves correctly, since 'shift' above is itself a related field
    # onto the student's own main group.
