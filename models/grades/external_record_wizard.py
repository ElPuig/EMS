# -*- coding: utf-8 -*-

import base64
import re

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..shared import base
from .academic_record_pdf import AcademicRecordPdfError, parse_academic_record

# A course the student took at another centre - typically the first year of a study whose second
# year they come here to take - typed in from that centre's academic certificate (issue #585).
#
# Two ways in, sharing the same record and the same grading rules:
# - The certificate is the Esfera "Expedient acadèmic" PDF: uploading it fills in the centre, the
#   course, the study and a review grid with every module and learning outcome (RA) it grades,
#   mapped by code to this centre's curriculum. The user checks and corrects the grid, and the
#   record is created with all its modules at once.
# - Any other certificate: the record is opened here and its modules are then added one by one
#   through the grade review's own "add a missing subject" operation.
#
# Either way the grades go through the grading formulas with the weights of the study's teaching
# plan for that course, the internal grade is forced to the certificate's module grade when the
# other centre weighed its RAs differently (issue #503), and a module whose work placement grade
# is still missing is left with its final pending, which is what makes the EM grading wizard
# offer it to the student's current tutor.

_PLAN_OUTCOME_NUMBER_RE = re.compile(r"_(\d{2})RA$")


class EmsExternalRecordWizard(models.TransientModel):
    _name = 'ems.external_record_wizard'
    _description = 'Previous record wizard: academic history of a course typed in from an academic certificate.'

    student_id = fields.Many2one(string="Student", comodel_name='res.partner', required=True,
                                 ondelete='cascade')
    course_id = fields.Many2one(string="Course", comodel_name='ems.course', ondelete='cascade')
    # Courses already over (the record is a course taken elsewhere) for which the student has no
    # record yet: what course_id may pick from.
    available_course_ids = fields.Many2many(string="Available courses", comodel_name='ems.course',
                                            compute='_compute_available_course_ids')
    study_id = fields.Many2one(string="Study", comodel_name='ems.study', required=True,
                               ondelete='cascade')
    # Studies with a teaching plan of learning outcomes for that course: the certificate's grades
    # are typed per RA, so a study without one (ESO and BTX today) has nothing to type them into.
    available_study_ids = fields.Many2many(string="Available studies", comodel_name='ems.study',
                                           compute='_compute_available_study_ids')
    origin_centre_name = fields.Char(string="Origin centre", required=True)
    origin_centre_code = fields.Char(string="Origin centre code")
    certificate_file = fields.Binary(string="Academic certificate")
    certificate_filename = fields.Char(string="Certificate file name")
    # Who the certificate says it belongs to, checked against the student's own IDALU.
    certificate_student_identifier = fields.Char(string="Certificate student ID", readonly=True)
    certificate_student_name = fields.Char(string="Certificate student", readonly=True)
    certificate_message = fields.Char(string="Certificate reading", readonly=True)
    line_ids = fields.One2many(string="Certificate grades", comodel_name='ems.external_record_wizard.line',
                               inverse_name='wizard_id')
    notes = fields.Text(string="Notes")

    @api.depends('student_id')
    def _compute_available_course_ids(self):
        current_course = self.env.company.current_course_id
        for wizard in self:
            taken = self.env['ems.student.year_record'].sudo().search(
                [('student_id', '=', wizard.student_id.id)]).course_id
            domain = [('id', 'not in', taken.ids)]
            if current_course:
                domain.append(('start', '<', current_course.start))
            wizard.available_course_ids = self.env['ems.course'].search(domain)

    @api.depends('course_id', 'line_ids.course_id')
    def _compute_available_study_ids(self):
        for wizard in self:
            courses = wizard.line_ids.course_id or wizard.course_id
            plannings = self.env['ems.planning'].sudo().search([
                ('course_id', 'in', courses.ids), ('planning_outcome_ids', '!=', False)])
            wizard.available_study_ids = plannings.study_id

    @api.onchange('course_id')
    def _onchange_course_id(self):
        for wizard in self:
            if not wizard.line_ids and wizard.study_id not in wizard.available_study_ids:
                wizard.study_id = False

    # --- reading the certificate ----------------------------------------------

    @api.onchange('certificate_file')
    def _onchange_certificate_file(self):
        self.ensure_one()
        self.line_ids = [(5, 0, 0)]
        self.certificate_student_identifier = False
        self.certificate_student_name = False
        self.certificate_message = False
        if not self.certificate_file:
            return None
        pdf = base64.b64decode(self.certificate_file)
        if not pdf.startswith(b'%PDF'):
            return None
        try:
            certificate = parse_academic_record(pdf)
        except AcademicRecordPdfError:
            self.certificate_message = _("The file is not an Esfera academic record: fill in the "
                                         "record by hand and add its modules one by one.")
            return None
        # A course the history already holds (generated here by EMS, or added before) is left out;
        # anything else may be a record of this very centre from before EMS, or another centre's.
        taken = set(self.env['ems.student.year_record'].sudo().search(
            [('student_id', '=', self.student_id.id)]).course_id.mapped('name'))
        courses = [course for course in certificate['courses'] if course['course'] not in taken]
        if not courses:
            self.certificate_message = _("Every course of the certificate is already in the student's "
                                         "academic history.")
            return None
        self.certificate_student_identifier = certificate['student_identifier']
        self.certificate_student_name = certificate['student_name']
        self.origin_centre_code = courses[0]['centre_code']
        self.origin_centre_name = courses[0]['centre_name']
        self.study_id = self._study_from_code(certificate['study_code'])
        self.line_ids = self._line_commands(courses, certificate['study_code'])
        self.course_id = self.line_ids.course_id[:1]
        return self._certificate_warning()

    def _course_available(self, course):
        # By id: inside an onchange both sides may be new records wrapping the real ones.
        return bool(course) and course._origin.id in self.available_course_ids._origin.ids

    def _study_from_code(self, study_code):
        """The study whose EMS code ends with the certificate's (CFPM IC10 -> CFGM_IC10)."""
        if not study_code:
            return self.env['ems.study']
        return self.env['ems.study'].search([('code', '=like', f"%\\_{study_code}"),
                                             ('deprecated', '=', False)], limit=1)

    def _line_commands(self, courses, study_code):
        """One review line per module, learning outcome and work placement of the certificate, in
        its own order, each mapped to this centre's curriculum by code."""
        commands = []
        sequence = 0
        for course in courses:
            ems_course = self.env['ems.course'].search([('name', '=', course['course'])], limit=1)
            for module in course['modules']:
                subject = self._subject_from_code(module['code'], study_code)
                planning = self._planning(subject, ems_course)
                outcome_names = {self._plan_outcome_number(planning_outcome.outcome_id): planning_outcome.outcome_id.display_name
                                 for planning_outcome in planning.planning_outcome_ids}
                module_key = f"{course['course']}/{module['code']}"
                sequence += 1
                commands.append((0, 0, {
                    'sequence': sequence, 'kind': 'module', 'module_key': module_key,
                    'course_id': ems_course.id, 'certificate_course': course['course'],
                    'centre_code': course['centre_code'], 'centre_name': course['centre_name'],
                    'certificate_code': module['code'],
                    'label': module['name'], 'certificate_text': module['text'],
                    'subject_id': subject.id, 'score': module['grade'],
                    'is_scored': module['has_grade'],
                    'to_import': bool(planning) and self._course_available(ems_course),
                }))
                for outcome in module['outcomes']:
                    sequence += 1
                    commands.append((0, 0, {
                        'sequence': sequence,
                        'kind': 'outcome' if outcome['kind'] == 'ra' else 'placement',
                        'module_key': module_key, 'course_id': ems_course.id,
                        'certificate_code': outcome['code'], 'outcome_number': outcome['number'],
                        'label': outcome_names.get(outcome['number'], outcome['code'])
                        if outcome['kind'] == 'ra' else _("Work placement"),
                        'certificate_text': outcome['text'],
                        'score': outcome['score'], 'is_scored': outcome['is_scored'],
                    }))
        return commands

    def _subject_from_code(self, module_code, study_code):
        """A certificate module code ("0156_IC10") is this centre's subject code plus the study's
        token, the same rule as the Esfera grade import."""
        if not self.study_id:
            return self.env['ems.subject']
        code = module_code[:-len(study_code) - 1] if study_code and module_code.endswith(f"_{study_code}") \
            else module_code
        return self.env['ems.subject'].search([('code', '=', code),
                                               ('study_ids', '=', self.study_id.id)], limit=1)

    def _planning(self, subject, course):
        if not (subject and course and self.study_id):
            return self.env['ems.planning']
        return self.env['ems.planning'].sudo().search([
            ('study_id', '=', self.study_id.id), ('subject_id', '=', subject.id),
            ('course_id', '=', course.id)], limit=1)

    @api.model
    def _plan_outcome_number(self, outcome):
        match = _PLAN_OUTCOME_NUMBER_RE.search(outcome.code or '')
        return match.group(1) if match else None

    def _certificate_warning(self):
        identifier = self.certificate_student_identifier
        if identifier and self.student_id.student_id and identifier != self.student_id.student_id:
            return {'warning': {
                'title': _("Another student's certificate"),
                'message': _("The certificate belongs to %(name)s (%(identifier)s), not to this "
                             "student (%(own)s).", name=self.certificate_student_name,
                             identifier=identifier, own=self.student_id.student_id),
            }}
        return None

    @api.onchange('study_id')
    def _onchange_study_id(self):
        # The modules are mapped through the study: picking another one maps them again.
        for wizard in self.filtered('line_ids'):
            wizard._remap_lines()

    def _remap_lines(self):
        self.ensure_one()
        for line in self.line_ids.filtered(lambda line: line.kind == 'module'):
            study_code = (self.study_id.code or '').rsplit('_', 1)[-1]
            line.subject_id = self._subject_from_code(line.certificate_code, study_code)
            line.to_import = bool(self._planning(line.subject_id, line.course_id)) \
                and self._course_available(line.course_id)

    # --- creating the record ----------------------------------------------------

    def action_create(self):
        """Open the record of the course. From a certificate, with all its modules; otherwise, go
        straight on to add its first module through the grade review."""
        self.ensure_one()
        if not self.env['ems.base'].get_user_can_edit_history():
            raise UserError(_("Only the secretariat, the academic administration, the Head of "
                              "Studies and the Director may add a previous record."))
        if self.line_ids:
            return self._create_from_certificate()
        if not self.course_id:
            raise UserError(_("Pick the course of the record."))
        record = self._create_record(self.course_id)
        self._log_creation(record)
        return record.with_env(self.env).action_grade_review_add(resolution=self._resolution())

    def _resolution(self):
        return _("Academic certificate of %s", self.origin_centre_name)

    def _create_record(self, course, centre_code=None, centre_name=None):
        if not self._course_available(course):
            raise UserError(_("%(student)s already has an academic record for %(course)s, or the "
                              "course is not over yet.",
                              student=self.student_id.display_name, course=course.name))
        # sudo, as the grade review writes the history (see its _history()): the role was checked
        # by the caller, and the Head of Studies has no create right on the history otherwise.
        return self.env['ems.student.year_record'].sudo().create({
            'student_id': self.student_id.id,
            'course_id': course.id,
            'study_id': self.study_id.id,
            'study_name': self.study_id.display_name,
            'level_id': self.study_id.level_id.id,
            'level_name': self.study_id.level_id.display_name,
            'is_external': True,
            'origin_centre_name': centre_name or self.origin_centre_name,
            'origin_centre_code': centre_code or self.origin_centre_code,
            'certificate_file': self.certificate_file,
            'certificate_filename': self.certificate_filename,
        })

    def _create_from_certificate(self):
        identifier = self.certificate_student_identifier
        if identifier and self.student_id.student_id and identifier != self.student_id.student_id:
            raise UserError(self._certificate_warning()['warning']['message'])
        modules = self.line_ids.filtered(lambda line: line.kind == 'module' and line.to_import)
        if not modules:
            raise UserError(_("Tick at least one module to import."))
        for module in modules:
            if not module.subject_id or not self._planning(module.subject_id, module.course_id):
                raise UserError(_("%(module)s has no module of this study with a teaching plan that "
                                  "course: pick one or untick it.", module=module.certificate_code))
        # One centre (the usual case): the header, which the user may have corrected. Several (e.g.
        # this centre before EMS, then another one): each course keeps the centre that graded it.
        several_centres = len(set(modules.mapped('centre_code'))) > 1
        for course in modules.course_id:
            block = modules.filtered(lambda line: line.course_id == course)[:1] if several_centres \
                else self.env['ems.external_record_wizard.line']
            record = self._create_record(course, block.centre_code, block.centre_name)
            changes = [self._create_subject(record, module)
                       for module in modules.filtered(lambda line: line.course_id == course)]
            record.academic_result = record.grade_based_result()
            self._log_creation(record, changes)
        return {'type': 'ir.actions.act_window_close'}

    def _create_subject(self, record, module):
        """The subject record of one certificate module: its outcomes graded as the review grid
        says, through the very same helpers the grade review writes with."""
        planning = self._planning(module.subject_id, module.course_id)
        siblings = self.line_ids.filtered(lambda line: line.module_key == module.module_key)
        graded = {line.outcome_number: line for line in siblings if line.kind == 'outcome'}
        placement = siblings.filtered(lambda line: line.kind == 'placement')[:1]
        outcome_vals = []
        for planning_outcome in planning.planning_outcome_ids:
            line = graded.get(self._plan_outcome_number(planning_outcome.outcome_id))
            outcome_vals.append((0, 0, {
                'outcome_id': planning_outcome.outcome_id.id,
                'outcome_name': planning_outcome.outcome_id.display_name,
                'weight': planning_outcome.ponderation,
                'final_score': line.score if line else 0,
                'final_is_scored': bool(line and line.is_scored),
            }))
        subject_record = self.env['ems.student.year_record.subject'].sudo().create({
            'record_id': record.id,
            'subject_id': module.subject_id.id,
            'subject_name': module.subject_id.display_name,
            'internal_weight': planning.internal_ponderation,
            'external_weight': planning.external_ponderation,
            'outcome_record_ids': outcome_vals,
            'review_date': fields.Date.context_today(self),
            'review_user_id': self.env.user.id,
            'review_note': self._resolution(),
        })
        subject_record._recompute_from_outcomes()
        if placement.is_scored:
            subject_record.apply_external_grade(placement.score)
        # The certificate's own module grade prevails over the one this centre's RA weights give,
        # as long as both agree on passed / not passed (see _check_override_internal_grade).
        if module.is_scored and module.score != subject_record.internal_grade \
                and (module.score >= 5) == (subject_record.state == 'passed'):
            subject_record._force_internal_grade(module.score)
        return _("%(subject)s: %(state)s, grade %(grade)s",
                 subject=subject_record.subject_name,
                 state=dict(subject_record._fields['state']._description_selection(self.env)).get(
                     subject_record.state),
                 grade=subject_record.internal_grade)

    def _log_creation(self, record, changes=None):
        centre = self.origin_centre_name
        if self.origin_centre_code:
            centre = f"{centre} ({self.origin_centre_code})"
        body = Markup("<p>{}</p>").format(_(
            "Previous academic record of %(course)s (%(study)s) added by %(user)s: %(centre)s",
            course=record.course_id.name, study=self.study_id.display_name,
            user=self.env.user.name, centre=centre))
        if self.notes:
            body += Markup("<p>{}</p>").format(self.notes)
        if changes:
            body += base.EmsBase.build_html_list(self, changes)
        # Same as the grade review's own note: an automatic audit entry, not a message.
        self.student_id._message_log(body=body)


