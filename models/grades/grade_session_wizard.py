# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from .grade_session import grade_round_selection, grade_state_selection

class EmsGradeSessionWizard(models.TransientModel):
    _name = "ems.grade_session_wizard"
    _description = "Grade session wizard: bulk creation of grade sessions by level or study."

    mode = fields.Selection(string="Mode", selection=[("level", "By level"), ("study", "By study")], default="study", required=True)
    level_ids = fields.Many2many(string="Levels", comodel_name="ems.level")
    study_ids = fields.Many2many(string="Studies", comodel_name="ems.study")
    # Not asked (issue #354): the round following the highest one already existing within the
    # selected scope, shown read-only. Still writable so a caller (or a test) can force one.
    # Not required at the database level: it depends on the studies, a many2many that is only
    # written after the wizard's row is inserted.
    round = fields.Selection(string="Round", selection=grade_round_selection, compute="_compute_round", store=True, readonly=False)
    # Required by the form and by action_create_sessions(), not by the database: a NOT NULL would
    # fail on the wizard rows left from before this field existed.
    claim_date_from = fields.Date(string="Claims from")
    claim_date_to = fields.Date(string="Claims until")

    def _target_studies(self):
        self.ensure_one()
        if self.mode == "level":
            return self.env["ems.study"].search([("level_id", "in", self.level_ids.ids)])
        return self.study_ids

    @api.depends("mode", "level_ids", "study_ids")
    def _compute_round(self):
        last_round = int(grade_round_selection[-1][0])
        for wizard in self:
            studies = wizard._target_studies()
            max_round = 0
            if studies:
                # One grouped query instead of reading every session of the scope.
                rounds = self.env["ems.grade_session"]._read_group(
                    [("group_id.study_id", "in", studies.ids)], groupby=["round"])
                max_round = max((int(session_round) for session_round, in rounds), default=0)
            wizard.round = str(min(max_round + 1, last_round))

    def action_create_sessions(self):
        self.ensure_one()
        if not self.env["ems.grade_session"]._ems_user_manages_sessions():
            raise UserError(_("Only the Head of Studies or an administrator can create evaluation sessions."))
        studies = self._target_studies()
        if not studies:
            raise UserError(_("Please select at least one level or study."))
        if not (self.claim_date_from and self.claim_date_to):
            raise UserError(_("Please set the claims period of the new sessions."))

        # sudo: the Head of Studies manages the sessions but has no rights on the grade lines
        # fill_students() creates (checked just above).
        session_model = self.env["ems.grade_session"].sudo()
        created = session_model
        skipped = 0
        for study in studies:
            for group in self.env["ems.group"].search([("study_id", "=", study.id)]):
                # Only subjects with enrolled students in this group, excluding tutorships (not graded).
                subjects = self.env["ems.enrollment"].search([
                    ("group_id", "=", group.id),
                ]).mapped("subject_id").filtered(lambda subject: not subject.is_tutorship)
                for subject in subjects:
                    if session_model.search_count([
                        ("group_id", "=", group.id),
                        ("subject_id", "=", subject.id),
                        ("round", "=", self.round),
                    ]):
                        skipped += 1
                        continue
                    session = session_model.create({
                        "group_id": group.id,
                        "subject_id": subject.id,
                        "round": self.round,
                        "claim_date_from": self.claim_date_from,
                        "claim_date_to": self.claim_date_to,
                        "teacher_id": session_model._derive_teacher(group, subject).id,
                    })
                    session.fill_students()
                    created += session

        if not created:
            raise UserError(_("No grade sessions were created (they may already exist for the selected round, or the groups have no enrolled subjects)."))

        action = self.env["ir.actions.act_window"]._for_xml_id("ems.action_grade_session_tree")
        action["domain"] = [("id", "in", created.ids)]
        action["context"] = {}
        return action

    @api.constrains("claim_date_from", "claim_date_to")
    def _check_claim_dates(self):
        for wizard in self:
            if wizard.claim_date_from and wizard.claim_date_to and wizard.claim_date_from > wizard.claim_date_to:
                raise ValidationError(_("The claims period cannot end before it starts."))


