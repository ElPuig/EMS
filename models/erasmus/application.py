# -*- coding: utf-8 -*-

import base64
import io
from datetime import timedelta

import xlsxwriter
from pytz import UTC

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from .plan_rating import PROJECT_MERITS
from .records import PARTICIPANT_CATEGORIES, STAGE_CATEGORIES, check_upload
from .workflow import check_kept, check_workflow_create, check_workflow_write

# Who reads what only the Erasmus team handles (confidential evidence, the criteria of the score).
TEAM = 'ems.group_erasmus,ems.group_academic_admin'
CHECK_STATES = [('pending', "Pending"), ('met', "Met"), ('not_met', "Not met")]
YES_NO = [('yes', "Yes"), ('no', "No")]
# Criterion C (art. 12): the highest language certificate.
LANGUAGE_SCORES = {'none': 0.0, 'b1': 2.5, 'b2': 5.0, 'c1': 7.5, 'c2': 10.0}
# Values set by hand that keep who set them and when (<field>_user_id, <field>_date).
STAMPED_FIELDS = ('requirements_check', 'language_level', 'fewer_opportunities_check',
                  'first_mobility', 'last_staff_mobility', 'seniority', 'merits_checked')
# Application states whose data is frozen when the call closes.
SUBMITTED_STATES = ('submitted', 'subsanation', 'admitted', 'excluded')
# Application states that compete in the ranking (issue #685): admitted, and the results after it.
RANKED_STATES = ('admitted', 'selected', 'reserve', 'not_selected', 'accepted', 'renounced')
# The criteria and total a resolution freezes on its lines.
SCORE_FIELDS = ('score_a', 'score_b', 'score_c', 'score_d', 'score_e', 'score_f', 'score_total')
# Issue #686: the staff call's criteria (art. 11), frozen too.
STAFF_SCORE_FIELDS = ('score_plan', 'score_last_mobility', 'score_projects', 'score_staff_language',
                      'score_seniority', 'score_internationalisation')
# Criterion 4 of the staff call: from B2, the highest certificate.
STAFF_LANGUAGE_SCORES = {'b2': 1.0, 'c1': 1.5, 'c2': 2.0}
# Criterion 2: the last staff mobility. Criterion 5: continuous seniority at the closing date.
LAST_MOBILITY_SCORES = {'never': 1.5, 'older': 1.5, 'two_courses': 0.5, 'recent': 0.0}
SENIORITY_SCORES = {'y0': 0.0, 'y1': 1.0, 'y2': 1.5, 'y5': 2.0}
LAST_MOBILITY_BANDS = [('never', "Never"), ('older', "More than two courses ago"), ('two_courses', "Two courses ago"),
                       ('recent', "Last course or this one")]
SENIORITY_BANDS = [('y0', "Less than 1 year"), ('y1', "1 to less than 2 years"), ('y2', "2 to less than 5 years"),
                   ('y5', "5 years or more")]
# Issue #685: "Export to spreadsheet". An external tool imports the file as is, so the sheet name and
# the headers are fixed, in Spanish, in this order, and are never translated.
PARTICIPANT_SHEET = 'Participantes'
PARTICIPANT_HEADERS = ('Nombre', 'Apellidos', 'DNI', 'Email', 'Teléfono', 'Dirección', 'Fecha de nacimiento',
                       'Nacionalidad', 'Género', 'Ciclo formativo', 'Curso', 'Titular de la cuenta', 'Banco', 'BIC',
                       'IBAN', 'Tutor legal', 'Email del tutor legal', 'Teléfono del tutor legal')
# Answers of the portal form, editable by the applicant while the call accepts applications.
ANSWER_FIELDS = {
    'student': ('previous_mobility', 'previous_mobility_details', 'availability', 'fewer_opportunities',
                'image_consent', 'applicant_notes'),
    'staff': ('staff_activity', 'host_entity', 'destination', 'preferred_dates',
              'declared_never_staff_mobility', 'declared_last_mobility_date', 'declared_centre_start_date',
              'centre_projects', 'declared_language_level', 'support_needs', 'image_consent',
              'applicant_notes', 'plan_reason', 'plan_objectives', 'plan_application'),
}
# Issue #697: the mobility and transfer plan of the staff call (annex 1), written in the form and
# required to submit: the activity, host entity or course, destination and dates (always a
# concrete one), why that choice, the objectives and the application to the job. Its
# dissemination is not asked for: it is the same obligation for everyone (a news item on the
# website, and sharing it at a meeting if needed). The panel reads it on screen.
PLAN_FIELDS = ('staff_activity', 'host_entity', 'destination', 'preferred_dates', 'plan_reason', 'plan_objectives',
               'plan_application')
STAFF_ACTIVITIES = [('job_shadowing', "Job shadowing"), ('course', "Structured course"),
                    ('teaching', "Teaching assignment")]


