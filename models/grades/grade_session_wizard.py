# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from .grade_session import grade_round_selection, grade_state_selection

class EmsGradeSessionWizard(models.TransientModel):
    _name = "ems.grade_session_wizard"
    _description = "Grade session wizard: bulk creation of grade sessions by level or study."

    mode = fields.Selection(string="Mode", selection=[("level", "By level"), ("study", "By study")], default="study", required=True)
    level_ids = fields.Many2many(string="Levels", comodel_name="ems.level")
    study_ids = fields.Many2many(string="Studies", comodel_name="ems.study")
    round = fields.Selection(string="Round", selection=grade_round_selection, default="1", required=True)

    def _target_studies(self):
        self.ensure_one()
        if self.mode == "level":
            return self.env["ems.study"].search([("level_id", "in", self.level_ids.ids)])
        return self.study_ids

    @api.onchange("mode", "level_ids", "study_ids")
    def _onchange_suggest_round(self):
        # Suggest the round following the highest one already existing within the selected scope.
        for wizard in self:
            studies = wizard._target_studies()
            if not studies:
                wizard.round = "1"
                continue
            groups = self.env["ems.group"].search([("study_id", "in", studies.ids)])
            existing = self.env["ems.grade_session"].search([("group_id", "in", groups.ids)])
            max_round = max([int(session.round) for session in existing], default=0)
            wizard.round = str(min(max_round + 1, int(grade_round_selection[-1][0])))

    def action_create_sessions(self):
        self.ensure_one()
        studies = self._target_studies()
        if not studies:
            raise UserError(_("Please select at least one level or study."))

        session_model = self.env["ems.grade_session"]
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


class EmsGradeSessionStateWizard(models.TransientModel):
    _name = "ems.grade_session_state_wizard"
    _description = "Grade session state wizard: bulk state transition (board / final) by level or study."

    mode = fields.Selection(string="Mode", selection=[("level", "By level"), ("study", "By study")], default="study", required=True)
    level_ids = fields.Many2many(string="Levels", comodel_name="ems.level")
    study_ids = fields.Many2many(string="Studies", comodel_name="ems.study")
    round = fields.Selection(string="Round", selection=grade_round_selection, default="1", required=True)
    target_state = fields.Selection(string="Target state", selection=grade_state_selection, default="board", required=True)

    def _target_studies(self):
        self.ensure_one()
        if self.mode == "level":
            return self.env["ems.study"].search([("level_id", "in", self.level_ids.ids)])
        return self.study_ids

    def action_apply_state(self):
        self.ensure_one()
        studies = self._target_studies()
        if not studies:
            raise UserError(_("Please select at least one level or study."))

        groups = self.env["ems.group"].search([("study_id", "in", studies.ids)])
        sessions = self.env["ems.grade_session"].search([
            ("group_id", "in", groups.ids),
            ("round", "=", self.round),
        ])
        if not sessions:
            raise UserError(_("No grade sessions were found for the selected scope and round."))
        sessions.write({"state": self.target_state})

        action = self.env["ir.actions.act_window"]._for_xml_id("ems.action_grade_session_tree")
        action["domain"] = [("id", "in", sessions.ids)]
        action["context"] = {}
        return action
