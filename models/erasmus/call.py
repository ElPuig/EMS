# -*- coding: utf-8 -*-

from collections import Counter
from datetime import datetime, time, timedelta

from markupsafe import Markup
from pytz import UTC

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.sql import column_exists

from .application import RANKED_STATES, SUBMITTED_STATES
from .offer import HOLDING_STATES
from .records import LEGACY_FOLDER_SQL, PARTICIPANT_CATEGORIES
from .workflow import check_workflow_create, check_workflow_write

# The centre's two Erasmus+ projects: CFGM goes on KA121-VET, CFGS on KA131-HED.
PROJECTS = [('ka121_vet', "KA121-VET"), ('ka131_hed', "KA131-HED")]
# A staff call's panel rates the mobility plans in the two weeks after it closes.
STAFF_RATING_DAYS = 14
# Who a new staff call is for (art. 6 of the staff call): the teachers of every FP level.
STAFF_LEVELS = ['ems.level_cfgb', 'ems.level_cfgm', 'ems.level_cfgs', 'ems.level_efps', 'ems.level_pfi']


class EmsErasmusCall(models.Model):
    """Issue #683 - one Erasmus+ call: who can apply (its modalities' levels), when, and which
    documents it asks for. Issue #686: a call is for students or for staff (`audience`); a staff
    call has a panel that rates the mobility plans and ranks everyone in one list. See
    docs/en/developers/erasmus/erasmus.md."""
    _name = 'ems.erasmus.call'
    _description = 'Erasmus+ call'
    _inherit = ['ems.base']
    _order = 'date_open desc, id desc'

    name = fields.Char(string="Name", required=True, tracking=True)
    course_id = fields.Many2one(string="Course", comodel_name='ems.course', ondelete='restrict',
                                default=lambda self: self.env.company.current_course_id)
    audience = fields.Selection(string="Applicants", required=True, default='student', tracking=True,
                                selection=[('student', "Students"), ('staff', "Staff")],
                                help="Students apply in the modality of their level. Staff apply once, are "
                                     "ranked in one list, and the Erasmus team assigns each selected person a "
                                     "modality (project and period) afterwards.")
    state = fields.Selection(string="State", required=True, default='draft', tracking=True, copy=False,
                             selection=[('draft', "Draft"), ('published', "Published"), ('closed', "Closed")])
    date_open = fields.Datetime(string="Applications open", required=True, tracking=True)
    date_close = fields.Datetime(string="Applications close", required=True, tracking=True)
    subsanation_deadline = fields.Datetime(string="Corrections deadline", tracking=True, copy=False,
                                           help="Until when applicants can upload the corrections asked for.")
    interview_deadline = fields.Datetime(string="Score correction deadline", tracking=True, copy=False,
                                         help="Until when evaluators can reopen and change their interviews or "
                                              "mobility plan ratings, and the due date of the panel's tasks. A "
                                              "staff call sets it two weeks after closing.")
    claims_deadline = fields.Datetime(string="Claims deadline", tracking=True, copy=False,
                                      help="Until when applicants can claim against the provisional resolution "
                                           "(shown to them on the portal).")
    acceptance_deadline = fields.Datetime(string="Acceptance deadline", tracking=True, copy=False,
                                          help="Until when the selected can accept the place offered when the "
                                               "definitive resolution is published.")
    min_score = fields.Float(string="Minimum score", default=50.0, tracking=True,
                             help="Score needed to be eligible. The staff call has none.")
    staff_level_ids = fields.Many2many(string="Teachers of", comodel_name='ems.level',
                                       relation='ems_erasmus_call_staff_level_rel', tracking=True,
                                       help="A staff call is only for the teachers who teach a group of these "
                                            "levels, the Director and the Heads of Studies above those teachers. "
                                            "A new one is for every FP level.")
    validator_ids = fields.Many2many(string="Validates the activities", comodel_name='res.users',
                                     relation='ems_erasmus_call_validator_rel', tracking=True,
                                     domain=[('share', '=', False)],
                                     help="Staff call: the Direction that validates each selected person's activity "
                                          "and its changes (the Director and the Head of Studies of FP), whatever "
                                          "their place in the organisation chart. They can apply too.")
    description = fields.Html(string="Information for applicants",
                              help="Shown on the portal above the application form.")
    rules_document = fields.Binary(string="Published call", attachment=True, copy=False)
    rules_filename = fields.Char(string="Published call file name", copy=False)
    modality_ids = fields.One2many(string="Modalities", comodel_name='ems.erasmus.call.modality',
                                   inverse_name='call_id', copy=True)
    document_ids = fields.One2many(string="Documents", comodel_name='ems.erasmus.call.document',
                                   inverse_name='call_id', copy=True, domain=[('stage', '=', 'application')])
    # Issue #687: mobility preparation.
    commitment_text = fields.Html(
        string="Commitment letter", sanitize=True,
        help="Annex 3 of the call: what the selected accept and sign in EMS before leaving. Empty: no commitment "
             "letter is asked for.")
    preparation_document_ids = fields.One2many(
        string="Mobility documents", comodel_name='ems.erasmus.call.document', inverse_name='call_id', copy=True,
        domain=[('stage', 'in', ('preparation', 'return'))],
        help="What the participants hand in before leaving and on return, once their place is accepted.")
    task_ids = fields.One2many(string="Checklist", comodel_name='ems.erasmus.call.task', inverse_name='call_id',
                               copy=True)
    self_assessment_question_ids = fields.One2many(
        string="Weekly self-assessment", comodel_name='ems.erasmus.call.question', inverse_name='call_id', copy=True,
        help="What the participants answer on the portal every week of the stay. Empty: no self-assessment.")
    destination_ids = fields.One2many(string="Destinations", comodel_name='ems.erasmus.destination',
                                      inverse_name='call_id')
    mobility_ids = fields.One2many(string="Mobilities", comodel_name='ems.erasmus.mobility', inverse_name='call_id')
    choice_open = fields.Boolean(string="Destination choice open", readonly=True, copy=False, tracking=True)
    choice_turn_hours = fields.Integer(string="Hours per choice turn", default=72,
                                       help="How long each selected student has to choose their destination when "
                                            "their turn comes. Without an answer in time, the turn passes on and "
                                            "they choose among what is left at the end (art. 15).")
    application_ids = fields.One2many(string="Applications", comodel_name='ems.erasmus.application',
                                      inverse_name='call_id')
    resolution_ids = fields.One2many(string="Resolutions", comodel_name='ems.erasmus.resolution',
                                     inverse_name='call_id')
    offer_ids = fields.One2many(string="Place offers", comodel_name='ems.erasmus.offer', inverse_name='call_id')
    claim_ids = fields.One2many(string="Claims", comodel_name='ems.erasmus.claim', inverse_name='call_id')
    panel_ids = fields.One2many(string="Panel", comodel_name='ems.erasmus.call.panel', inverse_name='call_id',
                                copy=True, help="Staff call: who rates the mobility plans (all of them rate "
                                                "every plan).")
    free_places = fields.Integer(string="Free places", compute='_compute_offers',
                                 help="Staff call: places not accepted nor offered to someone still to answer.")
    next_reserve_id = fields.Many2one(string="Next reserve", comodel_name='ems.erasmus.application',
                                      compute='_compute_offers',
                                      help="Staff call: the best-ranked reserve without an offer waiting or accepted.")
    # Audit D-13: the ties left in the ranking after every tie-break, drawn by EMS (as a group mobility's).
    needs_draw = fields.Boolean(string="Tie to resolve", compute='_compute_needs_draw')
    draw_ids = fields.One2many(string="Draws", comodel_name='ems.erasmus.group.draw', inverse_name='call_id',
                               readonly=True)
    has_final_resolution = fields.Boolean(string="Definitive resolution published",
                                          compute='_compute_has_final_resolution')
    application_count = fields.Integer(string="Number of applications", compute='_compute_application_count')
    is_accepting = fields.Boolean(string="Accepting applications", compute='_compute_is_accepting',
                                  help="Published, and the closing date has not passed yet.")

    @api.depends('application_ids')
    def _compute_application_count(self):
        counts = dict(self.env['ems.erasmus.application']._read_group(
            [('call_id', 'in', self.ids)], ['call_id'], ['__count']))
        for call in self:
            call.application_count = counts.get(call, 0)

    @api.depends('application_ids.needs_draw')
    def _compute_needs_draw(self):
        tied = {call for call, in self.env['ems.erasmus.application'].sudo()._read_group(
            [('call_id', 'in', self.ids), ('needs_draw', '=', True)], ['call_id'])}
        for call in self:
            call.needs_draw = call in tied

    @api.depends('resolution_ids.state', 'resolution_ids.kind')
    def _compute_has_final_resolution(self):
        for call in self:
            call.has_final_resolution = 'definitive' in call._ems_published_resolutions().mapped('kind')

    @api.depends('audience', 'modality_ids.places', 'offer_ids.state', 'application_ids.state', 'application_ids.rank')
    def _compute_offers(self):
        """Issue #686: a staff call offers its places as one pool, whatever the modality."""
        for call in self:
            is_staff = call.audience == 'staff'
            call.free_places = is_staff and call._ems_free_places()
            call.next_reserve_id = is_staff and call._ems_next_reserve()

    @api.depends('state', 'date_open', 'date_close')
    def _compute_is_accepting(self):
        now = self._ems_now()
        for call in self:
            call.is_accepting = call.state == 'published' and call.date_open <= now < call.date_close

    @api.constrains('date_open', 'date_close')
    def _check_dates(self):
        for call in self:
            if call.date_close <= call.date_open:
                raise ValidationError(_("The call must close after it opens."))

    @api.onchange('audience')
    def _onchange_audience(self):
        """A staff call has no minimum score and starts with the documents of art. 8 of the staff call."""
        self.min_score = 0.0 if self.audience == 'staff' else 50.0
        if self.audience == 'staff' and not self.document_ids:
            self.document_ids = self._ems_staff_documents()
        if self.audience == 'staff' and not self.modality_ids:
            self.modality_ids = self._ems_staff_modalities()
        if self.audience == 'staff' and not self.staff_level_ids:
            self.staff_level_ids = self._ems_staff_levels()
        if self.audience == 'staff' and not self.validator_ids:
            self.validator_ids = self._ems_staff_validators(self.staff_level_ids)
        if self.audience == 'staff' and not self.interview_deadline:
            self.interview_deadline = self._ems_rating_deadline(self.date_close)

    @api.onchange('date_close')
    def _onchange_date_close(self):
        """The panel's deadline follows the closing date, unless it was changed by hand."""
        if self.audience == 'staff' and self.interview_deadline in (
                False, self._ems_rating_deadline(self._origin.date_close)):
            self.interview_deadline = self._ems_rating_deadline(self.date_close)

    @api.model
    def _ems_staff_levels(self):
        levels = self.env['ems.level']
        for xmlid in STAFF_LEVELS:
            levels |= self.env.ref(xmlid, raise_if_not_found=False) or levels
        return levels

    @api.model
    def _ems_staff_validators(self, levels):
        """The Director and the Head of Studies of FP: the one above most of the teachers of
        `levels` in the organisation chart."""
        teachers = self.env['hr.employee'].sudo().search([
            ('employee_type', '=', 'teacher'), ('teaching_ids.group_id.level_id', 'in', levels.ids)])
        heads = Counter(teacher.find_head_of_studies() for teacher in teachers)
        heads.pop(self.env['hr.employee'], None)
        head = heads and heads.most_common(1)[0][0] or self.env['hr.employee']
        return (self.env.company.sudo().director_id | head).user_id

    @api.model
    def _ems_rating_deadline(self, date_close):
        return date_close and fields.Datetime.to_datetime(date_close) + timedelta(days=STAFF_RATING_DAYS)

    @api.model_create_multi
    def create(self, vals_list):
        check_workflow_create(self, vals_list)
        for vals in vals_list:
            audience = vals.get('audience', 'student')
            if audience == 'staff':
                # Its criteria add up to 10 at most: a minimum score would leave everyone out.
                vals.setdefault('min_score', 0.0)
                levels = self._ems_staff_levels()
                vals.setdefault('staff_level_ids', [(6, 0, levels.ids)])
                vals.setdefault('validator_ids', [(6, 0, self._ems_staff_validators(levels).ids)])
                if not vals.get('interview_deadline'):
                    vals['interview_deadline'] = self._ems_rating_deadline(vals.get('date_close'))
            if audience == 'staff' and not vals.get('document_ids'):
                vals['document_ids'] = self._ems_staff_documents()
            if audience == 'staff' and not vals.get('modality_ids'):
                vals['modality_ids'] = self._ems_staff_modalities()
            # Issue #687: the documents and checklist of art. 17 (students) and art. 15 (staff), editable.
            if 'preparation_document_ids' not in vals:
                vals['preparation_document_ids'] = self._ems_preparation_documents(audience)
            if 'task_ids' not in vals:
                vals['task_ids'] = self._ems_preparation_tasks(audience)
            if audience == 'student' and 'self_assessment_question_ids' not in vals:
                vals['self_assessment_question_ids'] = self._ems_self_assessment_questions()
            if audience == 'student' and 'commitment_text' not in vals:
                vals['commitment_text'] = self._ems_commitment_text()
        return super().create(vals_list)

    @api.model
    def _ems_staff_modalities(self):
        """A staff call's places, by project (issue #697): each selected person goes on an FP
        (KA121-VET) or a higher education (KA131-HED) staff mobility, with no period: they propose
        their own dates."""
        return [(0, 0, {'sequence': 1, 'name': _("FP staff (KA121-VET)"), 'project': 'ka121_vet'}),
                (0, 0, {'sequence': 2, 'name': _("Higher education staff (KA131-HED)"), 'project': 'ka131_hed'})]

    @api.model
    def _ems_staff_documents(self):
        """The documents art. 8 of the staff call asks for. The mobility plan is written in the form (issue #697)."""
        return [(0, 0, vals) for vals in (
            {'sequence': 1, 'name': _("Identity document"), 'requirement': 'required',
             'description': _("DNI or passport (EU citizens); passport and NIE (non-EU citizens).")},
            {'sequence': 2, 'name': _("Europass CV in English"), 'requirement': 'required',
             'description': _("With your experience, skills and a photo (europass.europa.eu).")},
            {'sequence': 3, 'name': _("Language certificates"), 'requirement': 'optional',
             'description': _("Official, B2 or higher.")},
        )]

    @api.model
    def _ems_preparation_documents(self, audience):
        """Travel documents and the OLS certificate: a month after the destination is set. The
        agreements the Erasmus team fills in: signed a month before leaving at the latest (ideally
        three); the insurance policy, uploaded a month before leaving. Return documents: a month
        after the end. The Director signs the grant agreement; the Erasmus coordinator, the learning
        (or staff mobility) agreement and the Europass mobility document (KA121-VET only). The sBID
        documents and the recognition of ECTS credits (KA131-HED) are required for a curricular work
        placement only (the mobility's placement type); the student's virtual component, for a short
        blended KA131-HED stay only."""
        # Health information: confidential, only the Erasmus team sees it and it leaves only in an audit export.
        health_card = {'name': _("European Health Insurance Card"), 'file_category': '01_Dades_i_autoritzacions',
                       'confidential': True,
                       'description': _("Requested at the Social Security's electronic office.")}
        insurance = {'name': _("Insurance policy"), 'handled_by': 'team', 'due_basis': 'before_start',
                     'description': _("The Erasmus team uploads it for you to keep.")}
        agreement = {'due_basis': 'before_start', 'handled_by': 'team_to_sign', 'sign_participant': True,
                     'description': _(
                         "The Erasmus team uploads it filled in. Ideally signed three months before leaving.")}
        grant_agreement = {**agreement, 'name': _("Grant agreement"), 'sign_director': True}
        learning_agreement = {**agreement, 'name': _("Learning agreement"), 'sign_coordinator': True,
                              'sign_host': True}
        europass = {'stage': 'return', 'name': _("Europass mobility document"), 'handled_by': 'team',
                    'project': 'ka121_vet', 'sign_coordinator': True, 'description': _(
                        "It certifies what you learned during the stay. The Erasmus team issues it after the mobility, "
                        "with the learning outcomes and the actual dates of the stay, and uploads it for you to "
                        "download. The Erasmus coordinator signs it on behalf of the centre when authorised to, as "
                        "the Europass model allows.")}
        stay_description = _("It must state the dates, the tasks done and the project number.")
        # Issue #697: the tickets or boarding passes, kept in the participant's record (during the mobility).
        travel_proof = {'stage': 'return', 'name': _("Tickets or boarding passes"), 'requirement': 'optional',
                        'file_category': '03_Durant_la_mobilitat', 'description': _(
                            "Your tickets or boarding passes and, for sustainable travel, the receipts of the means of "
                            "transport. Upload them within a month of your return.")}
        if audience == 'staff':
            documents = [
                health_card,
                grant_agreement,
                insurance,
                {**learning_agreement, 'handled_by': 'participant', 'project': 'ka121_vet', 'description': _(
                    "Activities, dates and expected results, agreed with the host entity.")},
                {**learning_agreement, 'name': _("Mobility agreement"), 'handled_by': 'participant',
                 'project': 'ka131_hed', 'description': _(
                     "The Mobility Agreement for staff training: programme, dates and expected results, agreed with the "
                     "host entity.")},
                # KA121-VET: the Europass mobility document already certifies the activity; the
                # certificate is optional, for when the dates or the activity need proving.
                {'stage': 'return', 'name': _("Certificate of stay or attendance"), 'sign_host': True,
                 'project': 'ka131_hed', 'description': stay_description},
                {'stage': 'return', 'name': _("Certificate of stay or attendance"), 'sign_host': True,
                 'project': 'ka121_vet', 'requirement': 'optional', 'description': _(
                     "Only if needed to prove the dates or the activity: the Europass mobility document already "
                     "certifies it. It must state the dates, the tasks done and the project number.")},
                europass,
                travel_proof,
                {'stage': 'return', 'name': _("Report with evidence"), 'sign_participant': True,
                 'description': _("A short report with evidence, within a month of your return.")},
            ]
        else:
            # sBID (the Department of Education's work placement application): the Erasmus team
            # uploads its agreement (REF5) and activity plan (REF6), signed outside EMS.
            sbid = {'handled_by': 'team', 'requirement': 'curricular', 'due_basis': 'before_start'}
            documents = [
                {**health_card, 'description': _(
                    "Both sides, valid for the whole stay. Requested at the Social Security's electronic office: upload "
                    "it as soon as you have it.")},
                {'name': _("OLS certificate"),
                 'description': _("The certificate of the online language course (OLS), with your English level.")},
                {'name': _("Inclusion documentation"), 'requirement': 'optional', 'confidential': True,
                 'file_category': '01_Dades_i_autoritzacions',
                 'description': _("Only if it applies to you: evidence of fewer opportunities, grants, special needs. "
                                  "Only the Erasmus team sees it.")},
                {'name': _("Family authorisation to travel"), 'requirement': 'minor', 'sign_guardian': True,
                 'file_category': '01_Dades_i_autoritzacions'},
                {'name': _("Authorisation for minors to travel abroad"), 'requirement': 'minor',
                 'file_category': '01_Dades_i_autoritzacions',
                 'description': _("Processed with the Mossos d'Esquadra.")},
                {**grant_agreement, 'sign_guardian': True},
                {**learning_agreement, 'sign_guardian': True, 'description': _(
                    "GM: learning agreement. GS: Learning Agreement for Traineeships. The Erasmus team uploads it "
                    "filled in. Ideally signed three months before leaving.")},
                {**sbid, 'name': _("sBID agreement (REF5)"), 'sign_director': True, 'sign_participant': True,
                 'sign_host': True, 'description': _(
                     "Curricular work placement: the Erasmus team uploads it from sBID.")},
                {**sbid, 'name': _("sBID activity plan (REF6)"), 'sign_tutor': True, 'sign_participant': True,
                 'sign_host': True, 'description': _(
                     "Curricular work placement: the Erasmus team uploads it from sBID.")},
                insurance,
                # The virtual component of a short blended KA131-HED stay: the student's preparation, kept
                # in the record.
                {'name': _("Virtual component"), 'project': 'ka131_hed', 'requirement': 'short_blended',
                 'open_days': 30, 'due_basis': 'before_start', 'due_days': 1,
                 'description': _(
                     "Short stays (30 days or fewer): a PDF with your preparation before leaving. Information about the "
                     "city, how you will get to the company and how much transport costs, and the exercises on the "
                     "technologies and tasks of the host company (the Erasmus coordinator asks the company about "
                     "them).")},
                {'stage': 'return', 'name': _("Certificate of stay"), 'handled_by': 'team_to_sign', 'sign_host': True,
                 'description': _("The Erasmus team uploads it for your tutor at the host company to sign at the end "
                                  "of the stay. It must state the dates, the tasks done and the project number. "
                                  "Upload it signed within a month of your return.")},
                europass,
                {'stage': 'return', 'name': _("Recognition of ECTS credits"), 'handled_by': 'team',
                 'project': 'ka131_hed', 'requirement': 'curricular', 'description': _(
                     "The centre's recognition of the stay's ECTS credits. The Erasmus team uploads it.")},
                travel_proof,
            ]
        defaults = {'preparation': 'destination', 'return': 'after_end'}
        return [(0, 0, {'sequence': index, 'stage': vals.get('stage', 'preparation'), 'requirement': 'required',
                        'due_days': 30, 'due_basis': defaults[vals.get('stage', 'preparation')], **vals})
                for index, vals in enumerate(documents, 1)]

    @api.model
    def _ems_self_assessment_questions(self):
        """The weekly self-assessment of a students' call during the stay, editable."""
        questions = [(_("What did you do this week?"), 'text'), (_("What have you learned?"), 'text'),
                     (_("How do you rate your week?"), 'rating'),
                     (_("What was hardest for you, and what would you improve?"), 'text')]
        return [(0, 0, {'sequence': index, 'name': name, 'kind': kind})
                for index, (name, kind) in enumerate(questions, 1)]

    @api.model
    def _ems_commitment_text(self):
        """Annex 3 of the students' call, accepted and signed in EMS by each selected student."""
        commitments = [
            _("Hand in the travel documents within the deadline."),
            _("Attend the preparation sessions and take the online language course (OLS)."),
            _("Comply with the timetable and rules of the host entity, the accommodation and the destination "
              "country, and with the instructions of the Erasmus coordination."),
            _("Complete the stay on the agreed dates."),
            _("In case of early return, interruption or breaking off the relationship with the host entity by my own "
              "will or for reasons attributable to me, bear the cost of the return trip and return the amounts that "
              "cannot be justified to SEPIE and the expenses already paid that cannot be recovered, except in cases "
              "of force majeure accepted by SEPIE."),
            _("In case of renouncing without a justified cause before leaving, bear the expenses already committed "
              "that cannot be recovered."),
            _("Hand in the certificate of stay, answer the final report (EU Survey) and take part in the "
              "dissemination activities."),
        ]
        return Markup("<p>{}</p>{}").format(
            _("I declare that I know the rules of the call for Erasmus+ internship grants and I commit to:"),
            Markup("<ol>{}</ol>").format(Markup().join(Markup("<li>{}</li>").format(item) for item in commitments)))

    @api.model
    def _ems_preparation_tasks(self, audience):
        if audience == 'staff':
            names = [('preparation', _("Preparation meetings")),
                     ('preparation', _("Activities left for your groups")),
                     ('return', _("News item on the centre's website, following the Erasmus+ visual identity")),
                     ('return', _("Share it at a department or cycles meeting, if it is considered necessary"))]
        else:
            names = [('preparation', _("Preparation sessions")),
                     ('return', _("Dissemination activities"))]
        return [(0, 0, {'sequence': index, 'stage': step[0], 'name': step[1], **(step[2] if len(step) > 2 else {})})
                for index, step in enumerate(names, 1)]

    def write(self, vals):
        check_workflow_write(self, vals)
        if 'audience' in vals and self.filtered(
                lambda call: call.audience != vals['audience'] and call.application_ids):
            raise UserError(_("A call with applications cannot change who it is for."))
        # A staff call's panel deadline follows its closing date, unless it was changed by hand.
        following = self.filtered(lambda call: call.audience == 'staff' and call.interview_deadline in (
            False, self._ems_rating_deadline(call.date_close))) if 'date_close' in vals and \
            'interview_deadline' not in vals else self.browse()
        result = super().write(vals)
        if following:
            following.write({'interview_deadline': self._ems_rating_deadline(vals['date_close'])})
        if 'interview_deadline' in vals:
            self._ems_move_evaluation_activities()
        return result

    def _ems_move_evaluation_activities(self):
        """The open tasks of the interviews and mobility plan ratings follow the deadline."""
        applications = self.sudo().application_ids
        for evaluation in (*applications.interview_ids, *applications.plan_rating_ids):
            if evaluation.activity_ids:
                evaluation.activity_ids.date_deadline = evaluation._ems_activity_date()

    def copy_data(self, default=None):
        vals_list = super().copy_data(default)
        default = default or {}
        for call, vals in zip(self, vals_list):
            if 'name' not in default:
                vals['name'] = _("%s (copy)", call.name)
        return vals_list

    def action_publish(self):
        for call in self:
            if call.audience == 'student' and not call.modality_ids:
                raise UserError(_("Add at least one modality before publishing the call."))
            if call.audience == 'student' and call.modality_ids.filtered(lambda modality: not modality.level_ids):
                raise UserError(_("Every modality of a students' call needs the levels whose students apply in it."))
            if call.audience == 'staff' and not call.staff_level_ids:
                raise UserError(_("Say which levels' teachers the staff call is for before publishing it."))
            if call.audience == 'staff' and not call.validator_ids:
                raise UserError(_("Say who validates the staff's activities before publishing the call."))
            if not call.document_ids.filtered(lambda document: document.requirement == 'required'):
                raise UserError(_("Add at least one required document before publishing the call."))
        self._ems_set_state('draft', 'published')

    def action_back_to_draft(self):
        if self.application_ids.filtered(lambda application: application.state != 'draft'):
            raise UserError(_("A call with submitted applications cannot go back to draft."))
        self._ems_set_state('published', 'draft')

    def action_close(self):
        """Close the applications: those never submitted stay as not submitted, and the scoring
        data of the submitted ones is frozen (issue #684)."""
        self._ems_set_state('published', 'closed')
        drafts = self.application_ids.filtered(lambda application: application.state == 'draft')
        drafts._ems_set_state('not_submitted')
        self.filtered(lambda call: call.audience == 'student').application_ids.filtered(
            lambda application: application.state in SUBMITTED_STATES)._ems_freeze_scoring_data()

    def action_send_to_panel(self):
        """Issue #686: one rating per admitted application and panel member, for those still
        without one. A member who is a candidate in the call abstains (art. 10): their rating has no
        evaluator and does not count."""
        Rating = self.env['ems.erasmus.plan_rating']
        for call in self:
            if call.audience != 'staff' or call.state != 'closed':
                raise UserError(_("Only a closed staff call sends the mobility plans to the panel."))
            if not call.panel_ids:
                raise UserError(_("Add the panel members first."))
            if not call.interview_deadline:
                raise UserError(_("Set the call's score correction deadline first: it is the due date of the "
                                  "panel's tasks."))
            candidates = call._ems_candidate_partners()
            vals_list = []
            for application in call.application_ids.filtered(lambda application: application.state == 'admitted'):
                rated = application.sudo().plan_rating_ids.panel_member_id
                for member in call.panel_ids.user_id - rated:
                    is_candidate = member.partner_id in candidates
                    vals_list.append({
                        'application_id': application.id, 'panel_member_id': member.id,
                        'evaluator_id': not is_candidate and member.id,
                        'abstention_reason': is_candidate and _("Candidate in this call"),
                    })
            if not vals_list:
                raise UserError(_("Every admitted application already has its ratings."))
            Rating.create(vals_list)

    def action_view_ranking(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('ems.action_erasmus_ranking')
        action['domain'] = [('call_id', '=', self.id), ('state', 'in', RANKED_STATES)]
        if self.audience == 'staff':
            action['views'] = [(self.env.ref('ems.view_erasmus_staff_ranking_list').id, 'list'), (False, 'form')]
        return action

    def action_offer_place(self):
        """Issue #685: offer a free place to the next reserve (the team confirms it in the wizard)."""
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('ems.action_erasmus_offer_wizard')
        action['context'] = {'default_call_id': self.id}
        return action

    def action_export_participants(self):
        self.ensure_one()
        return self.application_ids.action_export_participants()

    def action_open_destination_choice(self):
        """Issue #687 - start the destination choice by turns (art. 15 of the students' call)."""
        for call in self:
            if call.audience != 'student' or not call.has_final_resolution:
                raise UserError(_("The destinations are chosen after the definitive resolution of a students' call."))
            if not call.destination_ids:
                raise UserError(_("Add the destinations first."))
        self._ems_check_manager()
        self.sudo().write({'choice_open': True})
        self._ems_advance_choice()

    def _ems_advance_choice(self):
        """Per modality: a modality with one destination assigns it to everyone directly (art.
        15); otherwise the best-ranked student still choosing gets the turn, unless one is open.
        Who missed their turn waits until the others have chosen, and then chooses among what is
        left, with no turn nor deadline."""
        now = self._ems_now()
        for call in self.filtered(lambda call: call.choice_open and call.audience == 'student'):
            choosing = call.sudo().mobility_ids._ems_choosing()
            for modality in call.modality_ids:
                waiting = choosing.filtered(lambda mobility: mobility.modality_id == modality).sorted('rank')
                destinations = call.destination_ids.filtered(lambda destination: destination.modality_id == modality)
                if len(destinations) == 1:
                    for mobility in waiting.filtered(lambda mobility: destinations._ems_suits(mobility)):
                        mobility._ems_assign(destinations)
                    continue
                if not destinations or waiting.filtered('turn_deadline'):
                    continue
                in_order = waiting.filtered(lambda mobility: not mobility.turn_missed)
                for mobility in in_order[:1]:
                    mobility.write(
                        {'turn_deadline': now + timedelta(hours=call.choice_turn_hours)})
                    mobility._ems_send('ems.email_template_erasmus_choice_turn')
                if not in_order:
                    left = waiting.filtered(lambda mobility: not mobility.free_choice)
                    left.write({'free_choice': True})
                    left._ems_send('ems.email_template_erasmus_choice_turn')

    def _ems_candidate_partners(self):
        """Who applied to this call (submitted at least once): they never rate in it."""
        self.ensure_one()
        return self.sudo().application_ids.filtered(
            lambda application: application.state not in ('draft', 'not_submitted')).partner_id

    def _ems_holding_applications(self, modality=None):
        """The applications holding a place (offer waiting or accepted), of `modality` for a
        students' call, of the whole call for a staff one."""
        self.ensure_one()
        offers = self.offer_ids.filtered(lambda offer: offer.state in HOLDING_STATES and (
            self.audience == 'staff' or offer.modality_id == modality))
        return offers.application_id

    def _ems_free_places(self, modality=None):
        self.ensure_one()
        places = sum(self.modality_ids.mapped('places')) if self.audience == 'staff' else modality.places
        return places - len(self._ems_holding_applications(modality))

    def _ems_free_place_names(self):
        """Where a free place can be offered to a reserve: the modalities of a students' call, the
        call itself for a staff one."""
        self.ensure_one()
        if self.audience == 'staff':
            return [self.name] if self._ems_free_places() > 0 and self._ems_next_reserve() else []
        return [modality.name for modality in self.modality_ids
                if self._ems_free_places(modality) > 0 and self._ems_next_reserve(modality)]

    def _ems_sync_free_place_tasks(self):
        """A task for each member of the Erasmus team when a place a reserve can take is free (a
        renunciation, an offer without an answer, a rectification); EMS never offers it on its own
        (offer wizard). Marked done once no such place is left."""
        activity_type = self.env.ref('ems.mail_activity_erasmus_free_place')
        team = self._ems_erasmus_team()
        for call in self.sudo():
            tasks = call.activity_ids.filtered(lambda activity: activity.activity_type_id == activity_type)
            names = call._ems_free_place_names()
            if not names:
                tasks.action_feedback()
                continue
            for user in team - tasks.user_id:
                call.activity_schedule(
                    activity_type_id=activity_type.id, user_id=user.id,
                    summary=_("Erasmus+: a place is free in %s: offer it to the next reserve", ", ".join(names)))

    def _ems_next_reserve(self, modality=None):
        """The best-ranked reserve without a place, of `modality` (students) or the call (staff)."""
        self.ensure_one()
        holding = self._ems_holding_applications(modality)
        reserves = self.application_ids.filtered(
            lambda application: application.state == 'reserve' and application not in holding and (
                self.audience == 'staff' or application.modality_id == modality))
        return reserves.sorted('rank')[:1]

    def _ems_published_resolutions(self):
        self.ensure_one()
        return self.resolution_ids.filtered(lambda resolution: resolution.state == 'published')

    def action_view_mobilities(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('ems.action_erasmus_mobility')
        action['domain'] = [('call_id', '=', self.id)]
        return action

    def action_view_applications(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('ems.action_erasmus_application')
        action['domain'] = [('call_id', '=', self.id)]
        action['context'] = {'default_call_id': self.id}
        return action

    def _ems_set_state(self, from_state, to_state):
        self._ems_check_manager()
        for call in self:
            if call.state != from_state:
                raise UserError(_("The call %s is not in the right state for this action.", call.name))
        self.sudo().write({'state': to_state})

    def action_draw_ties(self):
        """Audit D-13: the Erasmus coordinator resolves the ties left in the ranking after every
        tie-break by a draw EMS runs and keeps (ems.erasmus.group.draw), as in a group mobility: each
        tied set of a modality (a staff call's, of the whole list) in a random order nobody chooses.
        Usually before the provisional resolution, which needs every tie drawn; again when a correction
        (a claim upheld, before a rectification) ties someone with others, the whole set is drawn anew.
        A set already drawn is never drawn again otherwise."""
        self.env['ems.erasmus.group.mobility']._ems_check_coordinator()
        Draw = self.env['ems.erasmus.group.draw']
        for call in self.sudo():
            tied = call.application_ids.filtered('needs_draw')
            if not tied:
                raise UserError(_("There is no tie to draw in %s.", call.name))
            Draw._ems_run(call, [
                (applications, {'score_total': applications[0].score_total})
                for applications in tied.grouped(lambda application: (
                    application.audience == 'student' and application.modality_id,
                    application._ems_rank_key()[:-1])).values()])

    def _ems_check_manager(self):
        """The actions write the call's workflow fields as superuser: only once this is checked."""
        if not self.env['ems.erasmus.application']._ems_can_manage():
            raise AccessError(_("Only the Erasmus team manages a call."))

    def _ems_now(self):
        """Now, from the centre's clock (ems.datetime_utils), as Odoo stores datetimes: naive UTC."""
        utils = self.env['ems.datetime_utils']
        return utils.datetime_to_odoo(utils.local_datetime_to_utc(utils.get_local_datetime()))

    def _ems_local_deadline(self):
        """The corrections deadline as the applicant reads it: in the centre's timezone."""
        self.ensure_one()
        return self._ems_local_format(self.subsanation_deadline)

    @api.model
    def _ems_local_format(self, value):
        """A stored (UTC) datetime as the centre reads it, for the emails."""
        if not value:
            return ''
        return self.env['ems.datetime_utils'].utc_datetime_to_local(value.replace(tzinfo=UTC)).strftime(
            '%d/%m/%Y %H:%M')

    def _ems_staff_can_apply(self, employee):
        """Art. 6 of the staff call: the teachers of a group of its levels and the Direction that
        validates the activities (the Director and the Head of Studies of FP). Never the
        administration staff nor a teacher of ESO or Batxillerat only."""
        self.ensure_one()
        employee = employee.sudo()
        return employee.user_id in self.validator_ids or (
            employee.employee_type == 'teacher' and bool(employee.teaching_ids.group_id.level_id & self.staff_level_ids))

    def _ems_modality_for(self, partner):
        """The modality `partner` competes in: the one whose levels include their main group's."""
        self.ensure_one()
        level = self.audience == 'student' and partner.contact_type == 'student' and partner.main_group_id.level_id
        if not level:
            return self.env['ems.erasmus.call.modality']
        return self.modality_ids.filtered(lambda modality: level in modality.level_ids)[:1]

    def _ems_course_strike_count(self, partner):
        """How many conduct warnings (ems.strike) `partner` has during the call's course."""
        self.ensure_one()
        return self._ems_partner_course_strike_count(partner, self.course_id)

    @api.model
    def _ems_partner_course_strike_count(self, partner, course):
        """How many conduct warnings `partner` has during `course` (empty: the current one). Issue
        #701: group mobilities apply the same rule."""
        course = course or self.env.company.current_course_id
        if not course or partner.contact_type != 'student':
            return 0
        utils = self.env['ems.datetime_utils']
        first_day = datetime.combine(course.date_range()[0], time.min, tzinfo=utils.current_tz())
        return self.env['ems.strike'].sudo().search_count([
            ('student_id', '=', partner.id), ('date', '>=', utils.datetime_to_odoo(first_day.astimezone(UTC)))])

    @api.model
    def _ems_conduct_blocked_count(self, count):
        """Students' call art. 6: as many conduct warnings this course as the number that sends the
        case to the coexistence team (res.company.strike_escalation_threshold), or more, rule a
        student out. No threshold, no rule."""
        threshold = self.env.company.strike_escalation_threshold
        return threshold > 0 and count >= threshold

    def _ems_conduct_blocked(self, partner):
        self.ensure_one()
        return self.audience == 'student' and self._ems_conduct_blocked_count(self._ems_course_strike_count(partner))

    @api.model
    def _ems_erasmus_team(self):
        """The Erasmus team's users (coordination and mobility technicians)."""
        return self.env.ref('ems.group_erasmus').sudo().users.filtered(lambda user: not user.share)


class EmsErasmusCallModality(models.Model):
    """A selection list of a call, with its own places (e.g. GM and GS), and the levels whose
    students compete in it."""
    _name = 'ems.erasmus.call.modality'
    _description = 'Erasmus+ call modality'
    _order = 'call_id, sequence, id'

    call_id = fields.Many2one(string="Call", comodel_name='ems.erasmus.call', required=True, ondelete='cascade',
                              index=True)
    sequence = fields.Integer(string="Sequence", default=10)
    name = fields.Char(string="Name", required=True)
    level_ids = fields.Many2many(string="Levels", comodel_name='ems.level',
                                 help="Students' call: students whose main group is of one of these levels apply in "
                                      "this modality.")
    project = fields.Selection(string="Project", selection=PROJECTS)
    places = fields.Integer(string="Places")
    period = fields.Char(string="Period")
    destinations = fields.Char(string="Destinations")
    free_places = fields.Integer(string="Free places", compute='_compute_offers',
                                 help="Places not accepted nor offered to someone still to answer.")
    next_reserve_id = fields.Many2one(string="Next reserve", comodel_name='ems.erasmus.application',
                                      compute='_compute_offers',
                                      help="The best-ranked reserve without an offer waiting or accepted.")

    @api.depends('places', 'call_id.audience', 'call_id.offer_ids.state', 'call_id.application_ids.state',
                 'call_id.application_ids.rank')
    def _compute_offers(self):
        """Issue #685: places still to offer, and to whom EMS proposes offering the next one. A
        staff call offers its places as one pool (the call's own fields), not per modality."""
        for modality in self:
            call = modality.call_id
            is_student = call.audience == 'student'
            modality.free_places = is_student and call._ems_free_places(modality)
            modality.next_reserve_id = is_student and call._ems_next_reserve(modality)

    @api.constrains('level_ids', 'call_id')
    def _check_one_modality_per_level(self):
        for call in self.call_id:
            levels = call.modality_ids.level_ids
            if len(levels) != sum(len(modality.level_ids) for modality in call.modality_ids):
                raise ValidationError(_("A level can only belong to one modality of the call."))


class EmsErasmusCallDocument(models.Model):
    """A document the call asks applicants for."""
    _name = 'ems.erasmus.call.document'
    _description = 'Erasmus+ call document'
    _order = 'call_id, sequence, id'

    call_id = fields.Many2one(string="Call", comodel_name='ems.erasmus.call', required=True, ondelete='cascade',
                              index=True)
    sequence = fields.Integer(string="Sequence", default=10)
    name = fields.Char(string="Name", required=True)
    description = fields.Text(string="Instructions", help="Shown to the applicant next to the upload.")
    requirement = fields.Selection(string="Requirement", required=True, default='required', selection=[
        ('required', "Required"), ('optional', "Optional"), ('minor', "Required for minors"),
        ('curricular', "Required for curricular work placement"), ('short_blended', "Short blended mobilities only")],
        help="Required for curricular work placement: when the student's stay is a work placement managed in sBID "
             "(the mobility's Placement type); optional for an extracurricular stay or a recent graduate. Short "
             "blended mobilities only: asked for in a KA131-HED stay of 30 days or fewer, and not shown otherwise.")
    confidential = fields.Boolean(string="Confidential",
                                  help="Only the Erasmus team sees these files (e.g. evidence of fewer opportunities).")
    stage = fields.Selection(string="When", required=True, default='application', selection=[
        ('application', "With the application"), ('preparation', "Before leaving"), ('return', "On return")])
    modality_ids = fields.Many2many(string="Only for modalities", comodel_name='ems.erasmus.call.modality',
                                    domain="[('call_id', '=', call_id)]",
                                    help="Mobility documents: empty, every modality.")
    project = fields.Selection(string="Only for project", selection=PROJECTS,
                               help="Mobility documents: only for the modalities of this project (e.g. the Europass "
                                    "mobility document, KA121-VET only). Empty: both projects.")
    sign_participant = fields.Boolean(string="Signed by the participant")
    sign_guardian = fields.Boolean(string="Signed by the legal guardian", help="Only for minors.")
    sign_tutor = fields.Boolean(string="Signed by the centre's tutor",
                                help="The work placement tutor of the centre that appears in sBID.")
    sign_director = fields.Boolean(string="Signed by the Director")
    sign_coordinator = fields.Boolean(string="Signed by the Erasmus coordinator")
    sign_host = fields.Boolean(string="Signed by the host entity")
    signers = fields.Char(string="Signed by", compute='_compute_signers')
    due_basis = fields.Selection(string="Due", selection=[
        ('destination', "After the destination is set"), ('before_start', "Before leaving"),
        ('after_end', "After returning")], help="Mobility documents: what the deadline counts from.")
    due_days = fields.Integer(string="Days", help="Mobility documents: days counted from the Due point.")
    open_days = fields.Integer(string="Opens (days before leaving)",
                               help="Mobility documents before leaving: the participant sees it and can upload it only "
                                    "from this many days before leaving. 0: as soon as the destination is set.")
    handled_by = fields.Selection(string="Handled by", default='participant', required=True, selection=[
        ('participant', "The participant uploads it"), ('team_to_sign', "The team fills it in, the participant signs it"),
        ('team', "The team provides it")],
        help="Mobility documents. Filled in by the team: the Erasmus team uploads it filled in, the participant "
             "downloads it, signs it and uploads it signed, and is not asked for it before. Provided by the team (e.g. "
             "the insurance policy): the team uploads it and the participant only downloads it.")
    file_category = fields.Selection(
        string="Category in the record", selection=PARTICIPANT_CATEGORIES,
        help="Where the document goes in the participant's record and in the exported ZIP. Empty: data and "
             "authorisations (application), before the mobility (before leaving) or after the mobility (on return).")
    panel_visible = fields.Boolean(string="Shown to the panel",
                                   help="Staff call: the panel members see these files when they rate (the mobility "
                                        "plan), and nothing else of the application.")

    @api.depends('sign_participant', 'sign_guardian', 'sign_director', 'sign_coordinator', 'sign_tutor', 'sign_host')
    def _compute_signers(self):
        """Issue #687: who signs it, outside EMS, before it is uploaded."""
        labels = [('sign_participant', _("participant")), ('sign_guardian', _("legal guardian")),
                  ('sign_director', _("director")), ('sign_coordinator', _("Erasmus coordinator")),
                  ('sign_tutor', _("centre's tutor")), ('sign_host', _("host entity"))]
        for document in self:
            document.signers = ", ".join(label for name, label in labels if document[name])

    def _auto_init(self):
        """A database that still has the SEPIE folder of each document (the dossier before the records,
        never released) gets the record's category from it, before Odoo drops the old column: the health
        card stays with the data and authorisations (and confidential), the tickets during the mobility.
        Nothing to do anywhere else."""
        legacy = column_exists(self.env.cr, self._table, 'sepie_folder')
        result = super()._auto_init()
        if legacy:
            self.env.cr.execute(LEGACY_FOLDER_SQL)
            if self.env.cr.rowcount:
                # Both are stored on the lines: the category, and whether it is confidential (record rules
                # and exports read it there).
                Line = self.env['ems.erasmus.application.document']
                lines = Line.search([])
                for name in ('file_category', 'confidential'):
                    self.env.add_to_compute(Line._fields[name], lines)
        return result
