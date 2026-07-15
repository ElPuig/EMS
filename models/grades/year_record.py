# -*- coding: utf-8 -*-

from odoo import api, fields, models

# The year record is a frozen COPY of the grades subsystem output — never recalculated
# here. The single source of truth for grade computation is ems.grade_subject_line /
# ems.grade_outcome_line; this model copies their values (and the planning weights in
# force) at generation time, so the history stays self-contained and verifiable after
# the transition wizard deletes the operational records of the outgoing year.


class EmsStudentYearRecord(models.Model):
    _name = 'ems.student.year_record'
    _description = 'Student academic year record: per-course summary of a student.'
    _order = 'student_id asc, study_id asc, course_id asc'
    _sql_constraints = [
        ('unique_student_course', 'unique (student_id, course_id)',
         'A year record already exists for this student and course!'),
    ]

    student_id = fields.Many2one(string="Student", comodel_name='res.partner',
                                 required=True, ondelete='restrict', index=True)
    course_id = fields.Many2one(string="Course", comodel_name='ems.course',
                                required=True, ondelete='restrict')
    # Snapshot of where the student was that course. The M2o keeps the link while the
    # entity exists; the denormalized name keeps the history readable if it is removed.
    study_id = fields.Many2one(string="Study", comodel_name='ems.study', ondelete='set null')
    study_name = fields.Char(string="Study name")
    level_id = fields.Many2one(string="Level", comodel_name='ems.level', ondelete='set null')
    level_name = fields.Char(string="Level name")
    group_id = fields.Many2one(string="Group", comodel_name='ems.group', ondelete='set null')
    group_name = fields.Char(string="Group name")
    tutor_id = fields.Many2one(string="Tutor", comodel_name='hr.employee', ondelete='set null')
    tutor_name = fields.Char(string="Tutor name")
    shift = fields.Selection(string="Shift", selection=[
        ('morning', 'Morning'),
        ('afternoon', 'Afternoon'),
    ])
    attendance_rate = fields.Float(string="Attendance (%)")
    attendance_issue_count = fields.Integer(
        string="Attendance notifications",
        help="Attendance notifications sent to the family during the course.")
    exit_type = fields.Selection(string="Exit type", selection=[
        ('graduation', 'Graduation'),
        ('withdrawal', 'Withdrawal'),
    ])
    exit_date = fields.Date(string="Exit date")
    # Written by the generator (not computed): admin/secretary may adjust it by hand.
    academic_result = fields.Selection(string="Academic result", selection=[
        ('full', 'Fully passed'),
        ('partial', 'Partially passed'),
        ('repeating', 'Repeating'),
        ('withdrawn', 'Withdrawn'),
    ])
    # Whether the title was obtained this course. Per record (= per study·course):
    # has_graduated alone is a global, permanent mark that does not say which
    # study/course granted the title. Independent of academic_result: a student can
    # pass everything and still have requirements pending.
    title_obtained = fields.Boolean(string="Title obtained", default=False)
    subject_record_ids = fields.One2many(string="Subjects",
                                         comodel_name='ems.student.year_record.subject',
                                         inverse_name='record_id')
    subject_count = fields.Integer(string="Subjects taken", compute='_compute_subject_count')

    @api.depends('subject_record_ids')
    def _compute_subject_count(self):
        for record in self:
            record.subject_count = len(record.subject_record_ids)

    @api.depends('student_id', 'course_id')
    def _compute_display_name(self):
        for record in self:
            record.display_name = \
                f"{record.student_id.display_name or ''} ({record.course_id.name or ''})"

    # --- generation (called by the withdrawal wizard and the transition wizard) ---

    @api.model
    def generate_for_students(self, students, course):
        """Create or refresh the year record of each student for the given course.

        Idempotent on (student_id, course_id): an existing record has its copied
        content replaced instead of being duplicated. Must be called while the
        student still has its main_group_id (i.e. before any ex-student conversion).
        """
        records = self.browse()
        for student in students:
            records |= self._generate_one(student, course)
        return records

    @api.model
    def _generate_one(self, student, course):
        group = student.main_group_id
        attendance_rate, subject_rates = self._attendance_rates(student)
        subject_vals = self._subject_vals(student, subject_rates)
        all_passed = all(vals['state'] == 'passed' for vals in subject_vals)
        academic_result, title_obtained = self._academic_result(student, course, all_passed)
        exited_this_course = student.exit_course_id == course
        vals = {
            'student_id': student.id,
            'course_id': course.id,
            'study_id': group.study_id.id,
            'study_name': group.study_id.display_name,
            'level_id': group.level_id.id,
            'level_name': group.level_id.display_name,
            'group_id': group.id,
            'group_name': group.name,
            'tutor_id': group.tutor_id.id,
            'tutor_name': group.tutor_id.name,
            'shift': group.shift,
            'attendance_rate': attendance_rate,
            'attendance_issue_count': self.env['ems.attendance_issue_student'].search_count(
                [('student_id', '=', student.id)]),
            'exit_type': student.exit_type if exited_this_course else False,
            'exit_date': student.exit_date if exited_this_course else False,
            'academic_result': academic_result,
            'title_obtained': title_obtained,
            'subject_record_ids': [(0, 0, vals) for vals in subject_vals],
        }
        record = self.search([('student_id', '=', student.id), ('course_id', '=', course.id)])
        if record:
            record.subject_record_ids.unlink()
            record.write(vals)
        else:
            record = self.create(vals)
        return record

    @api.model
    def _attendance_rates(self, student):
        """Global and per-subject attendance rate (0-100). A status counts as
        assistance when it starts with 'a' (attended/delayed/issue), the same
        criterion as the attendance reports."""
        def rate(lines):
            attended = len([line for line in lines if line.status.startswith('a')])
            return round(100.0 * attended / len(lines), 2) if lines else 0.0

        lines = self.env['ems.attendance_session_line'].search([('student_id', '=', student.id)])
        by_subject = {}
        for line in lines:
            by_subject.setdefault(line.attendance_session_id.subject_id, []).append(line)
        return rate(lines), {subject: rate(subject_lines)
                             for subject, subject_lines in by_subject.items()}

    @api.model
    def _subject_vals(self, student, subject_rates):
        """One dict per subject with a grade line, copied from the LAST round's
        ems.grade_subject_line, freezing the planning weights in force."""
        lines = self.env['ems.grade_subject_line'].search([('student_id', '=', student.id)])
        vals_list = []
        for subject in lines.mapped('grade_session_id.subject_id'):
            subject_lines = lines.filtered(lambda line: line.grade_session_id.subject_id == subject)
            # round is a single-digit selection, so a string comparison is enough.
            last = max(subject_lines, key=lambda line: line.grade_session_id.round)
            outcome_vals, state = self._outcome_vals_and_state(student, subject)
            vals_list.append({
                'subject_id': subject.id,
                'subject_name': subject.display_name,
                'internal_weight': last.internal_ponderation,
                'external_weight': last.external_ponderation,
                'internal_grade': last.internal_score,
                'is_overridden': last.is_overridden,
                'external_grade': last.external_score,
                'external_is_scored': last.external_is_scored,
                'final_grade': last.final_score,
                'has_final': last.has_final,
                'state': state,
                'notes': last.notes,
                'attendance_rate': subject_rates.get(subject, 0.0),
                'outcome_record_ids': [(0, 0, vals) for vals in outcome_vals],
            })
        return vals_list

    @api.model
    def _outcome_vals_and_state(self, student, subject):
        """One dict per learning outcome (RA) with its scores by round, plus the
        subject's binary state: passed when every RA resolves >= 5, failed when
        some RA fails (or is never scored) after all rounds. The state depends
        ONLY on the RAs — a pending or failed work placement (EM) never fails a
        subject: the student repeats the placement, not the subject."""
        lines = self.env['ems.grade_outcome_line'].search([
            ('student_id', '=', student.id),
            ('grade_session_id.subject_id', '=', subject.id)])
        vals_list = []
        state = 'passed' if lines else 'failed'
        for outcome in lines.mapped('outcome_id'):
            outcome_lines = lines.filtered(lambda line: line.outcome_id == outcome).sorted(
                key=lambda line: line.grade_session_id.round)
            vals = {
                'outcome_id': outcome.id,
                'outcome_name': outcome.display_name,
                'weight': outcome_lines[-1].ponderation,
            }
            final_score = 0
            final_is_scored = False
            for line in outcome_lines:
                session_round = line.grade_session_id.round
                vals[f'round{session_round}_score'] = line.score
                vals[f'round{session_round}_is_scored'] = line.is_scored
                if line.is_scored:
                    # Rounds are visited in order: the resolved grade is the last scored one.
                    final_score = line.score
                    final_is_scored = True
            vals.update({'final_score': final_score, 'final_is_scored': final_is_scored})
            if not final_is_scored or final_score < 5:
                state = 'failed'
            vals_list.append(vals)
        return vals_list, state

    @api.model
    def _academic_result(self, student, course, all_passed):
        """(academic_result, title_obtained) per the transition plan rules. The
        destination enrollment (confirmed sale.order for the enrollment-default
        course) decides promotion vs repetition; the grades decide full vs partial."""
        if student.exit_type == 'withdrawal' and student.exit_course_id == course:
            return 'withdrawn', False
        if student.has_graduated and student.exit_type == 'graduation' \
                and student.exit_course_id == course:
            return 'full', True
        group = student.main_group_id
        destination = self._destination_order(student, course)
        if destination:
            destination_year = destination.ems_group_id.course \
                or destination.sale_order_template_id.study_year
            if destination.ems_study_id == group.study_id \
                    and destination_year and destination_year == group.course:
                return 'repeating', False
            return ('full' if all_passed else 'partial'), False
        if group.study_id.uses_enrollment_flow:
            # Suspicious: a flow study without destination; listed in the transition preview.
            return 'repeating', False
        # No enrollment flow (e.g. ESO): filled by the September re-import if applicable.
        return False, False

    @api.model
    def _destination_order(self, student, course):
        destination_course = self.env['ems.course'].search(
            [('is_enrollment_default', '=', True)], limit=1)
        if not destination_course or destination_course == course:
            return self.env['sale.order']
        return self.env['sale.order'].search([
            ('partner_id', '=', student.id),
            ('ems_course_id', '=', destination_course.id),
            ('state', '=', 'sale')], limit=1)


