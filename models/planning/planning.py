# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class EmsPlanning(models.Model):
    _name = "ems.planning"
    _description = "Planning: Curriculum deployment in the classroom (in development: just for grading ponderation at the moment)."
    _sql_constraints = [
        ('unique_study_subject_course', 'unique (study_id, subject_id, course_id)', 'A planning already exists for this study, subject and course!')
    ]

    # TODO: For now, only for grading ponderation.
    # TODO: Multiple teachers as planning redactors.
    #       Needed a review and approval system (like minutes will do).
    # teacher_id = fields.Many2one(string="Teacher", comodel_name="hr.employee", required=True, domain="[('employee_type', '=', 'teacher')]")
    name = fields.Char(string="Name", compute="_compute_name", store=True)
    study_id = fields.Many2one(string="Study", comodel_name="ems.study", required=True)
    subject_id = fields.Many2one(string="Subject", comodel_name="ems.subject", required=True)
    # A planning's ponderations are only valid for one academic year, not forever (issue #503).
    # NOT required=True at the field level: a data-file-created row (the centre's own
    # data/custom/ccff/ems.planning-*.csv) is created before current_course_id can be resolved
    # for a fresh install (post_init_hook, which backfills it there, runs strictly after every
    # data file has already loaded - see plans/current_course_auto_seed.md), so a hard DB NOT
    # NULL would break a clean install outright. Required at the application level instead, via
    # _check_course_id_required below, using the exact same install_mode escape hatch
    # check_ponderation already relies on for the same reason.
    course_id = fields.Many2one(string="Course", comodel_name="ems.course",
                                default=lambda self: self.env.company.current_course_id)
    allowed_subject_ids = fields.Many2many(related="study_id.subject_ids", store=False)
    planning_outcome_ids = fields.One2many(string="Outcome ponderation", comodel_name="ems.planning_outcome", inverse_name="planning_id")
    internal_ponderation = fields.Float(string="Internal grading ponderation (%)", default=90.0, required=True)
    external_ponderation = fields.Float(string="External grading ponderation (%)", default=10.0, required=True)
    # Feeds the "Show only mine" search filter (issue #503): now that Head of Studies/Deputy see
    # every planning (rule_planning_hos_all), the list defaults to their own taught subjects,
    # same as a plain teacher already sees, with an easy way to widen it back to everything.
    is_own_subject = fields.Boolean(string="Taught by me", compute="_compute_is_own_subject",
                                    search="_search_is_own_subject", store=False)

    @api.constrains("course_id")
    def check_course_id_required(self):
        # Skipped during data-file loading for the same reason check_ponderation is (see its own
        # comment): a fresh install's CSV rows are created before current_course_id can be
        # resolved. post_init_hook backfills any still-empty course_id right after seeding it
        # (models/planning/planning.py is read there too - see _ems_seed_current_course in
        # __init__.py), so this only ever fires for a genuine real-world edit.
        if self.env.context.get("install_mode"):
            return
        for planning in self:
            if not planning.course_id:
                raise ValidationError(_("The course is required."))

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

    @api.depends("study_id", "subject_id", "course_id")
    def _compute_name(self):
        for planning in self:
            base = "%s  %s" % (planning.study_id.acronym, planning.subject_id.display_name)
            # course_id can be transiently empty right after a fresh install's data-file create,
            # before post_init_hook backfills it (see check_course_id_required's own comment).
            planning.name = "%s (%s)" % (base, planning.course_id.name) if planning.course_id else base

    def _ems_own_subject_domain(self):
        """Domain matching the plannings of the subjects the current user personally teaches
        (via ems.teaching) - the same relation rule_planning_teacher_own_subjects already
        restricts a plain teacher to. Shared by the compute and the search below so the two can
        never disagree, same pattern as res.partner._ems_my_students_domain (issue #421)."""
        return [('subject_id', 'in', self.env.user.employee_ids.teaching_ids.subject_id.ids)]

    @api.depends("subject_id")
    def _compute_is_own_subject(self):
        mine = self.filtered_domain(self._ems_own_subject_domain())
        for planning in self:
            planning.is_own_subject = planning in mine

    def _search_is_own_subject(self, operator, value):
        if operator not in ('=', '!=') or not isinstance(value, bool):
            raise NotImplementedError(_("Unsupported search on is_own_subject"))
        domain = self._ems_own_subject_domain()
        if (operator == '=') == value:
            return domain
        return ['!'] + domain
