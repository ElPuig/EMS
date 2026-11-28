# -*- coding: utf-8 -*-

from collections import defaultdict

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class EmsGradeOutcomeLine(models.Model):
    _name = "ems.grade_outcome_line"
    _description = "Grade outcome line: a student's score for a single learning outcome within a grade session."
    _order = "student_id asc, outcome_id asc"

    grade_session_id = fields.Many2one(string="Grade session", comodel_name="ems.grade_session", required=True, ondelete="cascade")
    subject_id = fields.Many2one(string="Subject", comodel_name="ems.subject", related="grade_session_id.subject_id", store=False)
    student_id = fields.Many2one(string="Student", comodel_name="res.partner", domain="[('contact_type', '=', 'student')]")
    student_firstname = fields.Char(string="First name", related="student_id.firstname", store=False)
    student_lastname = fields.Char(string="Last name", related="student_id.lastname", store=False)
    image_1920 = fields.Binary(string="Image", related="student_id.image_1920")
    outcome_id = fields.Many2one(string="Outcome", comodel_name="ems.outcome", required=True)
    outcome_acronym = fields.Char(string="Outcome acronym", related="outcome_id.acronym", store=False)
    ponderation = fields.Float(string="Ponderation (%)", compute="_compute_ponderation", store=True)
    score = fields.Integer(string="Score")
    is_scored = fields.Boolean(string="Scored", default=False, help="Whether the score has been informed (an empty score is excluded from the subject grade).")
    is_locked = fields.Boolean(string="Locked", compute="_compute_is_locked", store=False, help="Whether this outcome was already passed (score >= 5) in an earlier round for the same student, group and subject; a passed outcome cannot be re-evaluated.")
    is_lock_released = fields.Boolean(string="Lock released", default=False, help="Set when the official grade import overwrites this line: the cross-round lock is released for this line only, so the imported grade is shown without the padlock. Earlier rounds are left untouched, preserving their history.")
    is_provisional = fields.Boolean(string="Provisional", default=False, help="The teacher marks this grade as provisional (e.g. pending a submission); the student sees it as such. Only when the session allows provisional grades.")
    is_auto_generated = fields.Boolean(default=False)

    # Read by the tutors' view, which may show lines of sessions the tutor cannot read (issue #878).
    allow_provisional = fields.Boolean(string="Provisional grades allowed", related="grade_session_id.allow_provisional")

    # Used only for access-rule filtering.
    teacher_id = fields.Many2one(string="Teacher", related="grade_session_id.teacher_id", store=False)

    @api.depends("grade_session_id.planning_id", "outcome_id")
    def _compute_ponderation(self):
        for line in self:
            planning_outcome = line.grade_session_id.planning_id.planning_outcome_ids.filtered(lambda po: po.outcome_id == line.outcome_id)
            line.ponderation = planning_outcome[:1].ponderation

    @api.depends("student_id", "outcome_id", "grade_session_id.group_id", "grade_session_id.subject_id", "grade_session_id.round", "is_lock_released")
    def _compute_is_locked(self):
        # A passed outcome (score >= 5) from an earlier round of the same group and subject is final: it
        # must not be re-evaluated. This crosses grade sessions, so it is recomputed on read (store=False),
        # like grade_session.can_edit. One query for the whole batch: a search_count per line took 12 s
        # to open a tutor's view of 1,400 lines (issue #878). sudo: it is a safety lock, so it counts
        # every earlier grade, not only those the reader may see.
        to_check = self.filtered(lambda line: not line.is_lock_released and line.student_id and line.outcome_id
                                 and line.grade_session_id.group_id and line.grade_session_id.subject_id
                                 and line.grade_session_id.round)
        passed_rounds = defaultdict(list)
        if to_check:
            sessions = to_check.grade_session_id
            for passed in self.sudo().search([
                ("student_id", "in", to_check.student_id.ids),
                ("outcome_id", "in", to_check.outcome_id.ids),
                ("grade_session_id.group_id", "in", sessions.group_id.ids),
                ("grade_session_id.subject_id", "in", sessions.subject_id.ids),
                ("grade_session_id.round", "<", max(sessions.mapped("round"))),
                ("is_scored", "=", True),
                ("score", ">=", 5),
            ]):
                earlier = passed.grade_session_id
                passed_rounds[(passed.student_id.id, passed.outcome_id.id, earlier.group_id.id,
                               earlier.subject_id.id)].append(earlier.round)
        for line in self:
            session = line.grade_session_id
            rounds = passed_rounds.get((line.student_id.id, line.outcome_id.id, session.group_id.id,
                                        session.subject_id.id), ()) if line in to_check else ()
            # round is a single-digit selection, so a string comparison orders it.
            line.is_locked = any(earlier_round < session.round for earlier_round in rounds)

    def write(self, vals):
        # open: scoped teachers/tutors; board: only the group's tutor; published and final: only admin.
        scoring = "score" in vals or "is_scored" in vals
        # The official grade importer may overwrite a locked outcome: the file is the source of
        # truth. This bypass is set only by ems.grade_import_wizard, never on manual editing.
        bypass_lock = self.env.context.get("ems_grade_import_bypass_lock")
        for line in self:
            # An accepted grade claim writes its one grade in a published session (issue #879), in
            # sudo after checking who answers it: a context flag alone, which any RPC can send, is not enough.
            if not (self.env.su and self.env.context.get("ems_grade_claim_apply")):
                line.grade_session_id._ems_check_can_edit(line.student_id)
            # A passed outcome from an earlier round cannot be re-evaluated (no exception, not even for admins).
            if scoring and line.is_locked and not bypass_lock:
                raise UserError(_("This learning outcome was already passed in an earlier round; its grade cannot be modified."))
            if vals.get("is_provisional") and not line.grade_session_id.allow_provisional:
                raise UserError(_("This evaluation session does not allow provisional grades."))
        # An emptied grade is no longer provisional either.
        if "is_scored" in vals and not vals["is_scored"]:
            vals = dict(vals, is_provisional=False)
        result = super().write(vals)
        if scoring and not bypass_lock:
            # A grade entered in an outcome the teacher ticked as "Provisional" is provisional too,
            # whatever was typed (issue #878). Not an official import's grade. sudo: the student's
            # tutor may grade a session of another group they cannot read.
            provisional = self.sudo().filtered(lambda line: line.is_scored and not line.is_provisional
                                        and line.grade_session_id.allow_provisional
                                        and line.outcome_id in line.grade_session_id.provisional_outcome_ids)
            if provisional:
                super(EmsGradeOutcomeLine, provisional).write({"is_provisional": True})
        return result

    @api.constrains("score")
    def _check_score(self):
        for line in self:
            if line.score < 0 or line.score > 10:
                raise ValidationError(_("The score must be within the range [0, 10]."))

    @api.depends("student_id", "outcome_id")
    def _compute_display_name(self):
        for line in self:
            line.display_name = "%s | %s" % (line.student_id.display_name or "", line.outcome_id.display_name or "")
