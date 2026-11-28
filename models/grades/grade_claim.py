# -*- coding: utf-8 -*-

from collections import defaultdict

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from ..shared import base

ANSWER_TASK = "ems.mail_activity_grade_claim_answer"
# The school days a student has, after the teacher's denial, to take the claim to the tutor when
# the claims period is already over or about to be (developer, issue #879).
ESCALATION_SCHOOL_DAYS = 2
PENDING_STATES = ("teacher", "tutor")


class EmsGradeClaimDenialReason(models.Model):
    """Why a teacher or a tutor denies a grade claim (issue #879): the catalog they pick from, edited
    in Planning and Grading > Configuration, as the convalidations' refusal reasons. A claim is about
    a grade that does not match the calculation the teacher shared, so the reasons say why it does."""
    _name = "ems.grade_claim.denial_reason"
    _inherit = "ems.reason.catalog"
    _description = "Grade claim denial reason"

    requires_details = fields.Boolean(string="Requires details",
                                      help="Whoever denies the claim must explain it in the details (e.g. 'Other').")


class EmsGradeClaim(models.Model):
    """A student's claim against a published grade (issue #879): a learning outcome's grade of the
    round, or the subject's final grade once every outcome is evaluated. A circuit before the
    official claim: the session's teacher answers first; if they deny it, the student may take it
    to their tutor. The Head of Studies in the tutor's chain (and an administrator) may answer
    either instance. Accepting it writes the corrected grade; nothing else in the session opens.
    See docs/en/developers/grades/grade_claim.md."""
    _name = "ems.grade_claim"
    _description = "Grade claim: a student asks for a published grade to be reviewed."
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc, id desc"
    _sql_constraints = [
        ("grade_claim_unique", "UNIQUE(claim_key)", "This grade has already been claimed."),
    ]

    session_id = fields.Many2one(string="Evaluation session", comodel_name="ems.grade_session", required=True,
                                 ondelete="cascade", index=True)
    student_id = fields.Many2one(string="Student", comodel_name="res.partner", required=True, index=True)
    group_id = fields.Many2one(string="Group", related="session_id.group_id", store=True)
    subject_id = fields.Many2one(string="Subject", related="session_id.subject_id", store=True)
    round = fields.Selection(string="Round", related="session_id.round", store=True)
    kind = fields.Selection(string="What is claimed", selection=[("outcome", "Learning outcome"), ("final", "Final grade")],
                            required=True)
    outcome_line_id = fields.Many2one(string="Learning outcome grade", comodel_name="ems.grade_outcome_line",
                                      ondelete="cascade")
    outcome_id = fields.Many2one(string="Learning outcome", related="outcome_line_id.outcome_id", store=True)
    subject_line_id = fields.Many2one(string="Subject grade", comodel_name="ems.grade_subject_line", required=True,
                                      ondelete="cascade")
    claim_key = fields.Char(compute="_compute_claim_key", store=True)
    claimed_score = fields.Integer(string="Grade when claimed", readonly=True,
                                   help="The grade when the claim was filed.")
    reason = fields.Text(string="What does not match", required=True,
                         help="Why the student thinks the grade does not match the calculation the teacher shared.")
    filed_by_id = fields.Many2one(string="Filed by", comodel_name="res.partner", readonly=True)
    state = fields.Selection(string="State", selection=[
        ("teacher", "Pending: teacher"),
        ("teacher_denied", "Denied by the teacher"),
        ("tutor", "Pending: tutor"),
        ("accepted", "Accepted"),
        ("denied", "Denied"),
    ], default="teacher", required=True, tracking=True, index=True)
    new_score = fields.Integer(string="Corrected grade", readonly=True)

    teacher_reason_id = fields.Many2one(string="Teacher's reason", comodel_name="ems.grade_claim.denial_reason",
                                        readonly=True)
    teacher_details = fields.Text(string="Teacher's answer", readonly=True)
    teacher_answered_by_id = fields.Many2one(string="Answered by (first instance)", comodel_name="res.users",
                                             readonly=True)
    teacher_answer_date = fields.Date(string="Answered on (first instance)", readonly=True)
    escalation_reason = fields.Text(string="Why it goes to the tutor", readonly=True)
    escalation_date = fields.Date(string="Taken to the tutor on", readonly=True)
    tutor_reason_id = fields.Many2one(string="Tutor's reason", comodel_name="ems.grade_claim.denial_reason",
                                      readonly=True)
    tutor_details = fields.Text(string="Tutor's answer", readonly=True)
    tutor_answered_by_id = fields.Many2one(string="Answered by (second instance)", comodel_name="res.users",
                                           readonly=True)
    tutor_answer_date = fields.Date(string="Answered on (second instance)", readonly=True)

    escalation_deadline = fields.Date(string="Can be taken to the tutor until", compute="_compute_escalation_deadline")
    can_answer = fields.Boolean(string="Can answer", compute="_compute_can_answer")

    @api.depends("session_id", "student_id", "kind", "outcome_line_id")
    def _compute_claim_key(self):
        # One claim per grade and round (each one can still go to the tutor once): an outcome's
        # line, or the subject's final grade.
        for claim in self:
            target = claim.outcome_line_id.outcome_id.id if claim.kind == "outcome" else "final"
            claim.claim_key = f"{claim.session_id.id}-{claim.student_id.id}-{target}"

    @api.depends("teacher_answer_date", "session_id.claim_date_to")
    def _compute_escalation_deadline(self):
        # The end of the claims period, or two school days after the teacher's denial when that is
        # later: a denial on the last day still leaves time to go to the tutor.
        # The holidays are read once for every answered claim (_ems_nth_school_days).
        answered = self.filtered("teacher_answer_date")
        after_denial = dict(zip(answered.ids, self.env["resource.calendar.leaves"]._ems_nth_school_days(
            answered.mapped("teacher_answer_date"), ESCALATION_SCHOOL_DAYS))) if answered else {}
        for claim in self:
            deadline = claim.session_id.claim_date_to
            if claim.id in after_denial:
                deadline = max(deadline, after_denial[claim.id]) if deadline else after_denial[claim.id]
            claim.escalation_deadline = deadline

    @api.depends_context("uid")
    @api.depends("state", "session_id.teacher_id", "student_id.tutor_id")
    def _compute_can_answer(self):
        for claim in self:
            claim.can_answer = claim.state in PENDING_STATES and claim._ems_user_answers()

    def _compute_display_name(self):
        for claim in self:
            target = claim.outcome_line_id.outcome_id.acronym if claim.kind == "outcome" else _("Final grade")
            claim.display_name = f"{claim.student_id.name} - {claim.subject_id.acronym or claim.subject_id.name} {target}"

    @api.constrains("kind", "outcome_line_id")
    def _check_outcome(self):
        for claim in self:
            if claim.kind == "outcome" and not claim.outcome_line_id:
                raise ValidationError(_("A claim about a learning outcome needs its grade."))

    # --- who may do what -------------------------------------------------------------------------

    def _ems_user_mediates(self):
        """The Head of Studies in the student's tutor's chain (tutor_scope_user_ids, which reaches
        the Director too) and an administrator answer either instance (developer, issue #879)."""
        self.ensure_one()
        user = self.env.user
        if user.has_group("ems.group_academic_admin"):
            return True
        return user.has_group("ems.group_head_of_studies") and base.EmsBase.user_acts_as_tutor(self, self.student_id.tutor_id)

    def _ems_user_answers(self):
        self.ensure_one()
        if self._ems_user_mediates():
            return True
        if self.state == "teacher":
            return self.env.user in self.session_id.teacher_id.sudo().acting_user_ids
        if self.state == "tutor":
            return base.EmsBase.user_acts_as_tutor(self, self.student_id.tutor_id)
        return False

    def _ems_check_can_answer(self):
        for claim in self:
            if claim.state not in PENDING_STATES:
                raise UserError(_("This claim has already been answered."))
            if claim.session_id.state != "published":
                raise UserError(_("Claims can only be answered while the grades are published."))
            if not claim._ems_user_answers():
                raise AccessError(_("You cannot answer this claim."))

    # --- filing (portal) -------------------------------------------------------------------------

    @api.model
    def _ems_claimable_items(self, student, partner):
        """What `partner` may claim for `student` now, from the portal: [(session, kind, line,
        score)], kind 'outcome' with its outcome line or 'final' with the subject line. Only
        published sessions inside their claims period; an outcome graded in that round (not one
        carried over passed from an earlier round), the final grade once every outcome is
        evaluated, and nothing already claimed. Empty when `partner` may not file for `student`
        (res.partner._ems_can_file_requests_for: the convalidations' rule). sudo: the portal user
        has no rights on the grades; scoped to that student."""
        if not student or not partner._ems_can_file_requests_for(student):
            return []
        today = self.env["ems.datetime_utils"].get_local_today()
        subject_lines = self.env["ems.grade_subject_line"].sudo().search([
            ("student_id", "=", student.id),
            ("session_state", "=", "published"),
            ("grade_session_id.claim_date_from", "<=", today),
            ("grade_session_id.claim_date_to", ">=", today),
            ("is_convalidated", "=", False),
        ])
        if not subject_lines:
            return []
        sessions = subject_lines.grade_session_id
        claimed = set(self.sudo().search([("student_id", "=", student.id), ("session_id", "in", sessions.ids)]).mapped("claim_key"))
        outcome_lines_by_session = defaultdict(list)
        for line in self.env["ems.grade_outcome_line"].sudo().search([
            ("student_id", "=", student.id), ("grade_session_id", "in", sessions.ids), ("is_scored", "=", True),
        ], order="outcome_id"):
            if not line.is_locked:
                outcome_lines_by_session[line.grade_session_id.id].append(line)
        items = []
        for subject_line in subject_lines.sorted(lambda line: (line.subject_id.code or "", line.id)):
            session = subject_line.grade_session_id
            for line in outcome_lines_by_session[session.id]:
                if f"{session.id}-{student.id}-{line.outcome_id.id}" not in claimed:
                    items.append((session, "outcome", line, line.score))
            if subject_line.has_final and f"{session.id}-{student.id}-final" not in claimed:
                items.append((session, "final", subject_line, subject_line.final_score))
        return items

    @api.model
    def ems_file_from_portal(self, student, partner, item_key, reason):
        """File a claim from the portal: `item_key` is 'outcome-<line id>' or 'final-<line id>', one
        of _ems_claimable_items(). Returns the claim (sudo)."""
        reason = (reason or "").strip()
        if not reason:
            raise UserError(_("Explain what does not match the calculation the teacher shared."))
        for session, kind, line, score in self._ems_claimable_items(student, partner):
            if f"{kind}-{line.id}" != item_key:
                continue
            subject_line = line if kind == "final" else self.env["ems.grade_subject_line"].sudo().search([
                ("grade_session_id", "=", session.id), ("student_id", "=", student.id)], limit=1)
            claim = self.sudo().create({
                "session_id": session.id,
                "student_id": student.id,
                "kind": kind,
                "outcome_line_id": line.id if kind == "outcome" else False,
                "subject_line_id": subject_line.id,
                "claimed_score": score,
                "reason": reason,
                "filed_by_id": partner.id,
            })
            claim._ems_sync_answer_task()
            return claim
        raise UserError(_("This grade cannot be claimed now."))

    def ems_escalate_from_portal(self, partner, reason):
        """Take a claim the teacher denied to the tutor, from the portal, until escalation_deadline."""
        self.ensure_one()
        claim = self.sudo()
        reason = (reason or "").strip()
        if not partner._ems_can_file_requests_for(claim.student_id):
            raise AccessError(_("You cannot take this claim to the tutor."))
        today = self.env["ems.datetime_utils"].get_local_today()
        if claim.state != "teacher_denied" or claim.session_id.state != "published" or today > claim.escalation_deadline:
            raise UserError(_("This claim can no longer be taken to the tutor."))
        if not reason:
            raise UserError(_("Explain why you take the claim to the tutor."))
        claim.write({"state": "tutor", "escalation_reason": reason, "escalation_date": today})
        claim._ems_sync_answer_task()
        return claim

    # --- answering (backend) ----------------------------------------------------------------------

    def _ems_answer_users(self):
        """Who gets the answering task: the session's teacher in the first instance, the student's
        tutor in the second. Mediators find it in the claims' list."""
        self.ensure_one()
        if self.state == "teacher":
            return self.session_id.teacher_id.sudo().acting_user_ids
        if self.state == "tutor":
            return self.student_id.tutor_id.sudo().user_id
        return self.env["res.users"]

    def _ems_sync_answer_task(self):
        # A quiet task (the daily summary tells its owner), due on the last day of the claims period.
        for claim in self.sudo():
            deadline = max(claim.session_id.claim_date_to or claim.create_date.date(),
                           self.env["ems.datetime_utils"].get_local_today())
            claim._ems_sync_user_tasks(self.env.ref(ANSWER_TASK), claim._ems_answer_users(), deadline,
                                       done=claim.state not in PENDING_STATES)

    def ems_accept(self, new_score):
        """Accept the claim and write the corrected grade: the outcome's grade, or, for the final
        grade, the internal grade overridden (the grade the teacher sets for the centre's part)."""
        self.ensure_one()
        self._ems_check_can_answer()
        if not 0 <= new_score <= 10:
            raise ValidationError(_("The score must be within the range [0, 10]."))
        claim = self.sudo()
        # The session is published: only an accepted claim opens this one grade (and only it).
        apply_env = claim.with_context(ems_grade_claim_apply=True)
        if claim.kind == "outcome":
            apply_env.outcome_line_id.write({"score": new_score, "is_scored": True, "is_provisional": False})
        else:
            apply_env.subject_line_id.write({"is_overridden": True, "internal_score": new_score})
        instance = claim.state
        claim.write(dict(claim._ems_answer_vals(instance), state="accepted", new_score=new_score))
        claim._ems_sync_answer_task()
        claim._ems_send_resolution(instance)
        return True

    def ems_deny(self, reason, details):
        self.ensure_one()
        self._ems_check_can_answer()
        if not reason:
            raise UserError(_("Choose the reason for denying the claim."))
        if reason.requires_details and not (details or "").strip():
            raise UserError(_("Explain the reason for denying the claim."))
        claim = self.sudo()
        instance = claim.state
        vals = claim._ems_answer_vals(instance)
        vals.update({f"{instance}_reason_id": reason.id, f"{instance}_details": details,
                     "state": "teacher_denied" if instance == "teacher" else "denied"})
        claim.write(vals)
        claim._ems_sync_answer_task()
        claim._ems_send_resolution(instance)
        return True

    def _ems_answer_vals(self, instance):
        return {f"{instance}_answered_by_id": self.env.user.id,
                f"{instance}_answer_date": self.env["ems.datetime_utils"].get_local_today()}

    def _ems_send_resolution(self, instance):
        """Email the student (and the family while a minor) the answer of one instance: card layout,
        a button to the portal. Queued, sent by the mail queue."""
        template = self.env.ref("ems.email_template_grade_claim_answered").sudo()
        for recipient in self.student_id._ems_informed_recipients().filtered("email"):
            lang = recipient.lang or self.student_id.lang or self.env.lang
            template.with_context(lang=lang, ems_claim_instance=instance).send_mail(
                self.id, force_send=False, email_values={"email_to": recipient.email})

    def action_accept(self):
        return self._ems_answer_wizard("accept")

    def action_deny(self):
        return self._ems_answer_wizard("deny")

    def _ems_answer_wizard(self, decision):
        self.ensure_one()
        self._ems_check_can_answer()
        action = self.env["ir.actions.act_window"]._for_xml_id("ems.action_grade_claim_answer_wizard")
        action["context"] = {"default_claim_id": self.id, "default_decision": decision}
        return action

    def _ems_grades_portal_url(self):
        # The grades layout's button (ems.mail_layout_grades), as res.partner's.
        return f"{self.get_base_url()}/my/calificaciones"


class EmsGradeClaimAnswerWizard(models.TransientModel):
    _name = "ems.grade_claim.answer_wizard"
    _description = "Answer a grade claim: accept it with the corrected grade, or deny it with a reason."

    claim_id = fields.Many2one(string="Claim", comodel_name="ems.grade_claim", required=True, ondelete="cascade")
    kind = fields.Selection(related="claim_id.kind")
    claimed_score = fields.Integer(related="claim_id.claimed_score")
    decision = fields.Selection(string="Decision", selection=[("accept", "Accept"), ("deny", "Deny")],
                                required=True, default="accept")
    new_score = fields.Integer(string="Corrected grade")
    reason_id = fields.Many2one(string="Reason", comodel_name="ems.grade_claim.denial_reason",
                                default=lambda self: self.env["ems.grade_claim.denial_reason"].default_reason())
    requires_details = fields.Boolean(related="reason_id.requires_details")
    details = fields.Text(string="Details")

    def action_confirm(self):
        self.ensure_one()
        if self.decision == "accept":
            self.claim_id.ems_accept(self.new_score)
        else:
            self.claim_id.ems_deny(self.reason_id, self.details)
        return {"type": "ir.actions.act_window_close"}
