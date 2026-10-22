# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

RUBRIC = [(str(points), str(points)) for points in range(6)]
GENERAL_CRITERIA = ('motivation', 'maturity', 'difficulties', 'adaptation')
ENGLISH_CRITERIA = ('comprehension', 'fluency', 'accuracy')
# What an evaluator may write on their own interview: the rubric and their notes.
EVALUATOR_FIELDS = set(GENERAL_CRITERIA + ENGLISH_CRITERIA) | {'notes'}


class EmsErasmusInterview(models.Model):
    """Issue #684 - one evaluator's score of an applicant's interview, with annex 4's rubric.
    The Erasmus team assigns two evaluators per applicant; each one sees only their own
    interviews. See docs/en/developers/erasmus/erasmus.md."""
    _name = 'ems.erasmus.interview'
    _description = 'Erasmus+ interview'
    _inherit = ['ems.base']
    _order = 'interview_date, partner_id, id'
    _sql_constraints = [
        ('application_evaluator_unique', 'unique(application_id, evaluator_id)',
         "An evaluator scores each interview only once."),
    ]

    application_id = fields.Many2one(string="Application", comodel_name='ems.erasmus.application', required=True,
                                     ondelete='cascade', index=True)
    evaluator_id = fields.Many2one(string="Evaluator", comodel_name='res.users', required=True, ondelete='restrict',
                                   index=True, tracking=True, domain="[('share', '=', False)]")
    partner_id = fields.Many2one(string="Applicant", related='application_id.partner_id', store=True)
    call_name = fields.Char(string="Call", related='application_id.call_id.name')
    modality_name = fields.Char(string="Modality", related='application_id.modality_id.name')
    interview_date = fields.Datetime(string="Interview date", related='application_id.interview_date', store=True)
    interview_place = fields.Char(string="Interview place", related='application_id.interview_place')
    state = fields.Selection(string="State", required=True, default='draft', tracking=True, copy=False,
                             selection=[('draft', "To score"), ('submitted', "Submitted")])
    submit_date = fields.Datetime(string="Submitted on", readonly=True, copy=False)
    is_locked = fields.Boolean(string="Locked", compute='_compute_is_locked', compute_sudo=True,
                               help="The call's interview review deadline has passed, or the provisional "
                                    "resolution is published: only the Erasmus team can reopen it, with a "
                                    "rectification note.")

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
    notes = fields.Text(string="Evaluator's notes")
    rectification_note = fields.Text(string="Rectification note",
                                     help="Why the Erasmus team reopens the interview after the review deadline.")

    @api.depends(*GENERAL_CRITERIA, *ENGLISH_CRITERIA)
    def _compute_scores(self):
        for interview in self:
            interview.general_score = sum(int(interview[name] or 0) for name in GENERAL_CRITERIA)
            interview.english_score = sum(int(interview[name] or 0) for name in ENGLISH_CRITERIA)

    @api.depends('application_id.call_id.interview_deadline', 'application_id.call_id.resolution_ids.state')
    def _compute_is_locked(self):
        """Locked at the review deadline, or when the provisional resolution is published if that
        comes first (issue #685)."""
        for interview in self:
            call = interview.application_id.call_id
            deadline = call.interview_deadline
            interview.is_locked = (bool(deadline) and deadline <= call._ems_now()) or bool(
                call.resolution_ids.filtered(lambda resolution: resolution.state == 'published'
                                             and resolution.kind != 'admission'))

    def _compute_display_name(self):
        for interview in self:
            interview.display_name = f"{interview.partner_id.name} - {interview.evaluator_id.name}"

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su and not self._ems_can_manage():
            raise AccessError(_("Only the Erasmus team assigns interviews."))
        interviews = super().create(vals_list)
        for interview in interviews:
            interview._ems_schedule_activity()
        interviews.evaluator_id._ems_sync_erasmus_evaluator_group()
        return interviews

    def write(self, vals):
        if not self.env.su and not self._ems_can_manage():
            if set(vals) - EVALUATOR_FIELDS:
                raise AccessError(_("An evaluator only scores the rubric of their interviews."))
            for interview in self:
                interview._ems_check_evaluator_can_change()
        if set(vals) & set(GENERAL_CRITERIA + ENGLISH_CRITERIA) and self.filtered(
                lambda interview: interview.state == 'submitted'):
            raise UserError(_("Reopen the interview before changing its scores."))
        previous_evaluators = self.evaluator_id if 'evaluator_id' in vals else self.env['res.users']
        result = super().write(vals)
        if previous_evaluators:
            self.activity_ids.sudo().write({'user_id': vals['evaluator_id']})
            (previous_evaluators | self.evaluator_id)._ems_sync_erasmus_evaluator_group()
        return result

    def unlink(self):
        evaluators = self.evaluator_id
        result = super().unlink()
        evaluators._ems_sync_erasmus_evaluator_group()
        return result

    def action_submit(self):
        for interview in self:
            interview._ems_check_evaluator_can_change()
            missing = [interview._fields[name].string for name in GENERAL_CRITERIA + ENGLISH_CRITERIA
                       if not interview[name]]
            if missing:
                raise UserError(_("Score every criterion first: %s", ", ".join(missing)))
        self.sudo().write({'state': 'submitted', 'submit_date': fields.Datetime.now()})
        self.sudo().activity_feedback(['mail.mail_activity_data_todo'])

    def action_reopen(self):
        """The evaluator reopens their own interview until the review deadline; afterwards only
        the Erasmus team can, writing why (a rectification)."""
        for interview in self:
            if interview.state != 'submitted':
                raise UserError(_("The interview is not submitted."))
            if not interview.is_locked:
                interview._ems_check_evaluator_can_change()
                continue
            if not self._ems_can_manage():
                raise UserError(_("The review deadline has passed: only the Erasmus team can reopen it."))
            if not (interview.rectification_note or '').strip():
                raise UserError(_("Write the rectification note before reopening after the review deadline."))
            interview.chatter(_("Reopened after the review deadline: %s", interview.rectification_note))
        self.sudo().write({'state': 'draft', 'rectification_note': False})

    def _ems_check_evaluator_can_change(self):
        """An evaluator changes only their own interview, before the review deadline; the
        Erasmus team any of them."""
        self.ensure_one()
        if self.env.su or self._ems_can_manage():
            return
        if self.evaluator_id != self.env.user:
            raise AccessError(_("This interview is assigned to someone else."))
        if self.is_locked:
            raise UserError(_("The review deadline has passed: the interview can no longer be changed."))

    def _ems_schedule_activity(self):
        self.ensure_one()
        deadline = self.interview_date or self.application_id.call_id.interview_deadline
        self.sudo().activity_schedule(
            'mail.mail_activity_data_todo', user_id=self.evaluator_id.id,
            date_deadline=deadline and fields.Date.to_date(deadline) or fields.Date.context_today(self),
            summary=_("Score the Erasmus+ interview of %s", self.partner_id.name))

    def _ems_can_manage(self):
        return self.env['ems.erasmus.application']._ems_can_manage()


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


class ResUsers(models.Model):
    _inherit = 'res.users'

    def _ems_sync_erasmus_evaluator_group(self):
        """Issue #684: *Erasmus+ > My evaluations* is for whoever has an interview assigned."""
        group = self.env.ref('ems.group_erasmus_evaluator')
        assigned = self.env['ems.erasmus.interview'].sudo().search([('evaluator_id', 'in', self.ids)]).evaluator_id
        (self & (assigned - group.users)).sudo().write({'groups_id': [(4, group.id)]})
        ((self - assigned) & group.users).sudo().write({'groups_id': [(3, group.id)]})
