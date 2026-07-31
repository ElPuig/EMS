# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class EmsPlanning(models.Model):
    _name = "ems.planning"
    _description = "Planning: Curriculum deployment in the classroom (in development: just for grading ponderation at the moment)."
    _sql_constraints = [
        ('unique_study_subject', 'unique (study_id, subject_id)', 'A planning already exists for this study and subject!')
    ]

    # TODO: For now, only for grading ponderation.
    # TODO: Multiple teachers as planning redactors.
    #       Needed a review and approval system (like minutes will do).
    # teacher_id = fields.Many2one(string="Teacher", comodel_name="hr.employee", required=True, domain="[('employee_type', '=', 'teacher')]")
    name = fields.Char(string="Name", compute="_compute_name", store=True)
    study_id = fields.Many2one(string="Study", comodel_name="ems.study", required=True)
    subject_id = fields.Many2one(string="Subject", comodel_name="ems.subject", required=True)
    allowed_subject_ids = fields.Many2many(related="study_id.subject_ids", store=False)
    planning_outcome_ids = fields.One2many(string="Outcome ponderation", comodel_name="ems.planning_outcome", inverse_name="planning_id")
    internal_ponderation = fields.Float(string="Internal grading ponderation (%)", default=90.0, required=True)
    external_ponderation = fields.Float(string="External grading ponderation (%)", default=10.0, required=True)

    @api.constrains("planning_outcome_ids", "internal_ponderation", "external_ponderation")
    def check_ponderation(self):
        # A data file's planning_outcome_ids can only be populated via a separate CSV (CSV has
        # no inline one2many eval, unlike XML), so the parent row's own create() always fires
        # this constraint first, with no children yet - install_mode=True is the context Odoo's
        # own data-file loader always applies (odoo/models.py::_load_records), so this only
        # skips the check while more files may still be loading, never for a real UI edit.
        if self.env.context.get("install_mode"):
            return
        for planning in self:
            total = sum(outcome_line.ponderation for outcome_line in planning.planning_outcome_ids)
            if round(total, 2) != 100:
                raise ValidationError(_("The outcome ponderation values must sum 100."))
            if round(planning.internal_ponderation + planning.external_ponderation, 2) != 100:
                raise ValidationError(_("The main ponderation values must sum 100."))

    @api.onchange('subject_id')
    def _onchange_planning_outcome_ids(self):
        for planning in self:
            planning.planning_outcome_ids = False
            if not planning.subject_id:
                continue

            outcomes = planning.subject_id.outcome_ids
            count = len(outcomes)
            if not count:
                continue

            # Split evenly; the last outcome absorbs the rounding remainder so the
            # total is always exactly 100 (check_ponderation enforces this on save).
            pond = round(100 / count, 2)
            last = round(100 - pond * (count - 1), 2)

            planning.planning_outcome_ids = [
                (0, 0, {"outcome_id": outcome.id, "ponderation": pond if i < count - 1 else last})
                for i, outcome in enumerate(outcomes)
            ]

    @api.depends("study_id", "subject_id")
    def _compute_name(self):
        for planning in self:
            planning.name = "%s  %s" % (planning.study_id.acronym, planning.subject_id.display_name)
