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

            