# -*- coding: utf-8 -*-

from datetime import date
from odoo import models, fields, api, _

class EmsStudy(models.Model):
    _name = "ems.study"
    _description = "Study: The concrete type of study (kind of bachelor, concrete university grade, etc.)"
    _order = "code asc"

    _sql_constraints = [
        ('unique_code', 'unique (code)', 'The code must be unique.'),
    ]

    code = fields.Char(string="Code", required=True)
    acronym = fields.Char(string="Acronym", required=True)
    name = fields.Char(string="Name", required=True)
    date = fields.Date(string="Release Date", required=True)
    deprecated = fields.Boolean(string="Deprecated", required=True, default=False)
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
        for study in self:
            year = date.today().year if study.date is False else study.date.year
            study.display_name = "%s (%s): %s" % (study.acronym, year, study.name)

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

    def _subjects_common_to_all(self):
        """Subjects taught in EVERY study in 'self' - the intersection (an empty recordset if
        'self' itself is empty, or once any one study in it teaches nothing at all). Shared by
        'ems.attendance_template.allowed_subject_ids' and the working-schedule import wizard's
        'subject_line' (both need exactly this same "valid across ALL these studies at once"
        rule) - extracted here rather than duplicated once the wizard needed the identical check.
        Uses 'search()' on ids (not a direct '.subject_ids' traversal) to preserve the exact,
        already-tested behavior 'allowed_subject_ids' had before this extraction, including
        working correctly against a still-unsaved form's NewId-wrapped study records, whose own
        '.id' is a placeholder object a search domain can't use directly - '.ids' resolves each
        one back to its real origin id regardless."""
        study_ids = self.ids
        if not study_ids:
            return self.env['ems.subject']
        subjects = self.env['ems.subject'].search([('study_ids', 'in', study_ids[0])])
        for study_id in study_ids[1:]:
            subjects &= self.env['ems.subject'].search([('study_ids', 'in', study_id)])
        return subjects

    def _ems_subject_course(self, product):
        """The single course (study_year) this study's own templates sell `product`
        for, or False when it is not sold by exactly one course's template - missing
        entirely, or genuinely offered across more than one (e.g. a transversal
        module). Shared by sale.order._ems_course_from_tutorship() (one specific
        product, the tutorship) and _ems_apply_destination_placement() (every
        subject on the order), so a subject's course is always resolved the same way."""
        self.ensure_one()
        templates = self.env['sale.order.template'].search([
            ('ems_study_id', '=', self.id), ('study_year', '!=', False)])
        years = {template.study_year for template in templates
            if product in template.sale_order_template_line_ids.product_id}
        return years.pop() if len(years) == 1 else False

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
