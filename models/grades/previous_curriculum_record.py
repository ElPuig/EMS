# -*- coding: utf-8 -*-

from odoo import api, fields, models

from .previous_curriculum_pdf import grade_passes

# The academic history of a student under a previous curriculum (issue #672): a VET cycle of an
# earlier law (LOE, organised in units - UF - instead of learning outcomes) that SAGA managed before
# Esfera. Its modules do not map onto the current curriculum, so it is kept apart from the per-course
# history (ems.student.year_record) and as printed on its academic history: only to be looked up,
# typically to decide a convalidation request. It is created by the import wizard
# (ems.previous_curriculum_wizard) and never generated.


class EmsStudentPreviousCurriculumRecord(models.Model):
    _name = 'ems.student.previous_curriculum_record'
    _description = 'Previous curriculum record: academic history of a student under a previous curriculum.'
    _order = 'student_id asc, start_year desc'
    _sql_constraints = [
        ('unique_student_curriculum', 'unique (student_id, curriculum_code)',
         'The student already has a record of this curriculum!'),
    ]

    student_id = fields.Many2one(string="Student", comodel_name='res.partner', required=True,
                                 ondelete='restrict', index=True)
    # As printed ("CFPS ICB0", "CFPS Desenvolupament d'aplicacions multiplataforma (LOE)"): the
    # curriculum is what identifies the studies, and it is no longer in EMS.
    curriculum_code = fields.Char(string="Curriculum code", required=True)
    curriculum_name = fields.Char(string="Curriculum", required=True)
    # The current study that took over the cycle, when its code matches: informative only.
    study_id = fields.Many2one(string="Current study", comodel_name='ems.study', ondelete='set null')
    source_application = fields.Char(string="Source application", default='SAGA')
    centre_code = fields.Char(string="Centre code")
    centre_name = fields.Char(string="Centre")
    start_year = fields.Integer(string="From year")
    end_year = fields.Integer(string="To year")
    title_obtained = fields.Boolean(string="Title obtained", default=False)
    title_date = fields.Date(string="Title date")
    certificate_file = fields.Binary(string="Academic document", attachment=True)
    certificate_filename = fields.Char(string="Document file name")
    notes = fields.Text(string="Notes")
    line_ids = fields.One2many(string="Modules and units",
                               comodel_name='ems.student.previous_curriculum_record.line',
                               inverse_name='record_id')
    module_count = fields.Integer(string="Modules", compute='_compute_module_counts')
    passed_module_count = fields.Integer(string="Modules passed", compute='_compute_module_counts')

    @api.depends('line_ids.kind', 'line_ids.is_passed')
    def _compute_module_counts(self):
        for record in self:
            modules = record.line_ids.filtered(lambda line: line.kind == 'module')
            record.module_count = len(modules)
            record.passed_module_count = len(modules.filtered('is_passed'))

    @api.depends('curriculum_name', 'start_year', 'end_year')
    def _compute_display_name(self):
        for record in self:
            years = f" ({record.start_year}-{record.end_year})" if record.start_year else ''
            record.display_name = f"{record.curriculum_name or ''}{years}"


class EmsStudentPreviousCurriculumRecordLine(models.Model):
    _name = 'ems.student.previous_curriculum_record.line'
    _description = 'Previous curriculum record: one module or unit (UF) with its grade.'
    _order = 'record_id asc, sequence asc, id asc'

    record_id = fields.Many2one(string="Record", comodel_name='ems.student.previous_curriculum_record',
                                required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(string="Sequence")
    # A module and, right below it, its units: the order of the printed table.
    kind = fields.Selection(string="Type", required=True, selection=[
        ('module', 'Module'),
        ('unit', 'Unit (UF)'),
    ])
    code = fields.Char(string="Code")
    name = fields.Char(string="Name", required=True)
    hours = fields.Integer(string="Hours")
    # As printed: a number, or "NP", "Ap", "CV"... A module is only graded once all its units are.
    grade = fields.Char(string="Grade")
    sitting = fields.Char(string="Sitting")
    is_passed = fields.Boolean(string="Passed", compute='_compute_is_passed', store=True)

    @api.depends('grade')
    def _compute_is_passed(self):
        for line in self:
            line.is_passed = grade_passes(line.grade)
