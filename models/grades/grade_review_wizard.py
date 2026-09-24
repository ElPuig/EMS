# -*- coding: utf-8 -*-

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from ..shared import base

# A grade review is a formal resolution signed once the academic file of a course is already
# closed: the frozen history (ems.student.year_record) is by then the only surviving trace of
# that year, since the course transition deleted the live grade lines it was copied from. This
# wizard is the single write path into it — correcting a subject through its learning outcomes
# (RA), adding a subject the history is missing, or removing one — always leaving the
# resolution, its date and its author on the record and the detail in the student's chatter.
#
# Corrections to the course in progress do NOT belong here: while a course is running the grade
# sessions are the source of truth and the history does not exist yet.


class EmsGradeReviewWizard(models.TransientModel):
    _name = 'ems.grade_review_wizard'
    _description = 'Grade review wizard: post-closure correction of a student academic year record.'

    record_id = fields.Many2one(string="Year record", comodel_name='ems.student.year_record',
                                required=True, ondelete='cascade')
    student_id = fields.Many2one(string="Student", related='record_id.student_id')
    course_id = fields.Many2one(string="Course", related='record_id.course_id')
    study_name = fields.Char(string="Study", related='record_id.study_name')
    operation = fields.Selection(string="Operation", required=True, default='correct', selection=[
        ('correct', 'Correct a subject'),
        ('add', 'Add a missing subject'),
        ('remove', 'Remove a subject'),
    ])
    subject_record_id = fields.Many2one(string="Subject", ondelete='cascade',
                                        comodel_name='ems.student.year_record.subject')
    subject_id = fields.Many2one(string="Subject to add", comodel_name='ems.subject',
                                 ondelete='cascade')
    # Subjects of the record's study not taken that course yet: what 'add' may pick from (the
    # view points subject_id's domain at this field).
    available_subject_ids = fields.Many2many(string="Available subjects", comodel_name='ems.subject',
                                             compute='_compute_available_subject_ids')
    # Weights of the subject being corrected or added. Editable only while adding: a correction
    # never touches the weights frozen from the teaching plan in force that course.
    internal_weight = fields.Float(string="Internal weight (%)", default=100.0)
    external_weight = fields.Float(string="Work placement weight (%)")
    line_ids = fields.One2many(string="Learning outcomes",
                               comodel_name='ems.grade_review_wizard.line',
                               inverse_name='wizard_id')
    review_date = fields.Date(string="Review date", required=True,
                              default=fields.Date.context_today)
    resolution = fields.Text(string="Resolution", required=True,
                             help="What the review resolves. Kept on the record and posted "
                                  "in the student's chatter.")
    # The same "calculated vs. applied" shape as line_ids' previous_score/score (issue #503):
    # preview_internal_grade_calculated always shows what the outcome grid above yields, and
    # preview_internal_grade - the value actually applied - starts equal to it but can be typed
    # over by hand, e.g. to correct a small rounding-type mismatch against Esfera without having
    # to reverse-engineer fake RA scores. There is no user-facing checkbox: "is this overridden"
    # is simply "does the applied value currently differ from the calculated one" (see
    # _check_override_internal_grade and _apply_internal_grade_override below), which needs no
    # bookkeeping flag at all. preview_internal_grade_synced is the one flag that IS still
    # needed, purely for _compute_preview_internal_grade's own "should I keep auto-following the
    # calculated value" decision (see its comment - an @api.onchange cannot do this: Odoo's
    # onchange dispatch re-fires an onchange registered on a field even when a *compute*, not the
    # user, changed that field's value, so it cannot tell the two apart).
    preview_internal_grade_calculated = fields.Integer(
        string="Internal grade (calculated)", compute='_compute_preview_internal_grade_calculated',
        help="The internal grade computed from the learning outcomes above.")
    preview_internal_grade = fields.Integer(
        string="Internal grade (applied)", compute='_compute_preview_internal_grade',
        store=True, readonly=False,
        help="The internal grade that will actually be applied to the subject. Starts equal to "
             "the calculated value; type a different one to correct it by hand - e.g. to match "
             "a value already recorded in Esfera. It cannot change whether the subject is "
             "passed or not passed.")
    # Technical/bookkeeping only, not shown in the view: the calculated value that was last
    # auto-pushed into preview_internal_grade. See _compute_preview_internal_grade.
    preview_internal_grade_synced = fields.Integer(string="Internal grade last synced")
    preview_state = fields.Selection(string="State", compute='_compute_preview', selection=[
        ('failed', 'Not passed'),
        ('passed', 'Passed'),
    ])
    preview_final_grade = fields.Integer(string="Final grade", compute='_compute_preview')
    preview_has_final = fields.Boolean(string="Has final", compute='_compute_preview')
    current_result = fields.Selection(string="Current course result",
                                      related='record_id.academic_result')
    proposed_result = fields.Selection(string="Proposed course result", compute='_compute_preview',
                                       selection=[
                                           ('full', 'Fully passed'),
                                           ('partial', 'Partially passed'),
                                           ('repeating', 'Repeating'),
                                           ('withdrawn', 'Withdrawn'),
                                       ])
    update_result = fields.Boolean(string="Update the course result", default=True,
                                   help="Write the proposed academic result on the course "
                                        "record once the review is applied.")

    @api.depends('record_id')
    def _compute_available_subject_ids(self):
        for wizard in self:
            taken = wizard.record_id.subject_record_ids.subject_id
            domain = [('id', 'not in', taken.ids)]
            if wizard.record_id.study_id:
                domain.append(('study_ids', '=', wizard.record_id.study_id.id))
            wizard.available_subject_ids = self.env['ems.subject'].search(domain)

    @api.depends('record_id', 'operation', 'subject_record_id', 'subject_id', 'line_ids.score',
                 'line_ids.is_scored', 'line_ids.weight', 'internal_weight', 'external_weight')
    def _compute_preview_internal_grade_calculated(self):
        for wizard in self:
            if wizard.operation == 'remove' or not (
                    wizard.subject_record_id if wizard.operation == 'correct' else wizard.subject_id):
                wizard.preview_internal_grade_calculated = 0
                continue
            wizard.preview_internal_grade_calculated = wizard._subject_values()['internal_grade']

    @api.depends('preview_internal_grade_calculated')
    def _compute_preview_internal_grade(self):
        # Kept apart from _compute_preview below (which computes state/final_grade/has_final):
        # a plain write to preview_internal_grade (typing a forced value) does not re-trigger
        # the method that OUTPUTS it, only methods that DEPEND on it - so preview_final_grade
        # must live in a separate method that lists preview_internal_grade as a dependency (see
        # its own comment), same split ems.grade_subject_line already uses for
        # internal_score/computed_score.
        #
        # "Should I keep auto-following the calculated value?" is answered by comparing the
        # CURRENT applied value against preview_internal_grade_synced - the calculated value we
        # last pushed here ourselves. Equal means nothing has touched it since (either it was
        # never touched, or the user last typed exactly what we'd already pushed) - keep
        # following. Different means the user typed something else after that last push - leave
        # it alone. This cannot be a plain "does applied differ from calculated right now" check
        # instead: on the very first pass after a fresh subject is picked, applied is still 0
        # while calculated is already the real value, which would look like a "divergence" too
        # and the initial seed would never happen.
        for wizard in self:
            if wizard.preview_internal_grade != wizard.preview_internal_grade_synced:
                continue
            wizard.preview_internal_grade = wizard.preview_internal_grade_calculated
            wizard.preview_internal_grade_synced = wizard.preview_internal_grade_calculated

    @api.depends('record_id', 'operation', 'subject_record_id', 'subject_id', 'line_ids.score',
                 'line_ids.is_scored', 'line_ids.weight', 'internal_weight', 'external_weight',
                 'preview_internal_grade')
    def _compute_preview(self):
        for wizard in self:
            wizard.preview_state = False
            wizard.preview_final_grade = 0
            wizard.preview_has_final = False
            wizard.proposed_result = wizard.record_id.academic_result
            if wizard.operation == 'remove':
                if wizard.subject_record_id:
                    wizard.proposed_result = wizard._result_after(
                        wizard.record_id.subject_record_ids - wizard.subject_record_id, None)
                continue
            if not (wizard.subject_record_id if wizard.operation == 'correct' else wizard.subject_id):
                # Nothing picked yet: a preview computed from an empty grid would only read as
                # a "Not passed" the user never asked for.
                continue
            values = wizard._subject_values()
            wizard.preview_state = values['state']
            # Final grade/has_final always derive from whatever preview_internal_grade IS NOW
            # (forced or computed) - never from values['final_grade'], which was computed from
            # the un-overridden internal grade and would silently ignore a forced value.
            wizard.preview_final_grade, wizard.preview_has_final = self.env[
                'ems.grade_subject_line']._final_from_parts(
                wizard.preview_internal_grade, True,
                wizard.subject_record_id.external_grade, wizard.subject_record_id.external_is_scored,
                wizard.internal_weight, wizard.external_weight)
            others = wizard.record_id.subject_record_ids - wizard.subject_record_id
            wizard.proposed_result = wizard._result_after(others, values['state'])

    @api.constrains('preview_internal_grade', 'preview_internal_grade_calculated')
    def _check_override_internal_grade(self):
        # The applied value can correct the exact number, but must never flip whether the
        # subject is actually passed - that stays whatever the learning outcomes (RA) say,
        # untouched by the override (issue #503). Nothing to check when it matches the
        # calculated value: nothing was actually forced.
        for wizard in self:
            if wizard.preview_internal_grade == wizard.preview_internal_grade_calculated:
                continue
            if wizard.preview_internal_grade < 0 or wizard.preview_internal_grade > 10:
                raise ValidationError(_("The forced internal grade must be within the range [0, 10]."))
            passed = wizard.preview_internal_grade >= 5
            if passed and wizard.preview_state != 'passed':
                raise ValidationError(_(
                    "At least one learning outcome is below 5, so the subject is not passed - "
                    "the forced internal grade must also stay below 5."))
            if not passed and wizard.preview_state == 'passed':
                raise ValidationError(_(
                    "Every learning outcome is at 5 or above, so the subject is passed - the "
                    "forced internal grade must also stay at 5 or above."))

    @api.onchange('operation')
    def _onchange_operation(self):
        for wizard in self:
            if wizard.operation != 'add':
                wizard.subject_id = False
            if wizard.operation == 'add':
                wizard.subject_record_id = False
            wizard._fill_lines()

    @api.onchange('subject_record_id')
    def _onchange_subject_record_id(self):
        for wizard in self:
            wizard._fill_lines()

    @api.onchange('subject_id')
    def _onchange_subject_id(self):
        for wizard in self:
            wizard._fill_lines()

    def _fill_lines(self):
        """(Re)build the outcome grid from whatever the wizard is pointing at: the frozen
        outcomes of the subject being corrected, or the teaching plan of the subject being
        added."""
        self.ensure_one()
        # A newly picked subject (or operation) starts fresh: resetting both to 0 makes the next
        # _compute_preview_internal_grade pass see them as still in sync (0 == 0) and re-seed the
        # applied grade from THIS subject's own calculated value, instead of carrying over
        # whatever was typed for a previous subject.
        self.preview_internal_grade = 0
        self.preview_internal_grade_synced = 0
        if self.operation == 'correct' and self.subject_record_id:
            self.internal_weight = self.subject_record_id.internal_weight
            self.external_weight = self.subject_record_id.external_weight
            self.line_ids = [(5, 0, 0)] + [(0, 0, {
                'outcome_record_id': outcome.id,
                'outcome_id': outcome.outcome_id.id,
                'score': outcome.final_score,
                'is_scored': outcome.final_is_scored,
            }) for outcome in self.subject_record_id.outcome_record_ids]
        elif self.operation == 'add' and self.subject_id:
            # Scoped to the record's own course (issue #503): a correction on an old course must
            # use the ponderations that were actually in force then, not today's, once
            # ems.planning is course-scoped.
            planning = self.env['ems.planning'].search([
                ('study_id', '=', self.record_id.study_id.id),
                ('subject_id', '=', self.subject_id.id),
                ('course_id', '=', self.record_id.course_id.id)], limit=1)
            self.internal_weight = planning.internal_ponderation or 100.0
            self.external_weight = planning.external_ponderation
            self.line_ids = [(5, 0, 0)] + [(0, 0, {
                'outcome_id': planning_outcome.outcome_id.id,
                'weight': planning_outcome.ponderation,
                'score': 0,
                'is_scored': False,
            }) for planning_outcome in planning.planning_outcome_ids]
        else:
            self.line_ids = [(5, 0, 0)]

    def _subject_values(self):
        """The internal grade, state and final grade the wizard's grid yields, through the very
        same helper that writes them (ems.student.year_record.subject._values_from_outcomes)."""
        self.ensure_one()
        scored = self.line_ids.filtered('is_scored')
        return self.env['ems.student.year_record.subject']._values_from_outcomes(
            [(line.score, line.weight) for line in scored], len(self.line_ids),
            self.subject_record_id.external_grade, self.subject_record_id.external_is_scored,
            self.internal_weight, self.external_weight)

    def _result_after(self, other_subject_records, state):
        """The academic result the record would show once this grade review is applied: the state
        of the subject being corrected or added (None when it is being removed) plus the state
        of every other subject, run through the record's own rule."""
        self.ensure_one()
        if self.record_id.academic_result in ('withdrawn', 'repeating'):
            return self.record_id.academic_result
        states = [subject_record.state for subject_record in other_subject_records]
        if state:
            states.append(state)
        if not states:
            return self.record_id.academic_result
        return 'full' if all(subject_state == 'passed' for subject_state in states) else 'partial'

    def action_apply(self):
        """Apply the review, stamp it on the record and post its detail in the student's
        chatter."""
        self.ensure_one()
        self._check_can_review()
        # A course still running is corrected in its grade sessions, not here (see the module
        # header): its record only holds the subjects convalidated so far (issue #276).
        if self.record_id.is_provisional:
            raise UserError(_("This course is still running: correct its grades in the grade "
                              "sessions. A grade review only applies to closed courses."))
        # Read while the record is still whole: 'remove' deletes what the preview is computed
        # from, and reading it afterwards would only raise on a record that no longer exists.
        previous_result = self.record_id.academic_result
        proposed_result = self.proposed_result
        # Everything below writes through _history(): see its docstring.
        changes = getattr(self, f'_apply_{self.operation}')()
        if self.update_result and proposed_result != previous_result:
            changes.append(_("Course result: %(previous)s → %(new)s",
                             previous=self._result_label(previous_result),
                             new=self._result_label(proposed_result)))
            self._history(self.record_id).academic_result = proposed_result
        self._log_review(changes)
        return {'type': 'ir.actions.act_window_close'}

    def _check_can_review(self):
        """Secretariat, academic administration, Head of Studies and Director sign grade reviews.
        Besides restricting the button in the view, this is what gates the elevated writes of
        _history(): the wizard is the only door to a closed history."""
        self.ensure_one()
        ems_base = self.env['ems.base']
        if not (ems_base.get_user_is_secretary() or ems_base.get_user_is_admin()
                or ems_base.get_user_is_head_of_studies()):
            raise UserError(_("Only the secretariat, the academic administration, the Head of "
                              "Studies and the Director may apply a grade review."))

    def _history(self, records):
        """`records` (year record, subject or outcome) with elevated rights.

        A closed academic history is read-only for every role, Head of Studies included: the
        ACL and the record rules grant no write access on it, so it cannot be edited over RPC
        or any other way around this wizard. The wizard writes with sudo, and only after
        _check_can_review. self stays un-elevated, so self.env.user is still the person who
        signs the review."""
        return records.sudo()

    def _apply_internal_grade_override(self, subject_record):
        """After _recompute_from_outcomes() has derived internal_grade/state/final_grade fresh
        from the outcomes, overwrite the internal grade with the reviewer's applied value when
        it was typed differently from the calculated one (issue #503) - lets a small
        Esfera-vs-EMS rounding mismatch be corrected without reverse-engineering fake RA scores.
        'state' is deliberately never touched here: _check_override_internal_grade already blocks saving a
        forced value on the wrong side of 5 relative to what the RAs say, so it is guaranteed
        consistent with the forced value by the time this runs. Reuses is_overridden (already on
        this model, otherwise only ever copied from the live ems.grade_subject_line.is_overridden
        at freeze time and cleared by _recompute_from_outcomes) rather than inventing a new
        field - same "this internal grade isn't purely outcome-derived" meaning either way.

        Returns an audit-trail message for the chatter, or None when nothing was forced."""
        self.ensure_one()
        if self.preview_internal_grade == self.preview_internal_grade_calculated:
            return None
        natural_grade = subject_record.internal_grade
        final_grade, has_final = self.env['ems.grade_subject_line']._final_from_parts(
            self.preview_internal_grade, True,
            subject_record.external_grade, subject_record.external_is_scored,
            subject_record.internal_weight, subject_record.external_weight)
        subject_record.write({
            'internal_grade': self.preview_internal_grade,
            'is_overridden': True,
            'final_grade': final_grade,
            'has_final': has_final,
        })
        return _("Internal grade forced manually: %(forced)s (the learning outcomes would give %(natural)s)",
                 forced=self.preview_internal_grade, natural=natural_grade)

    def _apply_correct(self):
        self.ensure_one()
        if not self.subject_record_id:
            raise UserError(_("Pick the subject the review corrects."))
        # A convalidated subject holds a convalidation resolution, not an evaluation of this
        # centre's own: its grade is changed by resolving the convalidation again (issue #276),
        # never by correcting learning outcomes the student never took here.
        if self.subject_record_id.is_convalidated:
            raise UserError(_("%s is convalidated: change the convalidation resolution instead of "
                              "reviewing its learning outcomes.") % self.subject_record_id.subject_name)
        changes = []
        for line in self.line_ids:
            if line.score == line.previous_score and line.is_scored == line.previous_is_scored:
                continue
            changes.append(_("%(outcome)s: %(previous)s → %(new)s",
                             outcome=line.outcome_name,
                             previous=self._score_label(line.previous_score, line.previous_is_scored),
                             new=self._score_label(line.score, line.is_scored)))
            self._history(line.outcome_record_id).write({'final_score': line.score,
                                                         'final_is_scored': line.is_scored})
        if not changes and self.preview_internal_grade == self.preview_internal_grade_calculated:
            raise UserError(_("The review does not change any learning outcome grade."))
        previous_state = self.subject_record_id.state
        self._history(self.subject_record_id)._recompute_from_outcomes()
        override_message = self._apply_internal_grade_override(self._history(self.subject_record_id))
        changes.append(_("%(subject)s: %(previous)s → %(new)s (grade %(grade)s)",
                         subject=self.subject_record_id.subject_name,
                         previous=self._state_label(previous_state),
                         new=self._state_label(self.subject_record_id.state),
                         grade=self.subject_record_id.internal_grade))
        if override_message:
            changes.append(override_message)
        self._stamp(self.subject_record_id)
        return changes

    def _apply_add(self):
        self.ensure_one()
        if not self.subject_id:
            raise UserError(_("Pick the subject the review adds."))
        subject_record = self._history(self.env['ems.student.year_record.subject']).create({
            'record_id': self.record_id.id,
            'subject_id': self.subject_id.id,
            'subject_name': self.subject_id.display_name,
            'internal_weight': self.internal_weight,
            'external_weight': self.external_weight,
            'outcome_record_ids': [(0, 0, {
                'outcome_id': line.outcome_id.id,
                'outcome_name': line.outcome_name,
                'weight': line.weight,
                'final_score': line.score,
                'final_is_scored': line.is_scored,
            }) for line in self.line_ids],
        })
        subject_record._recompute_from_outcomes()
        override_message = self._apply_internal_grade_override(subject_record)
        result = [_("Subject added: %(subject)s (%(state)s, grade %(grade)s)",
                  subject=subject_record.subject_name,
                  state=self._state_label(subject_record.state),
                  grade=subject_record.internal_grade)]
        if override_message:
            result.append(override_message)
        self._stamp(subject_record)
        return result

    def _apply_remove(self):
        self.ensure_one()
        if not self.subject_record_id:
            raise UserError(_("Pick the subject the review removes."))
        subject_record = self.subject_record_id
        changes = [_("Subject removed: %(subject)s", subject=subject_record.subject_name)]
        # Dropped from the wizard first: any later read of the wizard recomputes the preview,
        # and a preview pointing at an already deleted line would raise instead.
        self.subject_record_id = False
        self._history(subject_record).unlink()
        return changes

    def _stamp(self, subject_record):
        self._history(subject_record).write({
            'review_date': self.review_date,
            'review_user_id': self.env.user.id,
            'review_note': self.resolution,
        })

    def _log_review(self, changes):
        """Post the review in the student's chatter: its date, its author, what it resolves
        and every value it changed. The history itself only keeps the last grade review per
        subject, so the chatter is what makes the whole sequence auditable."""
        self.ensure_one()
        intro = _("Grade review of %(date)s applied by %(user)s on the academic history of "
                  "%(course)s: %(resolution)s",
                  date=fields.Date.to_string(self.review_date), user=self.env.user.name,
                  course=self.record_id.course_id.name, resolution=self.resolution)
        # _message_log, not message_post: this is an automatic audit note on the student, so it
        # needs neither a subtype nor an email address on whoever signed the review.
        self.record_id.student_id._message_log(
            body=Markup("<p>{}</p>").format(intro)
            + base.EmsBase.build_html_list(self, changes))

    def _score_label(self, score, is_scored):
        return str(score) if is_scored else _("not graded")

    def _selection_label(self, model, field_name, value):
        # The reader's own translated label of a selection value, for the chatter entry.
        return dict(self.env[model].fields_get([field_name])[field_name]['selection']).get(value, "")

    def _state_label(self, state):
        return self._selection_label('ems.student.year_record.subject', 'state', state)

    def _result_label(self, result):
        return self._selection_label('ems.student.year_record', 'academic_result', result)