class EmsStudentYearRecordSubject(models.Model):
    _name = 'ems.student.year_record.subject'
    _description = 'Student academic year record: one subject taken that course.'
    _order = 'subject_name asc'

    record_id = fields.Many2one(string="Year record", comodel_name='ems.student.year_record',
                                required=True, ondelete='cascade')
    subject_id = fields.Many2one(string="Subject", comodel_name='ems.subject', ondelete='set null')
    subject_name = fields.Char(string="Subject name")
    # Weights frozen from the planning in force when the record was generated.
    internal_weight = fields.Float(string="Internal weight (%)")
    external_weight = fields.Float(string="External weight (%)")
    internal_grade = fields.Integer(string="Internal grade")
    is_overridden = fields.Boolean(string="Overridden", default=False)
    external_grade = fields.Integer(string="External grade (EM)")
    external_is_scored = fields.Boolean(string="External scored", default=False)
    final_grade = fields.Integer(string="Final grade")
    has_final = fields.Boolean(string="Has final", default=False)
    # Binary state determined ONLY by the RAs: a failed or pending work placement (EM)
    # never fails a subject (the student repeats the placement, not the subject).
    # 'Not passed' (not 'Failed'): it also covers RAs never scored, and avoids
    # colliding with the 'Failed' msgid already used by the notification states.
    state = fields.Selection(string="State", selection=[
        ('failed', 'Not passed'),
        ('passed', 'Passed'),
    ])
    final_pending = fields.Boolean(string="Final pending", compute='_compute_final_pending',
                                   store=True,
                                   help="Passed subject whose final grade is still empty, "
                                        "waiting for the work placement (EM) grade.")
    notes = fields.Char(string="Comments")
    attendance_rate = fields.Float(string="Attendance (%)")
    outcome_record_ids = fields.One2many(string="Outcomes",
                                         comodel_name='ems.student.year_record.outcome',
                                         inverse_name='subject_record_id')

    @api.depends('state', 'external_weight', 'has_final')
    def _compute_final_pending(self):
        for subject_record in self:
            subject_record.final_pending = (
                subject_record.state == 'passed'
                and subject_record.external_weight > 0
                and not subject_record.has_final)

    @api.depends('subject_name')
    def _compute_display_name(self):
        for subject_record in self:
            subject_record.display_name = subject_record.subject_name or ""


