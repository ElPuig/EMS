# -*- coding: utf-8 -*-

from collections import defaultdict

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError

# Session line statuses an expected withdrawal takes off the roll-call when it is marked: the
# roll-call's default (attended) and a plain miss. Anything else was set on purpose (a delay, a
# justified absence) and is left alone.
REMOVABLE_STATUS_XMLIDS = ('ems.attendance_status_attended', 'ems.attendance_status_miss')


class EmsWithdrawalExpectedPartner(models.Model):
    """Expected withdrawal (issue #644): the tutor knows a student won't come back and asks for the
    withdrawal, which takes a while. Meanwhile the student stays a student (not archived), but every
    roll-call lists them as "not required to attend" (an archived session line, like the teacher's
    own "Remove from the roll-call"), so they stop piling up absences. Reverting it turns those
    sessions into absences. See docs/en/developers/contacts/withdrawal_expected.md."""
    _inherit = 'res.partner'

    withdrawal_expected = fields.Boolean(string="Expected withdrawal", readonly=True, copy=False, tracking=True)
    withdrawal_expected_date = fields.Datetime(string="Expected withdrawal since", readonly=True, copy=False)
    withdrawal_expected_by_id = fields.Many2one(string="Expected withdrawal marked by", comodel_name='res.users',
                                                readonly=True, copy=False)
    withdrawal_expected_note = fields.Text(string="Expected withdrawal note", readonly=True, copy=False)
    can_mark_withdrawal_expected = fields.Boolean(string="Can mark an expected withdrawal",
                                                  compute='_compute_can_mark_withdrawal_expected')
    # For the Schedule tab (readonly_schedule_grid): the subjects the student is not expected at,
    # drawn dashed, and the legend explaining why.
    not_expected_subject_ids = fields.Many2many(string="Subjects not required to attend", comodel_name='ems.subject',
                                                compute='_compute_not_expected_schedule')
    not_expected_legend = fields.Char(string="Not required to attend", compute='_compute_not_expected_schedule')

    @api.depends('tutor_id', 'contact_type', 'active')
    @api.depends_context('uid')
    def _compute_can_mark_withdrawal_expected(self):
        """The student's tutor and everyone above them (tutor scope: Department/Seminar Chief,
        JE/JEA, the Director), plus whoever registers withdrawals (secretary, Head of Studies, the
        administrator)."""
        registers_exits = self._ems_user_can_register_exits()
        base = self.env['ems.base']
        for partner in self:
            partner.can_mark_withdrawal_expected = (
                partner.contact_type == 'student' and partner.active
                and (registers_exits or base.user_acts_as_tutor(partner.tutor_id)))

    @api.depends('withdrawal_expected', 'enrollment_ids.subject_id')
    def _compute_not_expected_schedule(self):
        for partner in self:
            if partner.withdrawal_expected:
                partner.not_expected_subject_ids = partner.sudo().enrollment_ids.subject_id
                partner.not_expected_legend = _("Expected withdrawal: not required to attend while it is processed.")
            else:
                partner.not_expected_subject_ids = False
                partner.not_expected_legend = False

    # --- which roll-calls the student is not expected at ----------------------------------------

    @api.model
    def _ems_not_expected_reasons(self, students, subject, start):
        """{student id: session line vals} for the `students` not expected at a class of `subject`
        starting at `start` (naive UTC): the line is created off the roll-call (archived), with the
        reason. One search for the whole roster."""
        expected_withdrawals = students.sudo().filtered(
            lambda student: student.withdrawal_expected and student.withdrawal_expected_date <= start)
        return {student.id: {'active': False, 'not_expected_reason': 'withdrawal'} for student in expected_withdrawals}

    # --- who teaches the student --------------------------------------------------------------

    def _ems_teaching_staff(self, subjects=None):
        """{res.users: ems.subject} - who teaches this student each of their subjects (among
        `subjects` if given), in the group they take it with, plus their group's tutor (with
        every subject). What informative notices about a student go to."""
        self.ensure_one()
        student = self.sudo()
        enrollments = student.enrollment_ids
        if subjects is not None:
            enrollments = enrollments.filtered(lambda enrollment: enrollment.subject_id in subjects)
        groups_by_subject = defaultdict(lambda: self.env['ems.group'])
        for enrollment in enrollments:
            groups_by_subject[enrollment.subject_id] |= enrollment.group_id | enrollment.slot_ids.group_id
        # A subject asked about with no enrollment (a convalidation completed before the student
        # was placed): whoever teaches it in their main group.
        for subject in (subjects or self.env['ems.subject']) - enrollments.subject_id:
            groups_by_subject[subject] |= student.main_group_id
        all_groups = self.env['ems.group'].union(*groups_by_subject.values())
        teachings = self.env['ems.teaching'].sudo().search([
            ('subject_id', 'in', list({subject.id for subject in groups_by_subject})),
            ('group_id', 'in', all_groups.ids), ('active', '=', True),
        ])
        staff = defaultdict(lambda: self.env['ems.subject'])
        for teaching in teachings:
            if teaching.group_id in groups_by_subject[teaching.subject_id] and teaching.teacher_id.user_id:
                staff[teaching.teacher_id.user_id] |= teaching.subject_id
        tutor_user = (student.tutor_id or student.main_group_id.tutor_id).user_id
        if tutor_user:
            staff[tutor_user] |= self.env['ems.subject'].union(*groups_by_subject)
        return dict(staff)

    def _ems_queue_staff_notice(self, compose, subjects=None):
        """Queues an informative notice about this student for whoever teaches them (and their
        tutor): it reaches them in their daily summary. `compose(user, subjects)` writes it in the
        user's language (the student comes as `self.with_context(lang=user.lang)`)."""
        self.ensure_one()
        Notice = self.env['ems.info_notice']
        for user, user_subjects in self._ems_teaching_staff(subjects).items():
            student = self.sudo().with_context(lang=user.lang or self.env.lang)
            Notice._ems_queue(user, student, lambda recipient, student=student, user_subjects=user_subjects:
                              compose(student, user_subjects))

    # --- mark / revert ------------------------------------------------------------------------

    def _ems_check_can_mark_withdrawal_expected(self):
        for partner in self:
            if not partner.can_mark_withdrawal_expected:
                raise UserError(_("Only the student's tutor, the secretary, the head of studies or an administrator "
                                  "can mark or revert an expected withdrawal."))

    def action_withdrawal_expected_wizard(self):
        self.ensure_one()
        self._ems_check_can_mark_withdrawal_expected()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Mark expected withdrawal"),
            'res_model': 'ems.withdrawal_expected_wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_student_id': self.id},
        }

    def _ems_mark_withdrawal_expected(self, note=False):
        """From now on the student is not expected at any roll-call; the sessions already taken
        from this moment on (later today) take them off too."""
        self._ems_check_can_mark_withdrawal_expected()
        now = fields.Datetime.now()
        removable = self.env['ems.attendance_status']
        for xmlid in REMOVABLE_STATUS_XMLIDS:
            removable |= self.env.ref(xmlid)
        for student in self.sudo():
            if student.withdrawal_expected:
                continue
            student.write({
                'withdrawal_expected': True,
                'withdrawal_expected_date': now,
                'withdrawal_expected_by_id': self.env.user.id,
                'withdrawal_expected_note': note,
            })
            lines = self.env['ems.attendance_session_line'].sudo().search([
                ('student_id', '=', student.id), ('attendance_session_id.start_date', '>=', now),
                ('status_id', 'in', removable.ids), ('attendance_justification_id', '=', False),
                ('strike_ids', '=', False)])
            for line in lines:  # one at a time: see _ems_restore_not_expected_lines
                line.write({'active': False, 'not_expected_reason': 'withdrawal'})
            student._ems_queue_staff_notice(lambda student, subjects: Markup("<p>{}</p>").format(student.env._(
                "%(tutor)s has asked for the withdrawal of %(student)s. While it is processed, they no longer "
                "appear in your roll-calls as expected (they show greyed out, \"not required to attend\").",
                tutor=self.env.user.name, student=student.name)))

    def action_revert_withdrawal_expected(self):
        """The student is expected again: every session they were taken off for the expected
        withdrawal becomes an absence (or stays justified, if the tutor had justified it), without
        notifying the family - the tutor sees them in their daily summary."""
        self._ems_check_can_mark_withdrawal_expected()
        for student in self.sudo().filtered('withdrawal_expected'):
            student.write({
                'withdrawal_expected': False,
                'withdrawal_expected_date': False,
                'withdrawal_expected_by_id': False,
                'withdrawal_expected_note': False,
            })
            student._ems_restore_not_expected_lines([('not_expected_reason', '=', 'withdrawal')])
            student._ems_queue_staff_notice(lambda student, subjects: Markup("<p>{}</p>").format(student.env._(
                "The expected withdrawal of %(student)s has been reverted: they appear in your roll-calls again, "
                "and the sessions they were not required to attend count as absences.", student=student.name)))
        return True

    def _ems_restore_not_expected_lines(self, domain):
        """Puts back on the roll-call this student's session lines taken off for a reason
        (`domain` narrows which), as absences."""
        self.ensure_one()
        Line = self.env['ems.attendance_session_line'].sudo().with_context(active_test=False, ems_skip_family_notification=True)
        lines = Line.search([('student_id', '=', self.id), ('active', '=', False)] + domain)
        miss = self.env.ref('ems.attendance_status_miss')
        # One line at a time: a session line's write() works out its notifications for one line.
        for line in lines:
            vals = {'active': True, 'not_expected_reason': False}
            if not (line.attendance_prevision_id or line.attendance_justification_id):
                vals['status_id'] = miss.id
            line.write(vals)
        return lines

    def _ems_clear_withdrawal_expected(self):
        """The withdrawal (or any exit) is registered: the mark has done its job. Its session lines
        stay off the roll-call."""
        self.sudo().filtered('withdrawal_expected').write({
            'withdrawal_expected': False,
            'withdrawal_expected_date': False,
            'withdrawal_expected_by_id': False,
            'withdrawal_expected_note': False,
        })


class EmsWithdrawalExpectedWizard(models.TransientModel):
    _name = 'ems.withdrawal_expected_wizard'
    _description = "Mark an expected withdrawal"

    student_id = fields.Many2one(string="Student", comodel_name='res.partner', required=True, readonly=True)
    note = fields.Text(string="Note")

    def action_confirm(self):
        self.ensure_one()
        self.student_id._ems_mark_withdrawal_expected(self.note)
        return {'type': 'ir.actions.act_window_close'}