class EmsExternalRecordWizardLine(models.TransientModel):
    _name = 'ems.external_record_wizard.line'
    _description = 'External record wizard: one module, learning outcome or work placement of the certificate.'
    _order = 'sequence asc, id asc'

    wizard_id = fields.Many2one(string="Wizard", comodel_name='ems.external_record_wizard',
                                required=True, ondelete='cascade')
    sequence = fields.Integer(string="Sequence")
    kind = fields.Selection(string="Type", required=True, selection=[
        ('module', 'Module'),
        ('outcome', 'Learning outcome'),
        ('placement', 'Work placement'),
    ])
    # The certificate's course and module this line belongs to: what ties an outcome to its module.
    module_key = fields.Char(string="Module key")
    course_id = fields.Many2one(string="Course", comodel_name='ems.course', ondelete='cascade')
    # As printed on the certificate: what the warning names when the course is not in EMS.
    certificate_course = fields.Char(string="Certificate course")
    # The centre that graded this course: a certificate can hold courses of several centres
    # (this one before EMS included), and each record keeps its own.
    centre_code = fields.Char(string="Centre code")
    centre_name = fields.Char(string="Centre name")
    certificate_code = fields.Char(string="Certificate code", readonly=True)
    label = fields.Char(string="Name", readonly=True)
    certificate_text = fields.Char(string="Certificate grade", readonly=True)
    outcome_number = fields.Char(string="Outcome number")
    subject_id = fields.Many2one(string="Module", comodel_name='ems.subject', ondelete='cascade')
    score = fields.Integer(string="Grade")
    is_scored = fields.Boolean(string="Graded")
    to_import = fields.Boolean(string="Import")
    warning = fields.Char(string="Warning", compute='_compute_warning')

    @api.depends('subject_id', 'to_import', 'score', 'is_scored', 'wizard_id.study_id',
                 'wizard_id.line_ids.score', 'wizard_id.line_ids.is_scored')
    def _compute_warning(self):
        for line in self:
            line.warning = line._module_warning() if line.kind == 'module' else False

    def _module_warning(self):
        wizard = self.wizard_id
        if not self.course_id:
            return _("The course %s does not exist in EMS: not imported.", self.certificate_course)
        if not wizard._course_available(self.course_id):
            return _("The course %s is not over yet: not imported.", self.course_id.name)
        if not self.subject_id:
            return _("Not a module of this study: not imported.")
        planning = wizard._planning(self.subject_id, self.course_id)
        if not planning:
            return _("No teaching plan for this module that course.")
        if not self.to_import:
            return False
        siblings = wizard.line_ids.filtered(
            lambda line: line.module_key == self.module_key and line.kind == 'outcome')
        numbers = {wizard._plan_outcome_number(planning_outcome.outcome_id): planning_outcome.ponderation
                   for planning_outcome in planning.planning_outcome_ids}
        missing = len(set(numbers) - set(siblings.mapped('outcome_number')))
        if missing:
            return _("%s learning outcomes of the teaching plan are not on the certificate.", missing)
        scored = [(line.score, numbers[line.outcome_number]) for line in siblings
                  if line.is_scored and line.outcome_number in numbers]
        values = self.env['ems.student.year_record.subject']._values_from_outcomes(
            scored, len(numbers), 0, False, planning.internal_ponderation, planning.external_ponderation)
        if self.is_scored and self.score != values['internal_grade']:
            if (self.score >= 5) != (values['state'] == 'passed'):
                return _("The learning outcomes give %s on the other side of 5: the module grade "
                         "cannot be applied.", values['internal_grade'])
            return _("The learning outcomes give %(grade)s: the certificate's %(certificate)s is applied.",
                     grade=values['internal_grade'], certificate=self.score)
        return False
