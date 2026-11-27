# -*- coding: utf-8 -*-

from collections import defaultdict

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from ..shared import base
from psycopg2 import IntegrityError

# The three ordinary evaluations and the extraordinary one (2a convocatòria), the last round:
# it carries over the outcomes passed in the ordinary ones (issue #878).
grade_round_selection = [("1", "1a"), ("2", "2a"), ("3", "3a"), ("4", "Extraordinary evaluation")]
grade_state_selection = [("open", "Open"), ("board", "Board"), ("published", "Published"), ("final", "Finalised")]
# Fields only the Head of Studies (or an administrator) may change on a session: its place in the
# evaluation calendar and what teachers may do in it (issue #878).
MANAGED_FIELDS = {"state", "claim_date_from", "claim_date_to", "allow_provisional"}

class EmsGradeSession(models.Model):
    _name = "ems.grade_session"
    _description = "Grade session: student grading per learning outcome for a group, subject and round."
    _inherit = ['ems.base']
    _sql_constraints = [
        (
            'grade_session_is_duped',
            'UNIQUE(group_id, subject_id, round)',
            'A grade session already exists for this group, subject and round.' # Translated within 'create'.
        )
    ]

    group_id = fields.Many2one(string="Group", comodel_name="ems.group", required=True)
    subject_id = fields.Many2one(string="Subject", comodel_name="ems.subject", required=True)
    allowed_subject_ids = fields.Many2many(related="group_id.study_id.subject_ids", store=False)
    round = fields.Selection(string="Round", selection=grade_round_selection, default="1", required=True)
    state = fields.Selection(string="State", selection=grade_state_selection, default="open", required=True, tracking=True)
    claim_date_from = fields.Date(string="Claims from", help="First day students may claim a grade of this session once it is published.")
    claim_date_to = fields.Date(string="Claims until", help="Last day students may claim a grade of this session.")
    allow_provisional = fields.Boolean(string="Provisional grades allowed", default=True, help="Teachers may mark a learning outcome's grade as provisional.")
    teacher_id = fields.Many2one(string="Teacher", comodel_name="hr.employee", domain="[('employee_type', '=', 'teacher')]", default=lambda self: self._default_teacher_id())

    planning_id = fields.Many2one(string="Planning", comodel_name="ems.planning", compute="_compute_planning_id", store=True)
    has_planning = fields.Boolean(string="Has planning", compute="_compute_has_planning", store=True)
    can_edit = fields.Boolean(string="Can edit", compute="_compute_can_edit", store=False, help="Whether the current user may edit the grades at the session's current state.")
    can_manage = fields.Boolean(string="Can manage", compute="_compute_can_manage", store=False, help="Whether the current user may change the session's state, claims period and provisional grades.")

    grade_outcome_line_ids = fields.One2many(string="Grades per outcome", comodel_name="ems.grade_outcome_line", inverse_name="grade_session_id")
    grade_subject_line_ids = fields.One2many(string="Subject grades", comodel_name="ems.grade_subject_line", inverse_name="grade_session_id")

    @api.depends("group_id.study_id", "subject_id")
    def _compute_planning_id(self):
        for session in self:
            session.planning_id = False
            if session.group_id.study_id and session.subject_id:
                # Live grade sessions only ever target the current course (issue #503) - once
                # ems.planning is course-scoped, an unscoped search could pick up a different
                # year's ponderations for the same study+subject.
                session.planning_id = self.env["ems.planning"].search([
                    ("study_id", "=", session.group_id.study_id.id),
                    ("subject_id", "=", session.subject_id.id),
                    ("course_id", "=", session.env.company.current_course_id.id),
                ], limit=1) or False

    @api.depends("planning_id")
    def _compute_has_planning(self):
        for session in self:
            session.has_planning = bool(session.planning_id)

    @api.depends_context("uid")
    @api.depends("state", "group_id")
    def _compute_can_edit(self):
        # open: everyone in scope; board: only the group's tutor (and admin); published and final:
        # only admin (issue #879 lets an accepted claim correct a published grade).
        # "In scope" mirrors the line rules (security/rules/grading.xml): the session's teacher (or
        # whoever created it) and the group's tutor scope. Whoever only reads every session (the
        # Head of Studies, the secretariat) must not be offered an editable grid it cannot save.
        user = self.env.user
        is_admin = user.has_group("ems.group_academic_admin")
        for session in self:
            is_tutor = base.EmsBase.user_acts_as_tutor(self, session.group_id.tutor_id)
            if is_admin:
                session.can_edit = True
            elif session.state == "open":
                session.can_edit = is_tutor or session.create_uid == user or user in session.teacher_id.sudo().acting_user_ids
            elif session.state == "board":
                session.can_edit = is_tutor
            else:
                session.can_edit = False

    @api.depends_context("uid")
    def _compute_can_manage(self):
        self.can_manage = self._ems_user_manages_sessions()

    def _ems_check_can_edit(self, student=None):
        """Raise the reason the current user may not edit this session's grades (see can_edit).
        Shared by the outcome and subject lines' write(), which pass the line's student: while the
        session is open or in the board, the tutor who follows the student may edit their grades
        too, whatever group the session is (issue #878: a 2nd-year student's 1st-year module)."""
        for session in self:
            if session.can_edit:
                continue
            if (student and session.state in ("open", "board")
                    and base.EmsBase.user_acts_as_tutor(self, student.tutor_id)):
                continue
            if session.state == "final":
                raise UserError(_("This evaluation session is final; only administrators can edit the grades."))
            if session.state == "published":
                raise UserError(_("The grades of this evaluation session are published; only administrators can edit them."))
            raise UserError(_("This evaluation session is in the board stage; only the group's tutor (or an administrator) can edit the grades."))

    @api.depends("group_id", "subject_id", "round")
    def _compute_display_name(self):
        labels = dict(self._fields["round"]._description_selection(self.env))
        for session in self:
            session.display_name = f"{session.group_id.name or ''} {session.subject_id.display_name or ''} ({labels.get(session.round, '')})"

    @api.constrains("claim_date_from", "claim_date_to")
    def _check_claim_dates(self):
        for session in self:
            if session.claim_date_from and session.claim_date_to and session.claim_date_from > session.claim_date_to:
                raise ValidationError(_("The claims period cannot end before it starts."))

    @api.onchange("group_id", "subject_id", "round")
    def _onchange_fill_students(self):
        for session in self:
            session.fill_students()

    def _default_teacher_id(self):
        return self.env["hr.employee"].search([("user_id", "=", self.env.uid), ("employee_type", "=", "teacher")]) or False

    @api.model
    def _derive_teacher(self, group, subject):
        # The canonical teacher for a (group, subject) is the active ems.teaching entry; if there is
        # none, the group's tutor evaluates it; otherwise it is left empty to be assigned later.
        teaching = self.env["ems.teaching"].search([
            ("group_id", "=", group.id),
            ("subject_id", "=", subject.id),
            ("active", "=", True),
        ], limit=1)
        # Always return an hr.employee recordset (possibly empty) so callers can use `.id` safely.
        return teaching.teacher_id or group.tutor_id

    def fill_students(self):
        for session in self:
            students = self.env["ems.enrollment"].search([
                ("group_id", "=", session.group_id.id),
                ("subject_id", "=", session.subject_id.id)
            ]).mapped("student_id")
            session.grade_outcome_line_ids = [(5, 0, 0)]
            session.grade_subject_line_ids = [(5, 0, 0)]
            session._ems_add_students_lines(students)

    def _ems_add_student_lines(self, student):
        """Add 'student's grade lines to this session (see _ems_add_students_lines)."""
        self._ems_add_students_lines(student)

    def _ems_add_students_lines(self, students):
        """Add the grade lines (subject + per-outcome) of 'students' to this session, carrying
        over passed-outcome scores from earlier rounds. Idempotent (a student who already has
        lines here is skipped) and leaves every other student's lines untouched, so it is safe
        to call incrementally (e.g. when a new ems.enrollment is created for this group+subject)
        without wiping grades other students already have. Every line is written in one go:
        one student at a time made each write recompute the whole session (issue #878)."""
        self.ensure_one()
        students = students - self.grade_subject_line_ids.student_id
        if not students:
            return

        # The outcomes to grade come from the planning; if there's no planning yet, fall back to the subject's outcomes.
        outcomes = self.planning_id.planning_outcome_ids.mapped("outcome_id") or self.subject_id.outcome_ids

        # Every evaluated outcome from an earlier round of the same group and subject is carried over:
        # the new line starts from the score of the most recent earlier round. Passed outcomes stay
        # locked (see grade_outcome_line.is_locked); failed ones are editable but keep their previous
        # score as a starting point. One search for every student.
        previous_scores = {}
        if self.group_id and self.subject_id and self.round:
            best_round = {}
            for line in self.env["ems.grade_outcome_line"].search([
                ("student_id", "in", students.ids),
                ("grade_session_id.group_id", "=", self.group_id.id),
                ("grade_session_id.subject_id", "=", self.subject_id.id),
                ("grade_session_id.round", "<", self.round),
                ("is_scored", "=", True),
            ]):
                key = (line.student_id.id, line.outcome_id.id)
                line_round = line.grade_session_id.round
                # round is a single-digit selection, so a string comparison is enough to keep the latest.
                if key not in best_round or line_round > best_round[key]:
                    best_round[key] = line_round
                    previous_scores[key] = line.score

        outcome_cmds = []
        subject_cmds = []
        convalidation = self.env["ems.convalidation.line"]
        for student in students:
            for outcome in outcomes:
                vals = {
                    "student_id": student.id,
                    "outcome_id": outcome.id,
                    "is_auto_generated": True,
                }
                previous = previous_scores.get((student.id, outcome.id))
                if previous is not None:
                    vals["score"] = previous
                    vals["is_scored"] = True
                outcome_cmds.append((0, 0, vals))
            convalidation_grade = convalidation._ems_convalidation_grade(student, self.subject_id)
            subject_cmds.append((0, 0, {
                "student_id": student.id,
                "is_convalidated": convalidation_grade is not None,
                "convalidation_grade": convalidation_grade or 0,
            }))
        self.write({"grade_subject_line_ids": subject_cmds, "grade_outcome_line_ids": outcome_cmds})

    @api.model
    def _ems_has_scored_grades(self, student_id, group_id, subject_id):
        """Whether 'student_id' already has any grade informed (a scored outcome, or an external
        grade) in a grade session for 'group_id'+'subject_id', in any round or state. Used to
        block deleting the underlying ems.enrollment once evaluation has actually started."""
        domain = [
            ("student_id", "=", student_id),
            ("grade_session_id.group_id", "=", group_id),
            ("grade_session_id.subject_id", "=", subject_id),
        ]
        # sudo() (issue #435): this is a safety guard, so it must see every grade line, not only
        # the ones its caller happens to be allowed to read - a teacher only sees their own
        # sessions (rule_grade_session_teacher_own, security/rules/grading.xml), which would let
        # a secretary-who-also-teaches delete an enrollment already carrying another teacher's
        # grades. Same reasoning as ems.enrollment._ems_attended_lines().
        if self.env["ems.grade_outcome_line"].sudo().search_count(domain + [("is_scored", "=", True)]):
            return True
        return bool(self.env["ems.grade_subject_line"].sudo().search_count(domain + [("external_is_scored", "=", True)]))

    def reload_students(self):
        self.fill_students()

    @api.model
    def apply_grade_changes(self, outcome_vals, subject_vals):
        # Batch-write the buffered edits from the tutor view in a single request. Each line carries its own
        # values, so the client cannot merge them into one ORM write; grouping them here turns what used to
        # be one RPC per changed line into a single round trip. Outcome lines are written before subject
        # lines so the subject grades recompute from the new outcome scores. The per-line write() overrides
        # still enforce the locking and state rules. Computed fields recompute once at flush.
        OutcomeLine = self.env["ems.grade_outcome_line"]
        for line_id, vals in outcome_vals.items():
            OutcomeLine.browse(int(line_id)).write(vals)
        SubjectLine = self.env["ems.grade_subject_line"]
        for line_id, vals in subject_vals.items():
            SubjectLine.browse(int(line_id)).write(vals)
        return True

    def action_open_state_wizard(self):
        # The form's Actions entry: an object method, so the wizard gets this record only (a
        # type="action" button would send the pager's whole list as active_ids).
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id("ems.action_grade_session_state_wizard")
        action["context"] = {"active_model": self._name, "active_ids": self.ids}
        return action

    @api.model_create_multi
    def create(self, vals_list):
        try:
            return super().create(vals_list)
        except IntegrityError as e:
            raise e if "grade_session_is_duped" not in str(e) else ValidationError(_('A grade session already exists for this group, subject and round. Please edit the existing one.'))

    @api.model
    def _ems_user_manages_sessions(self):
        return self.env.user.has_group("ems.group_academic_admin") or self.env.user.has_group("ems.group_head_of_studies")

    def _ems_check_state_change(self, new_state):
        """A session moves one step at a time, forwards or backwards (issue #878): open, board,
        published, final. Publishing needs the claims period, which is when students may claim."""
        order = [state for state, _label in grade_state_selection]
        labels = dict(self._fields["state"]._description_selection(self.env))
        for session in self:
            if session.state == new_state:
                continue
            if abs(order.index(new_state) - order.index(session.state)) != 1:
                raise UserError(_("%(session)s is %(state)s: it can only move to the previous or the next state, not to %(new)s.",
                                  session=session.display_name, state=labels[session.state], new=labels[new_state]))
            if new_state == "published" and not (session.claim_date_from and session.claim_date_to):
                raise UserError(_("%(session)s has no claims period: set it before publishing the grades.",
                                  session=session.display_name))

    def _ems_empty_grades_summary(self):
        """One line per session that still has empty outcome grades, for the warning shown before
        publishing. Publishing is not blocked: not every outcome is evaluated in every round. A
        convalidated subject's outcomes are never graded, so they don't count. Two queries for
        every session together."""
        convalidated = {
            (line.grade_session_id.id, line.student_id.id)
            for line in self.env["ems.grade_subject_line"].sudo().search([
                ("grade_session_id", "in", self.ids), ("is_convalidated", "=", True)])
        }
        empty = defaultdict(int)
        for session, student, count in self.env["ems.grade_outcome_line"].sudo()._read_group([
            ("grade_session_id", "in", self.ids),
            ("is_scored", "=", False),
        ], groupby=["grade_session_id", "student_id"], aggregates=["__count"]):
            if (session.id, student.id) not in convalidated:
                empty[session.id] += count
        return [
            _("%(session)s: %(count)s empty outcome grade(s)", session=session.display_name, count=empty[session.id])
            for session in self if empty[session.id]
        ]

    def write(self, vals):
        if MANAGED_FIELDS & set(vals) and not self._ems_user_manages_sessions():
            raise UserError(_("Only the Head of Studies or an administrator can change the evaluation state, claims period or provisional grades."))
        # The superuser (data migrations, tests building fixtures) may set any state directly.
        if "state" in vals and not self.env.su:
            self._ems_check_state_change(vals["state"])
        if not self.env.user.has_group("ems.group_academic_admin"):
            # Archiving / unarchiving (active) is a write; only administrators may archive or restore sessions.
            if "active" in vals:
                raise UserError(_("Only administrators can archive or delete evaluation sessions."))
        return super().write(vals)
