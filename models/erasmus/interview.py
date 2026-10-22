# -*- coding: utf-8 -*-

from odoo import _, api, fields, models

RUBRIC = [(str(points), str(points)) for points in range(6)]
GENERAL_CRITERIA = ('motivation', 'maturity', 'difficulties', 'adaptation')
ENGLISH_CRITERIA = ('comprehension', 'fluency', 'accuracy')


class EmsErasmusInterview(models.Model):
    """Issue #684 - one evaluator's score of an applicant's interview, with annex 4's rubric.
    The Erasmus team assigns two evaluators per applicant; each one sees only their own
    interviews. The evaluator's workflow is ems.erasmus.evaluation's. See
    docs/en/developers/erasmus/erasmus.md."""
    _name = 'ems.erasmus.interview'
    _description = 'Erasmus+ interview'
    _inherit = ['ems.erasmus.evaluation']
    _order = 'interview_date, partner_id, id'
    _sql_constraints = [
        ('application_evaluator_unique', 'unique(application_id, evaluator_id)',
         "An evaluator scores each interview only once."),
    ]
    _ems_criteria = GENERAL_CRITERIA + ENGLISH_CRITERIA

    evaluator_id = fields.Many2one(required=True)
    modality_name = fields.Char(string="Modality", related='application_id.modality_id.name')
    interview_date = fields.Datetime(string="Interview date", related='application_id.interview_date', store=True)
    interview_place = fields.Char(string="Interview place", related='application_id.interview_place')

    motivation = fields.Selection(string="Motivation", selection=RUBRIC, tracking=True,
                                  help="0-1: mainly living abroad or leisure, unrelated to the cycle. 2-3: "
                                       "general training motivation. 4-5: explains what they want to learn, how it "
                                       "relates to the cycle and their future, and how they expect to grow.")
    maturity = fields.Selection(string="Maturity, autonomy and money management", selection=RUBRIC, tracking=True,
                                help="0-1: no idea of living alone abroad or of the expenses. 2-3: a general idea, "
                                     "with gaps. 4-5: knows how to organise travel, housing, food and the grant.")
    difficulties = fields.Selection(string="Handling difficulties", selection=RUBRIC, tracking=True,
                                    help="0-1: would give up or keep quiet. 2-3: aware of difficulties, vague "
                                         "answers. 4-5: would talk to the company and the Erasmus coordination, "
                                         "look for solutions and not give up.")
    adaptation = fields.Selection(string="Adaptation and communication", selection=RUBRIC, tracking=True,
                                  help="0-1: very short or unclear answers. 2-3: communicates correctly. 4-5: "
                                       "clear and confident, open to other cultures and ways of working.")
    comprehension = fields.Selection(string="Comprehension", selection=RUBRIC, tracking=True,
                                     help="0-1: does not understand most questions. 2-3: understands simple "
                                          "questions. 4-5: understands without difficulty, work questions too.")
    fluency = fields.Selection(string="Fluency and interaction", selection=RUBRIC, tracking=True,
                               help="0-1: single words. 2-3: a simple conversation with pauses and help. 4-5: "
                                    "fluent, asks and reacts naturally.")
    accuracy = fields.Selection(string="Accuracy, vocabulary and pronunciation", selection=RUBRIC, tracking=True,
                                help="0-1: constant errors, hard to understand. 2-3: errors that do not prevent "
                                     "understanding. 4-5: few errors, varied and professional vocabulary.")
    general_score = fields.Integer(string="General part (max 20)", compute='_compute_scores', store=True)
    english_score = fields.Integer(string="English part (max 15)", compute='_compute_scores', store=True)

    @api.depends(*GENERAL_CRITERIA, *ENGLISH_CRITERIA)
    def _compute_scores(self):
        for interview in self:
            interview.general_score = sum(int(interview[name] or 0) for name in GENERAL_CRITERIA)
            interview.english_score = sum(int(interview[name] or 0) for name in ENGLISH_CRITERIA)

    def _compute_display_name(self):
        for interview in self:
            interview.display_name = f"{interview.partner_id.name} - {interview.evaluator_id.name}"

    def _ems_activity_deadline(self):
        return self.interview_date or super()._ems_activity_deadline()

    def _ems_activity_summary(self):
        return _("Score the Erasmus+ interview of %s", self.partner_id.name)


class EmsErasmusApplicationGrade(models.Model):
    """Issue #684 - a module used for an application's record average (criterion A), copied
    when the call closed."""
    _name = 'ems.erasmus.application.grade'
    _description = 'Erasmus+ application record module'
    _order = 'application_id, course_name, subject_name'

    application_id = fields.Many2one(string="Application", comodel_name='ems.erasmus.application', required=True,
                                     ondelete='cascade', index=True)
    subject_id = fields.Many2one(string="Module", comodel_name='ems.subject', ondelete='set null')
    subject_name = fields.Char(string="Module name")
    course_name = fields.Char(string="Course")
    grade = fields.Integer(string="Grade")
    hours = fields.Integer(string="Hours")