class EmsStudentYearRecordOutcome(models.Model):
    _name = 'ems.student.year_record.outcome'
    _description = 'Student academic year record: one learning outcome (RA) of a subject.'
    _order = 'outcome_name asc'

    subject_record_id = fields.Many2one(string="Subject record",
                                        comodel_name='ems.student.year_record.subject',
                                        required=True, ondelete='cascade')
    outcome_id = fields.Many2one(string="Outcome", comodel_name='ems.outcome', ondelete='set null')
    outcome_name = fields.Char(string="Outcome name")
    # "The grade as of that round": fill_students() carries the best previous score
    # forward, so each round column shows the standing grade at that point.
    round1_score = fields.Integer(string="Round 1")
    round1_is_scored = fields.Boolean(string="Round 1 scored", default=False)
    round2_score = fields.Integer(string="Round 2")
    round2_is_scored = fields.Boolean(string="Round 2 scored", default=False)
    round3_score = fields.Integer(string="Round 3")
    round3_is_scored = fields.Boolean(string="Round 3 scored", default=False)
    round4_score = fields.Integer(string="Round 4")
    round4_is_scored = fields.Boolean(string="Round 4 scored", default=False)
    final_score = fields.Integer(string="Resolved grade",
                                 help="Grade of the last scored round.")
    final_is_scored = fields.Boolean(string="Resolved scored", default=False)
    # Frozen internal weight of the RA (the subject's RAs sum 100).
    weight = fields.Float(string="Weight (%)")

    @api.depends('outcome_name')
    def _compute_display_name(self):
        for outcome_record in self:
            outcome_record.display_name = outcome_record.outcome_name or ""
