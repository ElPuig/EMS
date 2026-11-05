# -*- coding: utf-8 -*-

from markupsafe import Markup

from odoo import _, api, fields, models

QUESTION_KINDS = [('text', "Text"), ('rating', "Rating from 1 to 5")]


class EmsErasmusCallQuestion(models.Model):
    """Issue #697 - one question of a call's weekly self-assessment during the stay."""
    _name = 'ems.erasmus.call.question'
    _description = 'Erasmus+ self-assessment question'
    _order = 'call_id, sequence, id'

    call_id = fields.Many2one(string="Call", comodel_name='ems.erasmus.call', required=True, ondelete='cascade',
                              index=True)
    sequence = fields.Integer(string="Sequence", default=10)
    name = fields.Char(string="Question", required=True)
    kind = fields.Selection(string="Answer", selection=QUESTION_KINDS, required=True, default='text')


class EmsErasmusSelfAssessment(models.Model):
    """Issue #697 - what a participant answers about one week of their stay, from the portal."""
    _name = 'ems.erasmus.self_assessment'
    _description = 'Erasmus+ weekly self-assessment'
    _order = 'mobility_id, week'
    _sql_constraints = [
        ('week_unique', 'unique(mobility_id, week)', "A week of a mobility is self-assessed only once."),
    ]

    mobility_id = fields.Many2one(string="Mobility", comodel_name='ems.erasmus.mobility', required=True,
                                  ondelete='cascade', index=True, readonly=True)
    partner_id = fields.Many2one(string="Participant", related='mobility_id.partner_id')
    week = fields.Integer(string="Week", required=True, readonly=True)
    date_from = fields.Date(string="From", readonly=True)
    date_to = fields.Date(string="To", readonly=True)
    answer_ids = fields.One2many(string="Answers", comodel_name='ems.erasmus.self_assessment.answer',
                                 inverse_name='assessment_id', readonly=True)
    rating = fields.Integer(string="Rating", compute='_compute_answers',
                            help="The week's rating from 1 to 5, when the self-assessment has one.")
    answers_html = fields.Html(string="Answers given", compute='_compute_answers', sanitize=False)

    @api.depends('answer_ids.rating', 'answer_ids.text', 'answer_ids.question')
    def _compute_answers(self):
        """The answers as the participant gave them, for the mobility form and the PDF."""
        for assessment in self:
            assessment.rating = max(assessment.answer_ids.mapped('rating'), default=0)
            assessment.answers_html = Markup('').join(
                Markup('<p><strong>{}</strong><br/><span style="white-space: pre-line;">{}</span></p>').format(
                    answer.question, f"{answer.rating} / 5" if answer.kind == 'rating' else answer.text or '')
                for answer in assessment.answer_ids)

    @api.depends('week', 'partner_id')
    def _compute_display_name(self):
        for assessment in self:
            week = _("Week %s", assessment.week)
            assessment.display_name = f"{assessment.partner_id.name} - {week}"


class EmsErasmusSelfAssessmentAnswer(models.Model):
    """Issue #697 - the answer to one question; it keeps the question as it was asked."""
    _name = 'ems.erasmus.self_assessment.answer'
    _description = 'Erasmus+ self-assessment answer'
    _order = 'assessment_id, id'

    assessment_id = fields.Many2one(string="Self-assessment", comodel_name='ems.erasmus.self_assessment',
                                    required=True, ondelete='cascade', index=True)
    question_id = fields.Many2one(string="Question of the call", comodel_name='ems.erasmus.call.question',
                                  ondelete='set null')
    question = fields.Char(string="Question", required=True)
    kind = fields.Selection(string="Answer type", selection=QUESTION_KINDS, required=True)
    rating = fields.Integer(string="Rating")
    text = fields.Text(string="Answer")