class EmsErasmusApplication(models.Model):
    """Issue #683 - a student's application to an Erasmus+ call; issue #686, also a staff
    member's to a staff call. Filed from the portal (controllers/portal_erasmus.py, with sudo),
    reviewed by the Erasmus team. The state only moves through the actions below. See
    docs/en/developers/erasmus/erasmus.md."""
    _name = 'ems.erasmus.application'
    _description = 'Erasmus+ application'
    _inherit = ['ems.base']
    _order = 'submit_date desc, id desc'
    _sql_constraints = [
        ('call_partner_unique', 'unique(call_id, partner_id)', "A person can only apply once to each call."),
    ]

    call_id = fields.Many2one(string="Call", comodel_name='ems.erasmus.call', required=True, ondelete='restrict',
                              index=True)
    partner_id = fields.Many2one(string="Applicant", comodel_name='res.partner', required=True, ondelete='restrict',
                                 index=True)
    audience = fields.Selection(string="Applicants", related='call_id.audience', store=True)
    employee_id = fields.Many2one(string="Employee", comodel_name='hr.employee', ondelete='restrict', readonly=True,
                                  help="Staff call: the applicant's employee file.")
    modality_id = fields.Many2one(string="Modality", comodel_name='ems.erasmus.call.modality', ondelete='restrict',
                                  domain="[('call_id', '=', call_id)]", tracking=True)
    state = fields.Selection(string="State", required=True, default='draft', tracking=True, copy=False, index=True,
                             selection=[
                                 ('draft', "Draft"), ('submitted', "Submitted"), ('subsanation', "Corrections requested"),
                                 ('admitted', "Admitted"), ('excluded', "Excluded"), ('not_submitted', "Not submitted"),
                                 ('selected', "Selected"), ('reserve', "Reserve"), ('not_selected', "Not selected"),
                                 ('accepted', "Place accepted"), ('renounced', "Renounced"),
                             ])
    submit_date = fields.Datetime(string="Submitted on", readonly=True, copy=False)
    is_minor = fields.Boolean(string="Minor", compute='_compute_is_minor')

    previous_mobility = fields.Boolean(string="Previous Erasmus+ mobility")
    previous_mobility_details = fields.Text(string="Previous mobility details")
    availability = fields.Text(string="Availability")
    # Audit D-4: what the applicant declares is the team's, as the accredited check (the Head of Studies reads
    # the conduct warnings and the exclusion reason, not this).
    fewer_opportunities = fields.Boolean(string="Declares fewer opportunities",
                                         groups=TEAM)
    image_consent = fields.Boolean(string="Image consent")
    applicant_notes = fields.Text(string="Applicant's notes")
    # Issue #686: the staff application form (art. 8 and annex 1 of the staff call).
    staff_activity = fields.Selection(string="Activity", selection=STAFF_ACTIVITIES)
    host_entity = fields.Char(string="Host entity or course")
    destination = fields.Char(string="Destination")
    preferred_dates = fields.Char(string="Preferred dates")
    centre_projects = fields.Text(string="Centre projects")
    plan_reason = fields.Text(string="Why this entity or course",
                              help="Annex 1, section 3: why this entity or course, and its relation with the "
                                   "applicant's job and with the centre's training cycles.")
    plan_objectives = fields.Text(string="Objectives",
                                  help="Annex 1, section 4: two or three concrete objectives: what to observe, learn "
                                       "or, in a teaching assignment, teach.")
    plan_application = fields.Text(string="Application to the job",
                                   help="Annex 1, section 5: how it will be used in the classes, the department or "
                                        "the centre's management, and which students will benefit.")
    support_needs = fields.Text(string="Support needs", groups=TEAM)
    declared_never_staff_mobility = fields.Boolean(
        string="Never had a staff mobility",
        help="The applicant has never done an Erasmus+ staff mobility from this centre.")
    declared_last_mobility_date = fields.Date(
        string="Last staff mobility on",
        help="Month and year of the applicant's last Erasmus+ staff mobility from this centre. Accompanying students, "
             "other programmes and mobilities from other centres do not count.")
    declared_centre_start_date = fields.Date(
        string="At the centre since", help="Month and year since when the applicant works at the centre without "
                                           "interruption.")
    declared_last_staff_mobility = fields.Selection(
        string="Declared last staff mobility", selection=LAST_MOBILITY_BANDS, compute='_compute_declared_staff_bands',
        store=True, help="Criterion 2, from what the applicant declared and the call's course.")
    declared_seniority = fields.Selection(
        string="Declared seniority", selection=SENIORITY_BANDS, compute='_compute_declared_staff_bands', store=True,
        help="Criterion 5, from the date the applicant declared, at the call's closing date.")
    declared_language_level = fields.Selection(string="Declared language certificate", selection=[
        ('none', "None"), ('b2', "B2"), ('c1', "C1"), ('c2', "C2")],
        help="The highest certificate the staff applicant declares (B2 or higher). It scores criterion 4 unless the "
             "Erasmus team records another level after checking the certificate.")

    document_ids = fields.One2many(string="Documents", comodel_name='ems.erasmus.application.document',
                                   inverse_name='application_id', domain=[('stage', '=', 'application')])
    mobility_ids = fields.One2many(string="Mobility", comodel_name='ems.erasmus.mobility',
                                   inverse_name='application_id')

    requirements_check = fields.Selection(string="Requirements", selection=CHECK_STATES, default='pending',
                                          required=True, tracking=True, copy=False)
    requirements_check_note = fields.Text(string="Requirements note", copy=False)
    requirements_check_user_id = fields.Many2one(string="Requirements checked by", comodel_name='res.users',
                                                 readonly=True, copy=False)
    requirements_check_date = fields.Datetime(string="Requirements checked on", readonly=True, copy=False)
    # Students' call art. 6: conduct is read from EMS's own conduct warnings, never checked by hand.
    course_strike_count = fields.Integer(string="Conduct warnings this course", compute='_compute_conduct',
                                         help="The applicant's conduct warnings in EMS during the call's course.")
    conduct_blocked = fields.Boolean(string="Too many conduct warnings", compute='_compute_conduct',
                                     help="As many conduct warnings this course as the number that sends the case "
                                          "to the coexistence team, or more: the student cannot apply.")
    can_manage = fields.Boolean(string="Can manage", compute='_compute_permissions',
                                help="Erasmus team or administrator.")
    exclusion_reason = fields.Text(string="Exclusion reason", tracking=True, copy=False)

    # --- scoring (issue #684, art. 12 of the call) ---
    scoring_frozen_date = fields.Datetime(string="Scoring data frozen on", readonly=True, copy=False,
                                          help="When the call was closed: the record average and the conduct "
                                               "warnings are the ones EMS had then.")
    grade_line_ids = fields.One2many(string="Modules used for the average", comodel_name='ems.erasmus.application.grade',
                                     inverse_name='application_id', readonly=True)
    grade_average_ems = fields.Float(string="Average from EMS", digits=(4, 2), readonly=True, copy=False)
    grade_average_from_ems = fields.Boolean(string="Average from EMS found", readonly=True, copy=False)
    grade_average = fields.Float(string="Record average", digits=(4, 2), compute='_compute_scores', store=True)
    language_level = fields.Selection(string="Language certificate", tracking=True, copy=False, selection=[
        ('none', "None"), ('b1', "B1"), ('b2', "B2"), ('c1', "C1"), ('c2', "C2")],
        help="The highest official foreign-language certificate the applicant uploaded.")
    language_level_user_id = fields.Many2one(string="Language checked by", comodel_name='res.users',
                                             readonly=True, copy=False)
    language_level_date = fields.Datetime(string="Language checked on", readonly=True, copy=False)
    fewer_opportunities_check = fields.Selection(
        string="Fewer opportunities accredited", selection=YES_NO, tracking=True, copy=False,
        groups=TEAM)
    fewer_opportunities_check_user_id = fields.Many2one(
        string="Fewer opportunities checked by", comodel_name='res.users', readonly=True, copy=False,
        groups=TEAM)
    fewer_opportunities_check_date = fields.Datetime(
        string="Fewer opportunities checked on", readonly=True, copy=False,
        groups=TEAM)
    first_mobility = fields.Selection(string="First mobility", selection=YES_NO, tracking=True, copy=False,
                                      help="GM: no previous Erasmus+ mobility. GS: no previous higher-education one.")
    first_mobility_user_id = fields.Many2one(string="First mobility checked by", comodel_name='res.users',
                                             readonly=True, copy=False)
    first_mobility_date = fields.Datetime(string="First mobility checked on", readonly=True, copy=False)
    strike_ids = fields.Many2many(string="Conduct warnings", comodel_name='ems.strike',
                                  relation='ems_erasmus_application_strike_rel', readonly=True, copy=False)
    strike_count = fields.Integer(string="Number of conduct warnings", readonly=True, copy=False)

    interview_ids = fields.One2many(string="Interviews", comodel_name='ems.erasmus.interview',
                                    inverse_name='application_id', groups=TEAM)
    interview_date = fields.Datetime(string="Interview date", tracking=True, copy=False)
    interview_place = fields.Char(string="Interview place", tracking=True, copy=False)
    interview_call_date = fields.Datetime(string="Interview call sent on", readonly=True, copy=False)
    single_interview_reason = fields.Text(string="Reason for a single evaluation", tracking=True, copy=False,
                                          help="Only one evaluator could score the interview (annex 4).")
    interview_general = fields.Float(string="Interview, general part", digits=(4, 2),
                                     compute='_compute_interview', store=True)
    interview_english = fields.Float(string="Interview, English part", digits=(4, 2),
                                     compute='_compute_interview', store=True)
    interview_complete = fields.Boolean(string="Interview scored", compute='_compute_interview', store=True)

    # Audit D-14: the Head of Studies sees the total and the rank only, so criterion D (fewer opportunities)
    # cannot be worked out from the others.
    score_a = fields.Float(string="A. Record", digits=(5, 2), compute='_compute_scores', store=True,
                           groups=TEAM)
    score_a_pending = fields.Boolean(string="Record average pending", compute='_compute_scores', store=True)
    score_b = fields.Float(string="B. Interview", digits=(5, 2), compute='_compute_scores', store=True,
                           groups=TEAM)
    score_c = fields.Float(string="C. Languages", digits=(5, 2), compute='_compute_scores', store=True,
                           groups=TEAM)
    score_d = fields.Float(string="D. Fewer opportunities", digits=(5, 2), compute='_compute_scores', store=True,
                           groups=TEAM)
    score_e = fields.Float(string="E. First mobility", digits=(5, 2), compute='_compute_scores', store=True,
                           groups=TEAM)
    score_f = fields.Float(string="F. Conduct", digits=(5, 2), compute='_compute_scores', store=True,
                           groups=TEAM)
    score_total = fields.Float(string="Total score", digits=(5, 2), compute='_compute_scores', store=True)
    score_complete = fields.Boolean(string="Score complete", compute='_compute_scores', store=True,
                                    help="Every criterion is in: a pending one never counts as zero.")
    is_eligible = fields.Boolean(string="Eligible", compute='_compute_scores', store=True,
                                 help="Complete score, at least the call's minimum.")
    draw_order = fields.Integer(string="Draw", tracking=True, copy=False, readonly=True,
                                help="Result of the draw between applications tied after every tie-break "
                                     "(lower goes first), run by the Erasmus coordinator from the call (audit D-13).")
    rank = fields.Integer(string="Rank", compute='_compute_rank', store=True,
                          help="Position in the modality among the admitted applications. 0 until every one "
                               "of them has a complete score.")
    needs_draw = fields.Boolean(string="Needs a draw", compute='_compute_rank', store=True)

    # --- resolutions, claims and offers (issue #685) ---
    resolution_line_ids = fields.One2many(string="Resolutions", comodel_name='ems.erasmus.resolution.line',
                                          inverse_name='application_id', readonly=True)
    offer_ids = fields.One2many(string="Place offers", comodel_name='ems.erasmus.offer',
                                inverse_name='application_id', readonly=True)
    claim_ids = fields.One2many(string="Claims", comodel_name='ems.erasmus.claim', inverse_name='application_id')

    # --- staff scoring (issue #686, art. 11 of the staff call) ---
    plan_rating_ids = fields.One2many(string="Mobility plan ratings", comodel_name='ems.erasmus.plan_rating',
                                      inverse_name='application_id',
                                      groups=TEAM)
    plan_score = fields.Float(string="Mobility plan score", digits=(4, 2), compute='_compute_plan', store=True,
                              help="Mean of the panel's ratings.")
    plan_complete = fields.Boolean(string="Mobility plan rated", compute='_compute_plan', store=True,
                                   help="Every panel member who does not abstain has submitted their rating.")
    last_staff_mobility = fields.Selection(string="Last staff mobility", tracking=True, copy=False,
                                           selection=LAST_MOBILITY_BANDS,
                                           help="Only when what the applicant declared is wrong: this counts instead.")
    last_staff_mobility_user_id = fields.Many2one(string="Last mobility checked by", comodel_name='res.users',
                                                  readonly=True, copy=False)
    last_staff_mobility_date = fields.Datetime(string="Last mobility checked on", readonly=True, copy=False)
    seniority = fields.Selection(string="Seniority at the centre", tracking=True, copy=False, selection=SENIORITY_BANDS,
                                 help="Only when what the applicant declared is wrong: this counts instead.")
    seniority_user_id = fields.Many2one(string="Seniority checked by", comodel_name='res.users', readonly=True,
                                        copy=False)
    seniority_date = fields.Datetime(string="Seniority checked on", readonly=True, copy=False)
    merit_ids = fields.One2many(string="Merits", comodel_name='ems.erasmus.application.merit',
                                inverse_name='application_id')
    merits_checked = fields.Boolean(string="Merits reviewed", tracking=True, copy=False,
                                    help="Every merit of criteria 3 and 6 is recorded (having none is an answer too).")
    merits_checked_user_id = fields.Many2one(string="Merits reviewed by", comodel_name='res.users', readonly=True,
                                             copy=False)
    merits_checked_date = fields.Datetime(string="Merits reviewed on", readonly=True, copy=False)
    score_plan = fields.Float(string="1. Mobility plan", digits=(4, 2), compute='_compute_scores', store=True)
    score_last_mobility = fields.Float(string="2. Last mobility", digits=(4, 2), compute='_compute_scores',
                                       store=True)
    score_projects = fields.Float(string="3. Centre projects", digits=(4, 2), compute='_compute_scores', store=True)
    score_staff_language = fields.Float(string="4. Languages", digits=(4, 2), compute='_compute_scores', store=True)
    score_seniority = fields.Float(string="5. Seniority", digits=(4, 2), compute='_compute_scores', store=True)
    score_internationalisation = fields.Float(string="6. Internationalisation", digits=(4, 2),
                                              compute='_compute_scores', store=True)

    @api.depends('partner_id.birth_date', 'audience')
    def _compute_is_minor(self):
        for application in self:
            application.is_minor = application.audience == 'student' and not application.partner_id.is_adult

    @api.depends_context('uid')
    def _compute_permissions(self):
        can_manage = self._ems_can_manage()
        for application in self:
            application.can_manage = can_manage

    def _compute_conduct(self):
        for application in self:
            count = application.call_id._ems_course_strike_count(application.partner_id) \
                if application.audience == 'student' else 0
            application.course_strike_count = count
            application.conduct_blocked = application.call_id._ems_conduct_blocked_count(count)

    @api.depends('interview_ids.state', 'interview_ids.general_score', 'interview_ids.english_score',
                 'single_interview_reason')
    def _compute_interview(self):
        """Mean of the submitted interviews; complete with two of them, or one and a reason."""
        for application in self:
            interviews = application.interview_ids
            submitted = interviews.filtered(lambda interview: interview.state == 'submitted')
            count = len(submitted)
            application.interview_complete = bool(submitted) and count == len(interviews) and (
                count >= 2 or bool(application.single_interview_reason))
            application.interview_general = sum(submitted.mapped('general_score')) / count if count else 0.0
            application.interview_english = sum(submitted.mapped('english_score')) / count if count else 0.0

    @api.depends('plan_rating_ids.state', 'plan_rating_ids.score', 'plan_rating_ids.panel_member_id',
                 'plan_rating_ids.abstention_reason',
                 'call_id.panel_ids.user_id')
    def _compute_plan(self):
        """Issue #686: the mean of the panel's ratings, complete when every panel member has a
        submitted one (a pending rating blocks, it never counts as zero). Abstentions do not count."""
        for application in self:
            ratings = application.plan_rating_ids
            counted = ratings.filtered(lambda rating: not rating.abstention_reason)
            submitted = counted.filtered(lambda rating: rating.state == 'submitted')
            application.plan_complete = bool(counted) and submitted == counted and not (
                application.call_id.panel_ids.user_id - ratings.panel_member_id)
            application.plan_score = round(sum(submitted.mapped('score')) / len(submitted), 2) if submitted else 0.0

    @api.depends('grade_average_ems', 'grade_average_from_ems', 'scoring_frozen_date',
                 'interview_general', 'interview_english', 'interview_complete', 'language_level',
                 'fewer_opportunities_check', 'first_mobility', 'strike_count', 'call_id.min_score', 'audience',
                 'plan_score', 'plan_complete', 'last_staff_mobility', 'seniority', 'merits_checked',
                 'declared_language_level', 'declared_last_staff_mobility', 'declared_seniority',
                 'merit_ids.kind')
    def _compute_scores(self):
        """Art. 12: A + B + C + D + E + F, no floor at zero. A pending criterion leaves it incomplete.
        A staff application, criteria 1 to 6 of the staff call instead (`_ems_staff_scores`)."""
        for application in self:
            application.update(dict.fromkeys(SCORE_FIELDS + STAFF_SCORE_FIELDS, 0.0))
            application.update({'grade_average': 0.0, 'score_a_pending': False})
            if application.audience == 'staff':
                application._ems_staff_scores()
                continue
            average = application.grade_average_ems
            application.grade_average = average
            application.score_a_pending = not (application.scoring_frozen_date and application.grade_average_from_ems)
            application.score_a = average * 4
            application.score_b = application.interview_general + application.interview_english
            application.score_c = LANGUAGE_SCORES.get(application.language_level, 0.0)
            application.score_d = 10.0 if application.fewer_opportunities_check == 'yes' else 0.0
            application.score_e = 5.0 if application.first_mobility == 'yes' else 0.0
            application.score_f = -min(3 * application.strike_count, 9)
            application.score_total = sum(application[f'score_{criterion}'] for criterion in 'abcdef')
            application.score_complete = not application.score_a_pending and application.interview_complete and all(
                application[name] for name in ('language_level', 'fewer_opportunities_check', 'first_mobility'))
            application.is_eligible = application.score_complete and \
                application.score_total >= application.call_id.min_score

    def _ems_staff_scores(self):
        """Art. 11 of the staff call: 1 + 2 + 3 + 4 + 5 + 6, max 10. Criteria 3 and 6 add up the
        merits, up to their maximums."""
        merits = self.merit_ids
        self.update({
            'score_plan': self.plan_score,
            'score_last_mobility': LAST_MOBILITY_SCORES.get(self._ems_staff_last_mobility(), 0.0),
            'score_projects': min(sum(merits.filtered(lambda merit: merit.kind in PROJECT_MERITS).mapped('points')),
                                  1.5),
            'score_staff_language': STAFF_LANGUAGE_SCORES.get(self._ems_staff_language_level(), 0.0),
            'score_seniority': SENIORITY_SCORES.get(self._ems_staff_seniority(), 0.0),
            'score_internationalisation': min(
                sum(merits.filtered(lambda merit: merit.kind == 'internationalisation').mapped('points')), 1.0),
        })
        self.score_total = sum(self[name] for name in STAFF_SCORE_FIELDS)
        self.score_complete = self.plan_complete and self.merits_checked and bool(
            self._ems_staff_last_mobility() and self._ems_staff_seniority())
        self.is_eligible = self.score_complete and self.score_total >= self.call_id.min_score

    @api.depends('declared_never_staff_mobility', 'declared_last_mobility_date', 'declared_centre_start_date',
                 'call_id.course_id.start', 'call_id.date_close')
    def _compute_declared_staff_bands(self):
        """Criteria 2 and 5 from the dates the applicant declared. A mobility belongs to the course
        starting on 1 September; seniority is counted in whole months up to the call's closing date."""
        utils = self.env['ems.datetime_utils']
        for application in self:
            mobility = application.declared_last_mobility_date
            band = 'never' if application.declared_never_staff_mobility else False
            if mobility and not band:
                course = (application.call_id.course_id or self.env.company.current_course_id).start
                ago = course - (mobility.year if mobility.month >= 9 else mobility.year - 1)
                band = 'recent' if ago <= 1 else 'two_courses' if ago == 2 else 'older'
            application.declared_last_staff_mobility = band
            start, close = application.declared_centre_start_date, application.call_id.date_close
            seniority = False
            if start and close:
                close = utils.utc_datetime_to_local(close.replace(tzinfo=UTC))
                months = (close.year - start.year) * 12 + close.month - start.month
                seniority = 'y0' if months < 12 else 'y1' if months < 24 else 'y2' if months < 60 else 'y5'
            application.declared_seniority = seniority

    def _ems_staff_last_mobility(self):
        """Criterion 2: the Erasmus team's correction, else what the applicant declared."""
        return self.last_staff_mobility or self.declared_last_staff_mobility

    def _ems_staff_seniority(self):
        """Criterion 5: the Erasmus team's correction, else what the applicant declared."""
        return self.seniority or self.declared_seniority

    def _ems_staff_language_level(self):
        """Criterion 4: the level the Erasmus team recorded after checking the certificate, else
        the one the applicant declared (none if they declared nothing)."""
        return self.language_level or self.declared_language_level or 'none'

    @api.depends('state', 'modality_id', 'score_total', 'score_complete', 'score_d', 'score_e',
                 'interview_english', 'grade_average', 'draw_order', 'score_plan', 'score_seniority',
                 'declared_centre_start_date',
                 'call_id.application_ids.state', 'call_id.application_ids.modality_id',
                 'call_id.application_ids.score_total', 'call_id.application_ids.score_complete',
                 'call_id.application_ids.score_d', 'call_id.application_ids.score_e',
                 'call_id.application_ids.interview_english', 'call_id.application_ids.grade_average',
                 'call_id.application_ids.draw_order', 'call_id.application_ids.score_plan',
                 'call_id.application_ids.score_seniority', 'call_id.application_ids.declared_centre_start_date')
    def _compute_rank(self):
        """Rank among the admitted applications (and their results) of the same modality, by total and art. 12's
        tie-breaks, then the draw. Only once every one of them has a complete score. A staff call ranks
        everyone in one list (issue #686). A tied set needs a draw until each of its applications has
        its own drawn position: also when someone joins a set already drawn (a claim upheld), who would
        otherwise go first with no draw at all."""
        self.rank = 0
        self.needs_draw = False
        for (call, modality), applications in self.grouped(lambda application: (
                application.call_id, application.audience == 'student' and application.modality_id)).items():
            ranked = call.application_ids.filtered(
                lambda application: application.state in RANKED_STATES and (
                    call.audience == 'staff' or application.modality_id == modality))
            if not ranked or not all(ranked.mapped('score_complete')):
                continue
            keys = {application: application._ems_rank_key() for application in ranked}
            ordered = sorted(keys.values())
            tied = ranked.grouped(lambda application: keys[application][:-1])
            for application in applications & ranked:
                application.rank = ordered.index(keys[application]) + 1
                draws = tied[keys[application][:-1]].mapped('draw_order')
                application.needs_draw = len(draws) > 1 and (0 in draws or len(set(draws)) < len(draws))

    def _ems_rank_key(self):
        """Total, then the call's tie-breaks (students: art. 12; staff, art. 11: mobility plan, then
        more seniority at the centre, by the month and year declared in the form, not by the band of
        criterion 5), then the draw."""
        self.ensure_one()
        if self.audience == 'staff':
            start = self.declared_centre_start_date
            return (-self.score_total, -self.score_plan, -self.score_seniority,
                    start.year * 12 + start.month if start else float('inf'), self.draw_order)
        return (-self.score_total, -self.score_d, -self.score_e, -self.interview_english, -self.grade_average,
                self.draw_order)

    def _compute_display_name(self):
        for application in self:
            application.display_name = f"{application.partner_id.name} - {application.call_id.name}"

    @api.model_create_multi
    def create(self, vals_list):
        """One document line per document the call asks for."""
        check_workflow_create(self, vals_list)
        Call = self.env['ems.erasmus.call']
        for vals in vals_list:
            if vals.get('call_id') and 'document_ids' not in vals:
                vals['document_ids'] = [(0, 0, {'call_document_id': document.id})
                                        for document in Call.browse(vals['call_id']).document_ids]
        return super().create(vals_list)

    def write(self, vals):
        """The state, the frozen scoring data and who checked what only change through the actions
        (ems.erasmus.workflow, audit R-25)."""
        check_workflow_write(self, vals)
        if not self.env.su and not self._ems_can_manage():
            raise AccessError(_("Only the Erasmus team changes an application."))
        now = fields.Datetime.now()
        for name in STAMPED_FIELDS:
            if name in vals:
                vals.update({f'{name}_user_id': self.env.uid, f'{name}_date': now})
        result = super().write(vals)
        if 'modality_id' in vals:
            # Issue #687: a staff member's modality, assigned after selection, brings its documents.
            self.mobility_ids.filtered(lambda mobility: mobility.state in ('choosing', 'preparing'))._ems_sync_requirements()
        return result

    def unlink(self):
        """An application whose documents are evidence is kept (its lines would go in cascade)."""
        check_kept(self, self.filtered(lambda application: application.document_ids._ems_evidence()))
        return super().unlink()

    # --- team actions ----------------------------------------------------------------------

    def action_request_subsanation(self):
        """Ask the applicant to correct or complete the documents marked as needing changes or
        missing, and email them the list and the deadline."""
        for application in self:
            application._ems_check_state(('submitted',))
            to_correct = application._ems_documents_to_correct()
            if not to_correct:
                raise UserError(_("Mark which documents need changes before asking for corrections."))
            to_correct.sudo().correction_requested = True
        self._ems_activities_done()
        self._ems_set_state('subsanation')
        self._ems_send('ems.email_template_erasmus_application_subsanation')

    def action_admit(self):
        for application in self:
            application._ems_check_state(('submitted',))
            if application.requirements_check != 'met':
                raise UserError(_("Every admission check must be met to admit %s.", application.partner_id.name))
            if application.conduct_blocked:
                raise UserError(_("%s has too many conduct warnings this course to take part (art. 6 of the call): "
                                  "exclude the application.", application.partner_id.name))
            if application.document_ids.filtered(lambda line: line.is_required and line.review_state != 'valid'):
                raise UserError(_("Every required document of %s must be valid to admit the application.",
                                  application.partner_id.name))
        self._ems_activities_done()
        self._ems_set_state('admitted')

    def action_exclude(self):
        """Also on an admitted application: not attending the interview excludes (art. 11)."""
        for application in self:
            application._ems_check_state(('submitted', 'subsanation', 'admitted'))
            if not (application.exclusion_reason or '').strip():
                raise UserError(_("Write the exclusion reason first."))
        self._ems_activities_done()
        self._ems_set_state('excluded')

    def action_back_to_review(self):
        for application in self:
            application._ems_check_state(('admitted', 'excluded'))
        self._ems_set_state('submitted')

    def action_send_interview_call(self):
        """Email the applicant the interview's date and place, at least 24 hours ahead (art. 11)."""
        limit = self.call_id._ems_now() + timedelta(hours=24)
        for application in self:
            application._ems_check_state(('admitted',))
            if application.audience != 'student':
                raise UserError(_("Only the students' call has interviews."))
            if not application.interview_date:
                raise UserError(_("Set the interview date of %s first.", application.partner_id.name))
            if application.interview_date < limit:
                raise UserError(_("The interview call must be sent at least 24 hours before the interview."))
        self._ems_send('ems.email_template_erasmus_interview_call')
        self.sudo().write({'interview_call_date': fields.Datetime.now()})

    def _ems_ranking_result(self):
        """Issue #685: selected within the modality's places, reserve after them, not selected
        below the minimum score. A staff call, within the places of all its modalities."""
        self.ensure_one()
        if not self.is_eligible:
            return 'not_selected'
        places = sum(self.call_id.modality_ids.mapped('places')) if self.audience == 'staff' \
            else self.modality_id.places
        return 'selected' if self.rank <= places else 'reserve'

    def action_export_participants(self):
        """Issue #685: the spreadsheet of the people who accepted a place, served by
        EmsErasmusExportController (it carries personal data: Erasmus team only)."""
        accepted = self._ems_participants()
        return {
            'type': 'ir.actions.act_url',
            'url': f"/ems/erasmus/participants?application_ids={','.join(map(str, accepted.ids))}",
            'target': 'download',
        }

    def _ems_participants(self):
        """The applications in self whose applicant accepted a place, for the Erasmus team only."""
        if not (self.env.su or self.env.user.has_group('ems.group_erasmus')):
            raise AccessError(_("Only the Erasmus team exports the participants."))
        accepted = self.filtered(lambda application: application.state == 'accepted')
        if not accepted:
            raise UserError(_("Nobody has accepted a place yet."))
        return accepted

    def _ems_participants_xlsx(self):
        """The participants as an .xlsx: one row per application, PARTICIPANT_HEADERS' columns. Each
        download is logged (audit D-10)."""
        applications = self._ems_participants().sudo().sorted(lambda application: application.partner_id.name)
        content = self._ems_participants_workbook([application._ems_participant_row()
                                                   for application in applications])
        for call in applications.call_id:
            self.env['ems.erasmus.export']._ems_log_spreadsheet(
                call, len(applications.filtered(lambda application: application.call_id == call)))
        return content

    @api.model
    def _ems_participants_workbook(self, rows):
        """The participants' spreadsheet, one sheet with PARTICIPANT_HEADERS' columns: the format an
        external tool reads, shared by the calls and the group mobilities (issue #703); never change
        its columns."""
        stream = io.BytesIO()
        workbook = xlsxwriter.Workbook(stream, {'in_memory': True})
        sheet = workbook.add_worksheet(PARTICIPANT_SHEET)
        bold = workbook.add_format({'bold': True})
        date_format = workbook.add_format({'num_format': 'dd/mm/yyyy'})
        sheet.write_row(0, 0, PARTICIPANT_HEADERS, bold)
        for row, values in enumerate(rows, start=1):
            values = list(values)
            birth_date = values.pop(6)
            sheet.write_row(row, 0, values[:6])
            if birth_date:
                sheet.write_datetime(row, 6, birth_date, date_format)
            sheet.write_row(row, 7, values[6:])
        sheet.set_column(0, len(PARTICIPANT_HEADERS) - 1, 18)
        workbook.close()
        return stream.getvalue()

    def _ems_participant_row(self):
        """The values of PARTICIPANT_HEADERS for this applicant, the birth date as a datetime.
        The legal guardian columns, only for minors: every family contact, in the same order."""
        self.ensure_one()
        if self.audience == 'staff':
            return self._ems_staff_row(self.employee_id, self.partner_id)
        return self._ems_student_row(self.partner_id, self.is_minor)

    @api.model
    def _ems_student_row(self, partner, is_minor, bank=True):
        """A student's row, from their contact; `bank` False leaves the bank columns empty."""
        group = partner.main_group_id
        bank = partner.bank_ids[:1] if bank else self.env['res.partner.bank']
        family = partner._ems_family_contacts() if is_minor else self.env['res.partner']
        address = partner._display_address(without_company=True).replace('\n', ', ').strip(', ')
        birth_date = partner.birth_date and fields.Datetime.to_datetime(partner.birth_date)
        return [
            partner.firstname or '', partner.lastname or '', partner.document_id or partner.passport_id or '',
            partner.email or '', partner.phone or partner.mobile or '', address, birth_date,
            partner.citizenship_id.name or '', '', group.study_id.acronym or '', group.course or '',
            bank.acc_holder_name or (bank and partner.name) or '', bank.bank_id.name or '', bank.bank_id.bic or '',
            bank.sanitized_acc_number or '',
            ', '.join(family.mapped('name')), ', '.join(contact.email or '' for contact in family),
            ', '.join(contact.phone or contact.mobile or '' for contact in family),
        ]

    @api.model
    def _ems_staff_row(self, employee, partner, bank=True):
        """Issue #686: a staff member's row, from their employee file. The cycle, the year and the
        legal guardian columns stay empty, and so does the gender (decided 2026-10-22); `bank`
        False leaves the bank columns empty too."""
        bank = employee.bank_account_id if bank else self.env['res.partner.bank']
        address = ', '.join(filter(None, [employee.private_street, employee.private_street2, employee.private_zip,
                                          employee.private_city, employee.private_state_id.name,
                                          employee.private_country_id.name]))
        birth_date = employee.birthday and fields.Datetime.to_datetime(employee.birthday)
        return [
            partner.firstname or employee.name or '', partner.lastname or '',
            employee.identification_id or employee.passport_id or '',
            employee.private_email or employee.work_email or '', employee.private_phone or employee.mobile_phone or '',
            address, birth_date, employee.country_id.name or '', '', '', '',
            bank.acc_holder_name or (bank and employee.name) or '', bank.bank_id.name or '', bank.bank_id.bic or '',
            bank.sanitized_acc_number or '', '', '', '',
        ]

    def _ems_identity_document(self):
        """The applicant's identity document: a student's from their contact, a staff member's
        from their employee file (DNI/NIE, else passport)."""
        self.ensure_one()
        record = self.sudo().employee_id if self.audience == 'staff' else self.sudo().partner_id
        number = record.identification_id if self.audience == 'staff' else record.document_id
        return number or record.passport_id or ''

    def _ems_freeze_scoring_data(self):
        """Copy the record average (A) and the conduct warnings (F) as EMS has them now: what the
        selection is based on, never recomputed afterwards."""
        Grade = self.env['ems.erasmus.application.grade'].sudo()
        for application in self.sudo():
            grades = application._ems_grade_values()
            average, hours = self._ems_grade_average(grades)
            study = application.partner_id.main_group_id.study_id
            strikes = self.env['ems.strike'].sudo().search([
                ('student_id', '=', application.partner_id.id), ('group_id.study_id', '=', study.id),
                ('date', '<=', application.call_id.date_close)]) if study else self.env['ems.strike']
            application.grade_line_ids.unlink()
            Grade.create([{**vals, 'application_id': application.id} for vals in grades])
            application.write({
                'scoring_frozen_date': fields.Datetime.now(),
                'grade_average_ems': average,
                'grade_average_from_ems': bool(hours),
                'strike_ids': [(6, 0, strikes.ids)],
                'strike_count': len(strikes),
            })

    def _ems_grade_values(self):
        self.ensure_one()
        return self._ems_partner_grade_values(
            self.partner_id, self.call_id.course_id.name or self.env.company.current_course_id.name)

    @api.model
    def _ems_grade_average(self, grades):
        """The record average of `_ems_partner_grade_values`' modules, weighted by their hours,
        and those hours (0: nothing to average)."""
        hours = sum(vals['hours'] for vals in grades)
        return (round(sum(vals['grade'] * vals['hours'] for vals in grades) / hours, 2) if hours else 0.0), hours

    @api.model
    def _ems_partner_grade_values(self, partner, course_name):
        """The modules of `partner`'s current cycle for the record average, as values of
        ems.erasmus.application.grade: one per module, its most recent grade (this course's
        grade lines, then the year records from the latest course). Convalidated and recognised
        modules are left out, and so are modules with nothing evaluated. Issue #701: group
        mobilities rank with the same average."""
        study = partner.main_group_id.study_id
        if not study:
            return []
        found = {}  # module -> its values, None when it is left out
        lines = self.env['ems.grade_subject_line'].sudo().search([
            ('student_id', '=', partner.id), ('grade_session_id.subject_id.study_ids', 'in', study.ids)])
        for subject, subject_lines in lines.grouped(lambda line: line.grade_session_id.subject_id).items():
            last = max(subject_lines, key=lambda line: line.grade_session_id.round)
            if last.is_convalidated:
                found[('subject', subject.id)] = None
            elif last.computed_is_scored or last.internal_is_scored:
                grade = last.computed_score if last.computed_is_scored else last.internal_score
                found[('subject', subject.id)] = self._ems_grade_vals(subject, subject.display_name, course_name, grade)
        records = self.env['ems.student.year_record'].sudo().search([
            ('student_id', '=', partner.id), ('study_id', '=', study.id), ('is_provisional', '=', False)])
        for record in records.sorted(lambda record: record.course_id.start, reverse=True):
            for subject_record in record.subject_record_ids:
                key = ('subject', subject_record.subject_id.id) if subject_record.subject_id \
                    else ('name', subject_record.subject_name)
                if key in found:
                    continue
                if subject_record.is_convalidated or subject_record.is_recognized:
                    found[key] = None
                elif subject_record.has_final:
                    grade = subject_record.final_grade
                elif subject_record.is_overridden or subject_record.outcome_record_ids.filtered('final_is_scored'):
                    grade = subject_record.internal_grade
                else:
                    continue
                if key not in found:
                    found[key] = self._ems_grade_vals(subject_record.subject_id, subject_record.subject_name,
                                                      record.course_id.name, grade)
        return [vals for vals in found.values() if vals]

    @api.model
    def _ems_grade_vals(self, subject, subject_name, course_name, grade):
        return {'subject_id': subject.id, 'subject_name': subject_name, 'course_name': course_name,
                'grade': grade, 'hours': subject.total_hours}

    # --- portal ----------------------------------------------------------------------------

    @api.model
    def _ems_portal_get_or_create(self, call, partner):
        """`partner`'s application to `call`, created (as a draft) on the first visit while the
        call accepts applications."""
        application = self.search([('call_id', '=', call.id), ('partner_id', '=', partner.id)])
        if application:
            return application
        if call not in partner._ems_erasmus_calls():
            raise UserError(_("You cannot apply to this call."))
        if call._ems_conduct_blocked(partner):
            raise UserError(_("You cannot apply to this call: you have too many conduct warnings this course."))
        if not call.is_accepting:
            raise UserError(_("This call is not accepting applications."))
        if call.audience == 'staff':
            # Issue #686: one application per person, its modality assigned by the team after selection.
            return self.create({'call_id': call.id, 'partner_id': partner.id,
                                'employee_id': partner._ems_erasmus_employee().id})
        return self.create({'call_id': call.id, 'partner_id': partner.id,
                            'modality_id': call._ems_modality_for(partner).id})

    def _ems_portal_save(self, answers, uploads):
        """Save what the applicant sent from the portal. `answers`: values of ANSWER_FIELDS, only
        while the call accepts applications. `uploads`: {call document id: [(file name, bytes)]},
        also during subsanation, until its deadline, for the documents asked for."""
        self.ensure_one()
        answers = {key: value for key, value in answers.items() if key in ANSWER_FIELDS[self.audience]}
        if answers.get('staff_activity') not in (False, None, *dict(STAFF_ACTIVITIES)):
            raise UserError(_("Choose one of the activities of the call."))
        if answers.get('declared_language_level') not in (
                False, None, *dict(self._fields['declared_language_level'].selection)):
            raise UserError(_("Choose one of the language levels."))
        if answers:
            if not self._ems_portal_editable():
                raise UserError(_("The application can no longer be changed."))
            self.write(answers)
        lines = {line.call_document_id.id: line for line in self.document_ids}
        editable = self._ems_portal_editable()
        correctable = self._ems_portal_correctable()
        for document_id, files in uploads.items():
            line = lines.get(document_id)
            if not files or not line:
                continue
            if not (editable or line in correctable):
                raise UserError(_("The document %s can no longer be changed.", line.name))
            line._ems_add_files(files)

    def _ems_portal_editable(self):
        """The applicant can change answers and every document: before the closing date."""
        self.ensure_one()
        return self.state in ('draft', 'submitted') and self.call_id.is_accepting

    def _ems_subsanation_open(self):
        """Corrections requested and their deadline (if any) not passed yet."""
        self.ensure_one()
        deadline = self.call_id.subsanation_deadline
        return self.state == 'subsanation' and not (deadline and deadline <= self.call_id._ems_now())

    def _ems_portal_correctable(self):
        """The document lines the applicant can still upload to during subsanation: those the
        team asked to correct."""
        self.ensure_one()
        if not self._ems_subsanation_open():
            return self.env['ems.erasmus.application.document']
        return self.document_ids.filtered('correction_requested')

    def action_submit(self):
        """Submit (or submit again) the application: every required document needs a file. Emails
        the applicant a receipt with the files received. A correction the team was waiting for
        becomes a task for the Erasmus team to review it."""
        for application in self:
            if not (application._ems_portal_editable() or application._ems_subsanation_open()):
                raise UserError(_("The application can no longer be submitted."))
            if application.conduct_blocked:
                raise UserError(_("You cannot apply to this call: you have too many conduct warnings this course."))
            missing = application.document_ids.filtered(lambda line: line.is_required and not line.attachment_ids)
            if missing:
                raise UserError(_("Upload the required documents first: %s", ", ".join(missing.mapped('name'))))
            if application.audience == 'staff' and not (
                    (application.declared_never_staff_mobility or application.declared_last_mobility_date)
                    and application.declared_centre_start_date):
                raise UserError(_("Say when your last staff mobility was (or that you never had one) and since when "
                                  "you work at the centre."))
            if application.audience == 'staff' and not all(application[name] for name in PLAN_FIELDS):
                raise UserError(_("Fill in every section of the mobility plan: the activity, the host entity or "
                                  "course, the destination, the dates, why you chose them, the objectives and the "
                                  "application to your job."))
        corrected = self.filtered(lambda application: application.state == 'subsanation')
        self._ems_set_state('submitted')
        self.sudo().write({'submit_date': fields.Datetime.now()})
        self.document_ids.sudo().correction_requested = False
        self._ems_send('ems.email_template_erasmus_application_submitted')
        corrected._ems_ask_review()

    # --- helpers -----------------------------------------------------------------------------

    def _ems_documents_to_correct(self):
        self.ensure_one()
        return self.document_ids.filtered(
            lambda line: line.review_state == 'needs_change' or (line.is_required and not line.attachment_ids))

    def _ems_check_state(self, states):
        self.ensure_one()
        if self.state not in states:
            raise UserError(_("The application of %s is not in the right state for this action.",
                              self.partner_id.name))

    def _ems_set_state(self, state):
        self.sudo().write({'state': state})

    def _ems_ask_review(self):
        """A task for each member of the Erasmus team to review the corrected application; it is
        marked done when the team admits, excludes or asks for corrections again."""
        activity_type = self.env.ref('mail.mail_activity_data_todo')
        team = self.env['ems.erasmus.call']._ems_erasmus_team()
        for application in self:
            for user in team:
                application.sudo().activity_schedule(
                    activity_type_id=activity_type.id, user_id=user.id,
                    summary=_("Erasmus+: review the corrections of %s", application.partner_id.name))

    def _ems_activities_done(self):
        self.sudo().activity_ids.action_feedback()

    def _ems_can_manage(self):
        user = self.env.user
        return self.env.su or user.has_group('ems.group_erasmus') or user.has_group('ems.group_academic_admin')

    def _ems_send(self, xmlid):
        self._ems_mail(self, xmlid)

    @api.model
    def _ems_mail(self, records, xmlid):
        """Email `xmlid` (a template of `records`' model: applications, resolution lines, offers) to
        each applicant's own address; note it in the application's chatter when there is none."""
        template = self.env.ref(xmlid, raise_if_not_found=False)
        if not template:
            return
        for record in records:
            partner = record.partner_id
            if partner.email:
                template.with_context(lang=partner.lang).sudo().send_mail(
                    record.id, force_send=False, email_values={'email_to': partner.email})
            else:
                application = record if record._name == self._name else record.application_id
                application.sudo().chatter(_("No email sent: the applicant has no email address."))

    def _ems_mail_document_list(self, lines):
        """The files of `lines` as an HTML list, for the emails."""
        return self.env['ems.base'].build_html_list([
            Markup("{}: {}").format(line.name, ", ".join(line.attachment_ids.mapped('name')) or "-")
            if line.attachment_ids else line.name
            for line in lines
        ])


