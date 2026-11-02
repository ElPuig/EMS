# -*- coding: utf-8 -*-

import base64

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .academic_record_pdf import AcademicRecordPdfError
from .previous_curriculum_pdf import grade_passes, parse_previous_curriculum_record

# Imports a student's academic history under a previous curriculum (issue #672) from its
# "Historial acadèmic" PDF, or from its "Certificat de qualificacions" (issue #732): uploading it
# fills in the curriculum, the centre, the years and a review grid with every module and unit (UF)
# as printed. The user checks and corrects it before
# the record is created; nothing is mapped onto the current curriculum. The same roles as the
# previous record of the current curriculum (issue #585) may import one.


class EmsPreviousCurriculumWizard(models.TransientModel):
    _name = 'ems.previous_curriculum_wizard'
    _description = 'Previous curriculum wizard: imports an academic history of a previous curriculum.'

    student_id = fields.Many2one(string="Student", comodel_name='res.partner', required=True,
                                 ondelete='cascade')
    certificate_file = fields.Binary(string="Academic document")
    certificate_filename = fields.Char(string="Document file name")
    # Who the document says it belongs to, checked against the student's own IDALU, or their
    # Document ID (DNI/NIE) on a grades certificate, which has no IDALU.
    certificate_student_identifier = fields.Char(string="Document student ID", readonly=True)
    certificate_student_document_id = fields.Char(string="Document DNI/NIE", readonly=True)
    certificate_student_name = fields.Char(string="Document student", readonly=True)
    certificate_message = fields.Char(string="Document reading", readonly=True)
    curriculum_code = fields.Char(string="Curriculum code")
    curriculum_name = fields.Char(string="Curriculum")
    study_id = fields.Many2one(string="Current study", comodel_name='ems.study', ondelete='cascade')
    centre_code = fields.Char(string="Centre code")
    centre_name = fields.Char(string="Centre")
    start_year = fields.Integer(string="From year")
    end_year = fields.Integer(string="To year")
    title_obtained = fields.Boolean(string="Title obtained")
    title_date = fields.Date(string="Title date")
    notes = fields.Text(string="Notes")
    line_ids = fields.One2many(string="Modules and units", comodel_name='ems.previous_curriculum_wizard.line',
                               inverse_name='wizard_id')
    # Every module of the document passed: what proposes the title, which the document never states.
    all_modules_passed = fields.Boolean(string="All modules passed", compute='_compute_all_modules_passed')

    @api.depends('line_ids.kind', 'line_ids.grade')
    def _compute_all_modules_passed(self):
        for wizard in self:
            modules = wizard.line_ids.filtered(lambda line: line.kind == 'module')
            wizard.all_modules_passed = bool(modules) and all(grade_passes(line.grade) for line in modules)

    @api.onchange('certificate_file')
    def _onchange_certificate_file(self):
        self.ensure_one()
        self.line_ids = [(5, 0, 0)]
        self.certificate_student_identifier = False
        self.certificate_student_document_id = False
        self.certificate_student_name = False
        self.certificate_message = False
        if not self.certificate_file:
            return None
        pdf = base64.b64decode(self.certificate_file)
        try:
            if not pdf.startswith(b'%PDF'):
                raise AcademicRecordPdfError()
            document = parse_previous_curriculum_record(pdf)
        except AcademicRecordPdfError:
            self.certificate_message = _("The file is neither the academic history (Historial "
                                         "acadèmic) nor the grades certificate (Certificat de "
                                         "qualificacions) of a previous curriculum.")
            return None
        self.certificate_student_identifier = document['student_identifier']
        self.certificate_student_document_id = document['student_document_id']
        self.certificate_student_name = document['student_name']
        self.update({key: document[key] for key in (
            'curriculum_code', 'curriculum_name', 'centre_code', 'centre_name', 'start_year',
            'end_year', 'notes')})
        # "CFPS ICB0" -> the current study CFGS_ICB0.
        self.study_id = self.env['ems.study'].find_by_code_token(
            (document['curriculum_code'].split() or [''])[-1])
        self.line_ids = self._line_commands(document['modules'])
        # A grades certificate may list only some of the cycle's modules: it never proposes it.
        self.title_obtained = self.all_modules_passed and not document['is_certificate']
        problem = self._certificate_student_problem()
        if problem:
            return {'warning': {'title': _("Check the certificate's student"), 'message': problem}}
        return None

    @api.model
    def _line_commands(self, modules):
        commands = []
        for module in modules:
            for row in [module, *module['units']]:
                commands.append((0, 0, {
                    'sequence': len(commands), 'kind': row['kind'], 'code': row['code'],
                    'name': row['name'], 'hours': row['hours'], 'grade': row['grade'],
                    'sitting': row['sitting']}))
        return commands

    def _certificate_student_problem(self):
        return self.env['ems.base'].get_certificate_student_problem(
            self.student_id, self.certificate_student_identifier, self.certificate_student_name,
            self.certificate_student_document_id)

    def action_create(self):
        self.ensure_one()
        if not self.env['ems.base'].get_user_can_edit_history():
            raise UserError(_("Only the secretariat, the academic administration, the Head of "
                              "Studies and the Director may add a previous curriculum record."))
        if not self.line_ids:
            raise UserError(_("Upload the academic history or the grades certificate of the previous "
                              "curriculum."))
        problem = self._certificate_student_problem()
        if problem:
            raise UserError(problem)
        Record = self.env['ems.student.previous_curriculum_record'].sudo()
        if Record.search_count([('student_id', '=', self.student_id.id),
                                ('curriculum_code', '=', self.curriculum_code)]):
            raise UserError(_("%(student)s already has a record of %(curriculum)s.",
                              student=self.student_id.display_name, curriculum=self.curriculum_name))
        # sudo, as for the previous record of the current curriculum: the role was checked above,
        # and the Head of Studies has no create right on the history otherwise.
        record = Record.create({
            'student_id': self.student_id.id,
            'curriculum_code': self.curriculum_code,
            'curriculum_name': self.curriculum_name,
            'study_id': self.study_id.id,
            'centre_code': self.centre_code,
            'centre_name': self.centre_name,
            'start_year': self.start_year,
            'end_year': self.end_year,
            'title_obtained': self.title_obtained,
            'title_date': self.title_date,
            'certificate_file': self.certificate_file,
            'certificate_filename': self.certificate_filename,
            'notes': self.notes,
            'line_ids': [(0, 0, {field: line[field] for field in (
                'sequence', 'kind', 'code', 'name', 'hours', 'grade', 'sitting')})
                for line in self.line_ids],
        })
        self.student_id._message_log(body=Markup("<p>{}</p>").format(_(
            "Previous curriculum record of %(curriculum)s added by %(user)s: %(centre)s",
            curriculum=record.display_name, user=self.env.user.name,
            centre=f"{self.centre_name} ({self.centre_code})" if self.centre_code else self.centre_name)))
        return {'type': 'ir.actions.act_window_close'}


class EmsPreviousCurriculumWizardLine(models.TransientModel):
    _name = 'ems.previous_curriculum_wizard.line'
    _description = 'Previous curriculum wizard: one module or unit (UF) of the document.'
    _order = 'sequence asc, id asc'

    wizard_id = fields.Many2one(string="Wizard", comodel_name='ems.previous_curriculum_wizard',
                                required=True, ondelete='cascade')
    sequence = fields.Integer(string="Sequence")
    kind = fields.Selection(string="Type", required=True, selection=[
        ('module', 'Module'),
        ('unit', 'Unit (UF)'),
    ])
    code = fields.Char(string="Code")
    name = fields.Char(string="Name", required=True)
    hours = fields.Integer(string="Hours")
    grade = fields.Char(string="Grade")
    sitting = fields.Char(string="Sitting")