class EmsGradeReviewWizardLine(models.TransientModel):
    _name = 'ems.grade_review_wizard.line'
    _description = 'Grade review wizard: the resolved grade of one learning outcome (RA).'
    # The grid is built in the order of the outcomes it was filled from, and its name is not a
    # stored column to sort on (see _compute_outcome_name).
    _order = 'id asc'

    wizard_id = fields.Many2one(string="Wizard", comodel_name='ems.grade_review_wizard',
                                required=True, ondelete='cascade')
    # Empty while adding a subject: there is no frozen outcome to write back to yet.
    outcome_record_id = fields.Many2one(string="Outcome record", ondelete='cascade',
                                        comodel_name='ems.student.year_record.outcome')
    outcome_id = fields.Many2one(string="Outcome", comodel_name='ems.outcome', ondelete='cascade')
    # Everything the user does not type is derived, never copied into the line: a field the view
    # shows read-only is not sent back by the client when the wizard is saved, so a plain copy
    # would reach action_apply() empty and the review would read every outcome as changed.
    outcome_name = fields.Char(string="Learning outcome", compute='_compute_outcome_name')
    # Frozen with the outcome being corrected; typed by the user only when adding a subject.
    weight = fields.Float(string="Weight (%)", compute='_compute_weight',
                          store=True, readonly=False)
    previous_score = fields.Integer(string="Current grade",
                                    related='outcome_record_id.final_score')
    previous_is_scored = fields.Boolean(string="Graded before",
                                        related='outcome_record_id.final_is_scored')
    score = fields.Integer(string="Resolved grade")
    is_scored = fields.Boolean(string="Graded")

    @api.depends('outcome_record_id', 'outcome_id')
    def _compute_outcome_name(self):
        for line in self:
            line.outcome_name = line.outcome_record_id.outcome_name \
                or line.outcome_id.display_name

    @api.depends('outcome_record_id')
    def _compute_weight(self):
        for line in self:
            line.weight = line.outcome_record_id.weight

    @api.onchange('score')
    def _onchange_score(self):
        # Typing a grade is what informs the outcome: ticking the box by hand on top of it
        # would only be a way to get it wrong.
        for line in self:
            if line.score:
                line.is_scored = True
