# -*- coding: utf-8 -*-

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError

# A course the student took at another centre - typically the first year of a study whose second
# year they come here to take - typed in from that centre's academic certificate (issue #585).
# This wizard only opens the record of that course; its modules are then added one by one through
# the grade review's own "add a missing subject" operation, which already builds the learning
# outcome (RA) grid from the teaching plan, computes the grades with the grading formulas and lets
# the internal grade be forced to match the certificate (issue #503). A module whose work
# placement grade is still missing is left with its final pending, which is what makes the EM
# grading wizard offer it to the student's current tutor.


class EmsExternalRecordWizard(models.TransientModel):
    _name = 'ems.external_record_wizard'
    _description = 'External record wizard: academic history of a course taken at another centre.'

    student_id = fields.Many2one(string="Student", comodel_name='res.partner', required=True,
                                 ondelete='cascade')
    course_id = fields.Many2one(string="Course", comodel_name='ems.course', required=True,
                                ondelete='cascade')
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

    @api.depends('course_id')
    def _compute_available_study_ids(self):
        for wizard in self:
            plannings = self.env['ems.planning'].sudo().search([
                ('course_id', '=', wizard.course_id.id), ('planning_outcome_ids', '!=', False)])
            wizard.available_study_ids = plannings.study_id

    @api.onchange('course_id')
    def _onchange_course_id(self):
        for wizard in self:
            if wizard.study_id not in wizard.available_study_ids:
                wizard.study_id = False

    def action_create(self):
        """Open the record of the course and go straight on to add its first module."""
        self.ensure_one()
        if not self.env['ems.base'].get_user_can_edit_history():
            raise UserError(_("Only the secretariat, the academic administration, the Head of "
                              "Studies and the Director may add a record from another centre."))
        YearRecord = self.env['ems.student.year_record'].sudo()
        if YearRecord.search_count([('student_id', '=', self.student_id.id),
                                    ('course_id', '=', self.course_id.id)]):
            raise UserError(_("%(student)s already has an academic record for %(course)s.",
                              student=self.student_id.display_name, course=self.course_id.name))
        # sudo, as the grade review writes the history (see its _history()): the role was checked
        # just above, and the Head of Studies has no create right on the history otherwise.
        record = YearRecord.create({
            'student_id': self.student_id.id,
            'course_id': self.course_id.id,
            'study_id': self.study_id.id,
            'study_name': self.study_id.display_name,
            'level_id': self.study_id.level_id.id,
            'level_name': self.study_id.level_id.display_name,
            'is_external': True,
            'origin_centre_name': self.origin_centre_name,
            'origin_centre_code': self.origin_centre_code,
            'certificate_file': self.certificate_file,
            'certificate_filename': self.certificate_filename,
        })
        self._log_creation()
        return record.with_env(self.env).action_grade_review_add(
            resolution=_("Academic certificate of %s", self.origin_centre_name))

    def _log_creation(self):
        self.ensure_one()
        centre = self.origin_centre_name
        if self.origin_centre_code:
            centre = f"{centre} ({self.origin_centre_code})"
        body = Markup("<p>{}</p>").format(_(
            "Academic record of %(course)s (%(study)s) added from another centre by %(user)s: %(centre)s",
            course=self.course_id.name, study=self.study_id.display_name,
            user=self.env.user.name, centre=centre))
        if self.notes:
            body += Markup("<p>{}</p>").format(self.notes)
        # Same as the grade review's own note: an automatic audit entry, not a message.
        self.student_id._message_log(body=body)
