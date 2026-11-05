# -*- coding: utf-8 -*-

from datetime import timedelta

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError

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
        return self.env['ems.base'].ems_elide(_("Score the Erasmus+ interview of %s", self.partner_id.name))

    def action_submit_next(self):
        """Submit and open the next interview this evaluator still has to score."""
        self.ensure_one()
        self.action_submit()
        following = self.search([('evaluator_id', '=', self.env.uid), ('state', '=', 'draft'),
                                 ('id', '!=', self.id)], limit=1)
        if not following:
            return self.env['ir.actions.act_window']._for_xml_id('ems.action_erasmus_my_interviews')
        return {'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': following.id,
                'view_mode': 'form', 'views': [(False, 'form')], 'target': 'current'}


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


class EmsErasmusInterviewSchedule(models.TransientModel):
    """The issue-#682 review: the interviews of many admitted applicants at once, in consecutive
    slots of the same place and evaluators, instead of application by application."""
    _name = 'ems.erasmus.interview.schedule'
    _description = 'Erasmus+ interview schedule'

    call_id = fields.Many2one(string="Call", comodel_name='ems.erasmus.call', required=True)
    modality_id = fields.Many2one(string="Modality", comodel_name='ems.erasmus.call.modality',
                                  domain="[('call_id', '=', call_id)]",
                                  help="Empty: the admitted applicants of every modality.")
    application_ids = fields.Many2many(
        string="Applicants", comodel_name='ems.erasmus.application', compute='_compute_application_ids', store=True,
        readonly=False, domain="[('call_id', '=', call_id), ('state', '=', 'admitted')]",
        help="In this order. By default, the admitted applicants without an interview date yet.")
    date_start = fields.Datetime(string="First interview", required=True)
    duration = fields.Integer(string="Minutes per interview", required=True, default=20)
    place = fields.Char(string="Place", required=True)
    evaluator_ids = fields.Many2many(string="Evaluators", comodel_name='res.users',
                                     domain="[('share', '=', False)]",
                                     help="Usually two: each one scores every interview of these slots.")
    send_call = fields.Boolean(string="Send the interview calls", default=True,
                               help="Emails each applicant the date and place (at least 24 hours ahead).")

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        values.setdefault('call_id', self.env.context.get('active_id'))
        return values

    @api.depends('call_id', 'modality_id')
    def _compute_application_ids(self):
        for wizard in self:
            wizard.application_ids = wizard.call_id.application_ids.filtered(
                lambda application: application.state == 'admitted' and not application.interview_date
                and (not wizard.modality_id or application.modality_id == wizard.modality_id)).sorted(
                lambda application: (application.modality_id.sequence, application.partner_id.name))

    def action_confirm(self):
        self.ensure_one()
        if not self.env['ems.erasmus.application']._ems_can_manage():
            raise UserError(_("Only the Erasmus team schedules the interviews."))
        if not self.application_ids:
            raise UserError(_("There is nobody to schedule."))
        if self.duration <= 0:
            raise UserError(_("Each interview needs some minutes."))
        # One task per interview (each one closes when it is scored), scheduled quietly: each
        # evaluator gets a single notice with the whole list instead of an email per interview.
        Interview = self.env['ems.erasmus.interview'].with_context(mail_activity_quick_update=True)
        created = Interview
        for index, application in enumerate(self.application_ids):
            application.write({'interview_date': self.date_start + timedelta(minutes=index * self.duration),
                               'interview_place': self.place})
            missing = self.evaluator_ids - application.interview_ids.evaluator_id
            created |= Interview.create([{'application_id': application.id, 'evaluator_id': user.id}
                                         for user in missing])
        self._ems_notify_evaluators(created)
        if self.send_call:
            self.application_ids.action_send_interview_call()
        return {'type': 'ir.actions.act_window_close'}

    def _ems_notify_evaluators(self, interviews):
        """One notice per evaluator with the interviews just assigned (date and time, place and
        applicant, in their language), in their next daily summary (ems.info_notice) next to the
        scoring tasks: not urgent, so never an email on the spot."""
        Call = self.env['ems.erasmus.call']
        for evaluator in interviews.evaluator_id:
            own = interviews.filtered(lambda interview: interview.evaluator_id == evaluator).sorted('interview_date')
            env = self.with_context(lang=evaluator.lang or self.env.lang).env
            body = Markup("<p>{}</p>{}").format(
                env._("Erasmus+: you have %(count)s interviews to score in %(call)s. Each one is a task in "
                      "Erasmus+ > My evaluations.", count=len(own), call=self.call_id.name),
                self.env['ems.base'].build_html_list([
                    f"{Call._ems_local_format(interview.interview_date)} - {interview.interview_place} - "
                    f"{interview.partner_id.name}" for interview in own]))
            self.env['ems.info_notice']._ems_queue(evaluator, self.call_id, lambda _user, body=body: body)