class EmsGradeSessionStateWizard(models.TransientModel):
    _name = "ems.grade_session_state_wizard"
    _description = "Grade session state wizard: state transition of the selected sessions, or of a whole level or study."

    mode = fields.Selection(string="Mode", selection=[("level", "By level"), ("study", "By study")], default="study", required=True)
    level_ids = fields.Many2many(string="Levels", comodel_name="ems.level")
    study_ids = fields.Many2many(string="Studies", comodel_name="ems.study")
    round = fields.Selection(string="Round", selection=grade_round_selection, default="1", required=True)
    target_state = fields.Selection(string="Target state", selection=grade_state_selection,
                                    compute="_compute_target_state", store=True, readonly=False)
    allowed_states = fields.Char(string="Allowed states", compute="_compute_allowed_states",
                                 help="Comma-separated states every target session can move to (the dropdown's options).")
    from_selection = fields.Boolean(default=lambda self: bool(self._selected_sessions()))
    announce = fields.Boolean(string="Announce the publication",
                              help="Email every student, and their family while a minor, that the grades are in the portal. The email carries no grades.")
    publish_warning = fields.Text(string="Empty grades", compute="_compute_publish_warning",
                                  help="Sessions about to be published that still have empty outcome grades.")

    def _target_studies(self):
        self.ensure_one()
        if self.mode == "level":
            return self.env["ems.study"].search([("level_id", "in", self.level_ids.ids)])
        return self.study_ids

    def _selected_sessions(self):
        # Launched from the sessions' list (issue #354) it acts on the selection; from the menu,
        # on every session of the chosen scope and round.
        context = self.env.context
        if context.get("active_model") == "ems.grade_session" and context.get("active_ids"):
            return self.env["ems.grade_session"].browse(context["active_ids"])
        return self.env["ems.grade_session"]

    def _target_sessions(self):
        self.ensure_one()
        sessions = self._selected_sessions()
        if sessions:
            return sessions
        studies = self._target_studies()
        if not studies:
            return sessions
        return self.env["ems.grade_session"].search([
            ("group_id.study_id", "in", studies.ids),
            ("round", "=", self.round),
        ])

    @api.depends("mode", "level_ids", "study_ids", "round")
    def _compute_allowed_states(self):
        # A session moves one step at a time (see ems.grade_session._ems_check_state_change): offer
        # only the states every target session can reach, leaving out the one they are all in already.
        order = [state for state, _label in grade_state_selection]
        for wizard in self:
            current = set(wizard._target_sessions().mapped("state"))
            if not current:
                # Nothing chosen yet (from the menu): every state, until a scope is picked.
                wizard.allowed_states = False
                continue
            allowed = set(order)
            for state in current:
                index = order.index(state)
                allowed &= set(order[max(index - 1, 0):index + 2])
            if len(current) == 1:
                allowed -= current
            wizard.allowed_states = ",".join(state for state in order if state in allowed)

    @api.depends("allowed_states")
    def _compute_target_state(self):
        # The next state by default: the furthest one allowed. With mixed states that share no
        # reachable state, nothing is offered and the write explains which session cannot move.
        for wizard in self:
            allowed = [state for state in (wizard.allowed_states or "").split(",") if state]
            if not allowed:
                wizard.target_state = wizard.target_state or "board"
            elif wizard.target_state not in allowed:
                wizard.target_state = allowed[-1]

    @api.depends("target_state", "mode", "level_ids", "study_ids", "round")
    def _compute_publish_warning(self):
        # A warning, not a block (issue #878): not every outcome is evaluated in every round.
        for wizard in self:
            lines = wizard._target_sessions()._ems_empty_grades_summary() if wizard.target_state == "published" else []
            wizard.publish_warning = "\n".join(lines) or False

    def action_apply_state(self):
        self.ensure_one()
        if not self._selected_sessions() and not self._target_studies():
            raise UserError(_("Please select at least one level or study."))
        sessions = self._target_sessions()
        if not sessions:
            raise UserError(_("No grade sessions were found for the selected scope and round."))
        sessions.write({"state": self.target_state})
        if self.announce and self.target_state == "published":
            sessions._ems_announce_publication()

        action = self.env["ir.actions.act_window"]._for_xml_id("ems.action_grade_session_tree")
        action["domain"] = [("id", "in", sessions.ids)]
        action["context"] = {}
        return action
