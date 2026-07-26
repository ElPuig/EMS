# -*- coding: utf-8 -*-

from datetime import date
from odoo import models, fields, api, _

class ems_study(models.Model):
    _name = "ems.study"
    _description = "Study: The concrete type of stidy (kind of bachelor, concrete univeristy grade, etc.)"
    
    code = fields.Char(string="Code", required=True)
    acronym = fields.Char(string="Acronym", required=True)
    name = fields.Char(string="Name", required=True)
    date = fields.Date(string="Release Date", required=True)
    deprecated = fields.Boolean(string="Deprecated", required=True)    
    notes = fields.Text(string="Notes")
    # Where this study stands in the end-of-year transition. Studies do not finish at the
    # same time (a CFGS may close in June while an ESO level is still evaluating), so the
    # transition wizard runs per study and marks the ones it processed; the global course
    # flip only happens on the run that leaves no 'active' study behind, which then resets
    # every study back to 'active'. It also tells sale.order._ems_admit_student() whether a
    # late confirmation still has a bulk placement coming ('active') or has to place the
    # student on its own ('transitioned'). copy=False: a duplicated study starts its own life.
    transition_state = fields.Selection(string="Transition state", selection=[
        ('active', 'Active'),
        ('transitioned', 'Transitioned'),
    ], default='active', required=True, copy=False)

    follow_ids = fields.One2many(string="Follow-up", comodel_name="ems.tracking", inverse_name="study_id")
    subject_ids = fields.Many2many(string="Subjects", comodel_name="ems.subject") 
    level_id = fields.Many2one(string="Level", comodel_name="ems.level")

    attachment_ids = fields.Many2many(string="Attached files", comodel_name="ir.attachment", domain="[('res_model', '=', 'ems.study')]")

    # Single source of truth for whether a study manages its admissions through the
    # matrícula (sale.order) flow. Derived, not a manual config flag: a study uses the
    # flow if it has at least one active enrollment template (sale.order.template).
    # NOTE: some institutes may run a dedicated enrollment application instead of EMS
    # matrículas. This computed field is the single place to adapt that case (point it
    # at the relevant signal) without touching the "no destination" report, the
    # transition_status computation or the transition wizard preview that consume it.
    uses_enrollment_flow = fields.Boolean(
        string="Uses enrollment flow",
        compute='_compute_uses_enrollment_flow',
        search='_search_uses_enrollment_flow')

    @api.depends('acronym', 'name')
    def _compute_display_name(self):
        for rec in self:
            year = date.today().year if rec.date is False else rec.date.year
            rec.display_name = "%s (%s): %s" % (rec.acronym, year, rec.name)

    def _ems_last_course(self):
        """Highest group course of this study (2 for a CFGM/CFGS, 4 for ESO...), 0 when
        the study has no group yet. Answers "is this the final year?", which drives both
        who may graduate (graduation wizard) and which evaluation components are due
        (transition wizard: the work placement only exists in the last course).
        Tolerates an empty recordset so callers can pass a student's study unchecked."""
        if not self:
            return 0
        self.ensure_one()
        courses = self.env['ems.group'].search([('study_id', '=', self.id)]).mapped('course')
        return max(courses) if courses else 0

    def _compute_uses_enrollment_flow(self):
        Template = self.env['sale.order.template']
        for study in self:
            study.uses_enrollment_flow = bool(Template.search_count([
                ('ems_study_id', '=', study.id), ('active', '=', True)]))

    def _search_uses_enrollment_flow(self, operator, value):
        if operator not in ('=', '!=') or not isinstance(value, bool):
            raise NotImplementedError(_("Unsupported search on uses_enrollment_flow"))
        study_ids = self.env['sale.order.template'].search([
            ('ems_study_id', '!=', False), ('active', '=', True)]).mapped('ems_study_id').ids
        # positive = has a flow; negative = has none
        positive = (operator == '=' and value) or (operator == '!=' and not value)
        return [('id', 'in' if positive else 'not in', study_ids)]

            