# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

# Annex 2 of the staff call: each aspect 0, 0.5 or 1.
PLAN_RUBRIC = [('0', "0"), ('0.5', "0.5"), ('1', "1")]
PLAN_CRITERIA = ('relevance', 'transfer')
# Art. 11 of the staff call, criteria 3 and 6: points per merit and the criterion it counts for.
MERIT_POINTS = {'project_collaboration': 0.5, 'project_coordination': 1.0, 'internationalisation': 0.5}
PROJECT_MERITS = ('project_collaboration', 'project_coordination')


class EmsErasmusCallPanel(models.Model):
    """Issue #686 - a member of the panel that rates the staff's mobility plans, configured per
    call (art. 10 of the staff call)."""
    _name = 'ems.erasmus.call.panel'
    _description = 'Erasmus+ call panel member'
    _order = 'call_id, sequence, id'
    _sql_constraints = [
        ('call_user_unique', 'unique(call_id, user_id)', "A person can only be once in the panel of a call."),
    ]

    call_id = fields.Many2one(string="Call", comodel_name='ems.erasmus.call', required=True, ondelete='cascade',
                              index=True)
    sequence = fields.Integer(string="Sequence", default=10)
    user_id = fields.Many2one(string="Member", comodel_name='res.users', required=True, ondelete='restrict',
                              domain="[('share', '=', False)]")
    post = fields.Char(string="Post", help="Why they are in the panel, e.g. Director, Head of department.")


class EmsErasmusPlanRating(models.Model):
    """Issue #686 - one panel member's rating of a staff applicant's mobility plan, with annex 2's
    rubric. Every panel member rates every plan; a member who abstains (a candidate in the call,
    or a conflict of interest) does not, and the plan's score is the mean of the others (decided
    with the coordinator 2026-10-22: no substitutes). The evaluator's workflow is
    ems.erasmus.evaluation's. See
    docs/en/developers/erasmus/erasmus.md."""
    _name = 'ems.erasmus.plan_rating'
    _description = 'Erasmus+ mobility plan rating'
    _inherit = ['ems.erasmus.evaluation']
    _order = 'partner_id, panel_member_id, id'
    _sql_constraints = [
        ('application_member_unique', 'unique(application_id, panel_member_id)',
         "Each panel member rates each plan only once."),
    ]
    _ems_criteria = PLAN_CRITERIA

    panel_member_id = fields.Many2one(string="Panel member", comodel_name='res.users', required=True,
                                      ondelete='restrict', index=True)
    abstention_reason = fields.Text(string="Abstention reason", tracking=True,
                                    help="Why the panel member does not rate this plan. The plan's score is the mean "
                                         "of the other members' ratings.")
    relevance = fields.Selection(string="Relevance and concreteness", selection=PLAN_RUBRIC, tracking=True,
                                 help="0: no relation with the job or the training cycles, generic objectives and "
                                      "activity. 0.5: a general relation, or objectives and activity not very "
                                      "concrete. 1: a clear relation with the job, the department and the training "
                                      "cycles, concrete objectives and the entity or course named.")
    transfer = fields.Selection(string="Application and dissemination", selection=PLAN_RUBRIC, tracking=True,
                                help="0: no application nor dissemination planned. 0.5: application or "
                                     "dissemination not very concrete. 1: a concrete application to the job and the "
                                     "students, and a defined dissemination proposal.")
    score = fields.Float(string="Score (max 2)", digits=(3, 1), compute='_compute_score', store=True)
    plan_attachment_ids = fields.Many2many(string="Mobility plan", comodel_name='ir.attachment',
                                           compute='_compute_plan_attachment_ids', compute_sudo=True,
                                           help="The files of the documents the call shows to the panel.")

    @api.depends(*PLAN_CRITERIA)
    def _compute_score(self):
        for rating in self:
            rating.score = sum(float(rating[name] or 0) for name in PLAN_CRITERIA)

    @api.depends('application_id.document_ids.attachment_ids')
    def _compute_plan_attachment_ids(self):
        for rating in self:
            rating.plan_attachment_ids = rating.application_id.document_ids.filtered(
                'call_document_id.panel_visible').attachment_ids

    @api.constrains('evaluator_id', 'panel_member_id', 'abstention_reason')
    def _check_evaluator(self):
        for rating in self:
            if rating.evaluator_id not in (rating.panel_member_id, self.env['res.users']):
                raise ValidationError(_("Only the panel member rates their plans."))
            if rating.evaluator_id and rating.evaluator_id.partner_id in rating.application_id.call_id \
                    ._ems_candidate_partners():
                raise ValidationError(_("%s is a candidate in this call and cannot rate.", rating.evaluator_id.name))

    def write(self, vals):
        """An abstention (team only, see ems.erasmus.evaluation.write) leaves the rating without
        evaluator; withdrawing it gives it back to the panel member."""
        if 'abstention_reason' not in vals:
            return super().write(vals)
        reason = (vals['abstention_reason'] or '').strip()
        result = True
        for member, ratings in self.grouped('panel_member_id').items():
            result &= super(EmsErasmusPlanRating, ratings).write({**vals, 'evaluator_id': not reason and member.id})
        return result

    def _compute_display_name(self):
        for rating in self:
            rating.display_name = f"{rating.partner_id.name} - {rating.panel_member_id.name}"

    def _ems_activity_summary(self):
        return _("Rate the Erasmus+ mobility plan of %s", self.partner_id.name)


class EmsErasmusApplicationMerit(models.Model):
    """Issue #686 - a merit of a staff applicant, recorded by the Erasmus team with its
    justification (art. 11 of the staff call): a collaboration in a centre project (0.5) or its
    coordination (1), criterion 3, max 1.5; an internationalisation activity (0.5), criterion 6,
    max 1."""
    _name = 'ems.erasmus.application.merit'
    _description = 'Erasmus+ staff merit'
    _order = 'application_id, kind, id'

    application_id = fields.Many2one(string="Application", comodel_name='ems.erasmus.application', required=True,
                                     ondelete='cascade', index=True)
    kind = fields.Selection(string="Kind", required=True, selection=[
        ('project_collaboration', "Collaboration in a centre project (0.5)"),
        ('project_coordination', "Coordination of a centre project (1)"),
        ('internationalisation', "Internationalisation activity (0.5)")])
    description = fields.Char(string="Justification", required=True,
                              help="Which project, commission or activity, and in which course.")
    points = fields.Float(string="Points", digits=(3, 1), compute='_compute_points')

    @api.depends('kind')
    def _compute_points(self):
        for merit in self:
            merit.points = MERIT_POINTS.get(merit.kind, 0.0)