class EmsErasmusApplicationDocument(models.Model):
    """The files an applicant uploaded for one document of the call, with the team's review.
    Every upload is kept: a new file never replaces the earlier ones."""
    _name = 'ems.erasmus.application.document'
    _description = 'Erasmus+ application document'
    _order = 'application_id, file_category, sequence, id'

    application_id = fields.Many2one(string="Application", comodel_name='ems.erasmus.application', required=True,
                                     ondelete='cascade', index=True)
    call_document_id = fields.Many2one(string="Call document", comodel_name='ems.erasmus.call.document',
                                       required=True, ondelete='restrict')
    # Issue #687: the documents of a mobility (before leaving, on return) are lines of its application too.
    mobility_id = fields.Many2one(string="Mobility", comodel_name='ems.erasmus.mobility', ondelete='cascade',
                                  index=True)
    stage = fields.Selection(string="When", related='call_document_id.stage', store=True)
    signers = fields.Char(string="Signed by", related='call_document_id.signers')
    handled_by = fields.Selection(string="Handled by", related='call_document_id.handled_by')
    prepared_attachment_ids = fields.Many2many(
        string="Files from the team", comodel_name='ir.attachment',
        relation='ems_erasmus_application_document_prepared_rel',
        help="What the Erasmus team uploads for the participant: the document to sign, or the one it provides (e.g. "
             "the insurance policy).")
    deadline = fields.Date(string="Deadline", compute='_compute_deadline')
    open_date = fields.Date(string="Opens on", compute='_compute_open_date',
                            help="Before this day the participant does not see the document on the portal.")
    description = fields.Text(string="Instructions", related='call_document_id.description')
    name = fields.Char(string="Document", related='call_document_id.name')
    sequence = fields.Integer(string="Sequence", related='call_document_id.sequence', store=True)
    confidential = fields.Boolean(string="Confidential", related='call_document_id.confidential', store=True)
    is_required = fields.Boolean(string="Required", compute='_compute_is_required')
    attachment_ids = fields.Many2many(string="Files", comodel_name='ir.attachment',
                                      relation='ems_erasmus_application_document_attachment_rel')
    review_state = fields.Selection(string="Review", required=True, default='pending', selection=[
        ('pending', "Pending review"), ('valid', "Valid"), ('needs_change', "Needs changes")])
    review_comment = fields.Char(string="Comment for the applicant")
    correction_requested = fields.Boolean(string="Correction requested", readonly=True, copy=False,
                                          help="Asked to the applicant in the current corrections request.")
    file_category = fields.Selection(string="Category", selection=PARTICIPANT_CATEGORIES,
                                     compute='_compute_file_category', store=True,
                                     help="Where it goes in the participant's record.")
    file_state = fields.Selection(string="Status", compute='_compute_file_state', selection=[
        ('missing', "Missing"), ('to_review', "Pending review"), ('needs_change', "Needs changes"),
        ('complete', "Complete"), ('optional', "Optional"), ('not_applicable', "Not applicable")],
        help="Complete: valid after the team's review (a signed document is only complete once checked, not when "
             "uploaded); one the team provides, once it is uploaded.")

    @api.depends('call_document_id.requirement', 'application_id.is_minor', 'mobility_id.placement_type',
                 'mobility_id.is_short_blended')
    def _compute_is_required(self):
        for line in self:
            requirement = line.call_document_id.requirement
            line.is_required = requirement == 'required' or (requirement == 'minor' and line.application_id.is_minor) \
                or (requirement == 'curricular' and line.mobility_id.placement_type == 'curricular') \
                or (requirement == 'short_blended' and line.mobility_id.is_short_blended)

    @api.depends('call_document_id.file_category', 'call_document_id.stage')
    def _compute_file_category(self):
        for line in self:
            document = line.call_document_id
            line.file_category = document.file_category or STAGE_CATEGORIES.get(document.stage)

    @api.depends('is_required', 'handled_by', 'signers', 'review_state', 'attachment_ids', 'prepared_attachment_ids')
    def _compute_file_state(self):
        """A document is complete once the team checked it (valid). The only exception: one the team
        provides that nobody signs (e.g. the insurance policy), complete once uploaded. A document
        someone has to sign is never complete only because a file is there, whoever uploaded it."""
        for line in self:
            checked = line.handled_by != 'team' or bool(line.signers)
            if line.handled_by == 'team':
                uploaded = bool(line.prepared_attachment_ids or line.attachment_ids)
            else:
                uploaded = bool(line.attachment_ids)
            if uploaded and (line.review_state == 'valid' or not checked):
                line.file_state = 'complete'
            elif line.review_state == 'needs_change' and checked:
                line.file_state = 'needs_change'
            elif uploaded:
                line.file_state = 'to_review'
            elif line.is_required:
                line.file_state = 'missing'
            else:
                line.file_state = 'optional' if line.call_document_id.requirement == 'optional' else 'not_applicable'

    @api.depends('call_document_id.due_basis', 'call_document_id.due_days', 'mobility_id.destination_date',
                 'mobility_id.date_start', 'mobility_id.date_end')
    def _compute_deadline(self):
        """Issue #687: a mobility document's deadline, from its call document's rule."""
        for line in self:
            document, mobility = line.call_document_id, line.mobility_id
            basis = {'destination': mobility.destination_date, 'before_start': mobility.date_start,
                     'after_end': mobility.date_end}.get(document.due_basis)
            sign = -1 if document.due_basis == 'before_start' else 1
            line.deadline = basis and basis + timedelta(days=sign * document.due_days)

    @api.depends('call_document_id.open_days', 'mobility_id.date_start')
    def _compute_open_date(self):
        for line in self:
            start, days = line.mobility_id.date_start, line.call_document_id.open_days
            line.open_date = days and start and start - timedelta(days=days)

    def _ems_file_state_label(self):
        self.ensure_one()
        return dict(self._fields['file_state']._description_selection(self.env)).get(self.file_state, '')

    def _ems_is_open(self):
        """A mobility document that opens some days before leaving: only once the dates are known
        and that day has come."""
        self.ensure_one()
        return not self.call_document_id.open_days or bool(
            self.open_date and self.open_date <= self.env['ems.datetime_utils'].get_local_today())

    def write(self, vals):
        """A record keeps its history: a file is never removed from a valid document nor from a closed
        mobility (a new version is uploaded instead), and every change of review in a mobility is
        written in its chatter, with who made it."""
        files = [name for name in ('attachment_ids', 'prepared_attachment_ids') if name in vals]
        kept = {(line, name): line[name] for line in self for name in files
                if line.review_state == 'valid' or line._ems_record_closed()}
        old_states = {line: line.review_state for line in self} if 'review_state' in vals else {}
        result = super().write(vals)
        for (line, name), attachments in kept.items():
            if attachments - line[name]:
                raise UserError(_("%s is valid or its mobility is closed: its files are kept. Upload a new version "
                                  "instead of removing one.", line.name))
        labels = dict(self._fields['review_state']._description_selection(self.env))
        for line, old_state in old_states.items():
            owner = line._ems_record_owner()
            if owner and line.review_state != old_state:
                owner.sudo().chatter(_("%(document)s: %(state)s.", document=line._ems_record_label(),
                                       state=labels[line.review_state]))
        return result

    def unlink(self):
        check_kept(self, self._ems_evidence())
        return super().unlink()

    def _ems_evidence(self):
        """The lines that are evidence of the record (audit R-01): with a file, or valid."""
        return self.filtered(lambda line: line.attachment_ids or line.prepared_attachment_ids
                             or line.review_state == 'valid')

    def _ems_kept_attachments(self):
        """The files kept as they are (see write()): those of a valid line or of a closed record."""
        lines = self.filtered(lambda line: line.review_state == 'valid' or line._ems_record_closed())
        return lines.attachment_ids | lines.prepared_attachment_ids

    def _ems_record_closed(self):
        """Whether the record this document belongs to is closed: its files are kept as they are."""
        return self.mobility_id.state in ('done', 'cancelled')

    def _ems_record_owner(self):
        """The record whose chatter keeps the history of this document's review."""
        return self.mobility_id

    def _ems_record_label(self):
        return self.name

    def _ems_check_reviewer(self):
        """Who reviews these documents (marks them valid, ticks their signatures, removes a file): the
        Erasmus team."""
        if not self.env['ems.erasmus.application']._ems_can_manage():
            raise AccessError(_("Only the Erasmus team reviews these documents."))

    def _ems_is_minor(self):
        self.ensure_one()
        return self.application_id.is_minor

    def action_mark_valid(self):
        self.write({'review_state': 'valid'})

    def action_mark_needs_change(self):
        self.write({'review_state': 'needs_change'})

    def _ems_add_files(self, files):
        """Attach `files` ([(name, bytes)]) to this line and put it back to review."""
        self.ensure_one()
        attachments = self.env['ir.attachment'].sudo().create([{
            'name': check_upload(name),
            'datas': base64.b64encode(content),
            'res_model': self._name,
            'res_id': self.id,
        } for name, content in files])
        self.sudo().write({'attachment_ids': [(4, attachment.id) for attachment in attachments],
                           'review_state': 'pending'})
