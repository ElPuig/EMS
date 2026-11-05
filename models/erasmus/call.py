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
# The reminder before a call closes is emailed from this hour on, in the centre's time.
REMINDER_HOUR = 9


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
    rules_document = fields.Binary(string="Call rules (PDF)", attachment=True, copy=False,
                                   help="The signed PDF of the call's rules. Applicants download it on the portal "
                                        "with \"Read the call\", and it goes into the project's documents.")
    rules_filename = fields.Char(string="Call rules file name", copy=False)
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
    places_total = fields.Integer(string="Places", compute='_compute_offers')
    places_accepted = fields.Integer(string="Places accepted", compute='_compute_offers',
                                     help="Selected applicants who have accepted their place.")
    offers_pending = fields.Integer(string="Offers waiting for an answer", compute='_compute_offers')
    # Audit D-13: the ties left in the ranking after every tie-break, drawn by EMS (as a group mobility's).
    needs_draw = fields.Boolean(string="Tie to resolve", compute='_compute_needs_draw')
    draw_ids = fields.One2many(string="Draws", comodel_name='ems.erasmus.group.draw', inverse_name='call_id',
                               readonly=True)
    has_final_resolution = fields.Boolean(string="Definitive resolution published",
                                          compute='_compute_has_final_resolution')
    has_provisional_resolution = fields.Boolean(string="Provisional resolution published",
                                                compute='_compute_has_final_resolution')
    application_count = fields.Integer(string="Number of applications", compute='_compute_application_count')
    is_accepting = fields.Boolean(string="Accepting applications", compute='_compute_is_accepting',
                                  help="Published, and the closing date has not passed yet.")
    # The notice of the open call to whoever can apply, sent by the Erasmus team, and the reminder
    # before it closes to those who have not submitted (the issue-#682 review).
    announce_date = fields.Datetime(string="Notice sent on", readonly=True, copy=False)
    announce_count = fields.Integer(string="Notice sent to", readonly=True, copy=False,
                                    help="How many people the notice of the open call was emailed to.")
    reminder_days = fields.Integer(string="Reminder (days before closing)", default=3,
                                   help="That many days before the closing date, EMS emails whoever can apply and "
                                        "has not submitted an application yet. Only once, and only after the notice "
                                        "of the open call. 0: no reminder.")
    reminder_date = fields.Datetime(string="Reminder sent on", readonly=True, copy=False)
    reminder_count = fields.Integer(string="Reminder sent to", readonly=True, copy=False,
                                    help="How many people the reminder before the closing date was emailed to.")

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
            kinds = call._ems_published_resolutions().mapped('kind')
            call.has_final_resolution = 'definitive' in kinds
            call.has_provisional_resolution = 'provisional' in kinds

    @api.depends('audience', 'modality_ids.places', 'offer_ids.state', 'application_ids.state', 'application_ids.rank')
    def _compute_offers(self):
        """Issue #686: a staff call offers its places as one pool, whatever the modality. And how
        many places are accepted and how many offers wait for an answer, to know when the destination
        choice can open (the 2026-11-03 review)."""
        for call in self:
            is_staff = call.audience == 'staff'
            call.free_places = is_staff and call._ems_free_places()
            call.next_reserve_id = is_staff and call._ems_next_reserve()
            call.places_total = sum(call.modality_ids.mapped('places'))
            call.places_accepted = len(call.application_ids.filtered(lambda application: application.state == 'accepted'))
            call.offers_pending = len(call.offer_ids.filtered(lambda offer: offer.state == 'pending'))

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

    @api.constrains('reminder_days')
    def _check_reminder_days(self):
        if any(call.reminder_days < 0 for call in self):
            raise ValidationError(_("The reminder cannot be after the closing date."))

    @api.onchange('audience')
    def _onchange_audience(self):
        """A staff call has no minimum score and starts with the documents of art. 8 of the staff call;
        a new call, unsaved, swaps its defaults for those of the audience chosen."""
        staff = self.audience == 'staff'
        self.min_score = 0.0 if staff else 50.0
        if not self._origin.id:
            # Each list is given as new records, not as commands: both document lists are lines of
            # the same model, and replacing one with commands brought back lines of the other.
            for name, value in self._ems_audience_defaults(self.audience).items():
                field = self._fields[name]
                if field.type == 'one2many':
                    Lines = self.env[field.comodel_name]
                    value = Lines.concat(Lines, *(Lines.new(command[2]) for command in value))
                self[name] = value
        if staff and not self.document_ids:
            self.document_ids = self._ems_staff_documents()
        if staff and not self.modality_ids:
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
            # Checked by value, not by key: the form always sends these fields, empty on a new call.
            for name, value in self._ems_audience_defaults(audience).items():
                if not vals.get(name):
                    vals[name] = value
        return super().create(vals_list)

    @api.model
    def default_get(self, fields_list):
        """The 2026-11-04 usage test: a new call shows its default documents, steps and questions
        before it is saved (the Documents tab was empty until then)."""
        values = super().default_get(fields_list)
        for name, value in self._ems_audience_defaults(values.get('audience', 'student')).items():
            if name in fields_list:
                values.setdefault(name, value)
        return values

    @api.model
    def _ems_audience_defaults(self, audience):
        """What a new call of `audience` starts with: the documents of art. 8, the staff call's
        modalities, and (issue #687) the documents and checklist of art. 17 (students) and art. 15
        (staff), the self-assessment questions and the commitment letter, all editable."""
        staff = audience == 'staff'
        return {
            'modality_ids': self._ems_staff_modalities() if staff else [],
            'preparation_document_ids': self._ems_preparation_documents(audience),
            'task_ids': self._ems_preparation_tasks(audience),
            'self_assessment_question_ids': [] if staff else self._ems_self_assessment_questions(),
            'commitment_text': False if staff else self._ems_commitment_text(),
            'document_ids': self._ems_staff_documents() if staff else self._ems_student_documents(),
        }

    @api.model
    def _ems_staff_modalities(self):
        """A staff call's places, by project (issue #697): each selected person goes on an FP
        (KA121-VET) or a higher education (KA131-HED) staff mobility, with no period: they propose
        their own dates."""
        return [(0, 0, {'sequence': 1, 'name': _("FP staff (KA121-VET)"), 'project': 'ka121_vet'}),
                (0, 0, {'sequence': 2, 'name': _("Higher education staff (KA131-HED)"), 'project': 'ka131_hed'})]

    @api.model
    def _ems_student_documents(self):
        """The documents art. 8 of the students' call asks for (the 2026-11-03 review): the CV and
        the video first, with what they must contain, then the optional ones; the evidence of fewer
        opportunities only once the student declares them."""
        return [(0, 0, vals) for vals in (
            {'sequence': 1, 'name': _("Europass CV in English"), 'requirement': 'required', 'upload_kind': 'pdf',
             'help_url': 'https://europass.europa.eu/en/create-europass-cv',
             'description': _("Made with the Europass editor, in English and with a photo. Include what you study, "
                              "what you are learning in the cycle, your strong points and a short \"About me\". It "
                              "is the CV we will send to the company of your internship: brief and clear. PDF only.")},
            {'sequence': 2, 'name': _("Presentation video in English"), 'requirement': 'required', 'upload_kind': 'link',
             'description': _("About one minute: why would you like to take part in Erasmus+ and what tasks would you "
                              "like to do in your host company? Save it in Google Drive with your school account, "
                              "click Share and, under General access, choose Institut Puig Castellar as Viewer. Copy "
                              "the link and paste it here.")},
            {'sequence': 3, 'name': _("Official language certificates"), 'requirement': 'optional',
             'single_file': False,
             'description': _("Official certificates of foreign languages, if you have any.")},
            {'sequence': 4, 'name': _("Evidence of fewer opportunities"), 'requirement': 'fewer_opportunities',
             'confidential': True,
             'description': _("Confidential: only the Erasmus team sees it (annex 2 of the call).")},
        )]

    @api.model
    def _ems_staff_documents(self):
        """The documents art. 8 of the staff call asks for: only the language certificates. The
        mobility plan is written in the form (issue #697); the CV is no longer asked for and the
        identity document only of whoever goes (a mobility document, the 2026-11-03 review)."""
        return [(0, 0, {'sequence': 1, 'name': _("Language certificates"), 'requirement': 'optional',
                         'single_file': False, 'description': _("Official, B2 or higher.")})]

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
                # The 2026-11-03 review: asked only of whoever goes, no longer with the application.
                {'name': _("Identity document"), 'file_category': '01_Dades_i_autoritzacions',
                 'description': _("DNI or passport (EU citizens); passport and NIE (non-EU citizens).")},
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
        # The terms of the "assumpció de responsabilitat" the centre had families and adult students sign
        # on paper before EMS (2026-11-05): the letter replaces it, so the family no longer authorises
        # taking part when applying, but by accepting this letter.
        accepted = [
            _("The responsibility of the centre and, where applicable, of the accompanying teachers is limited to the "
              "activities of the programme agreed with the host entity, and they are not responsible for the "
              "consequences of my inappropriate conduct."),
            _("If I seriously break the rules, I may be sent back immediately, and the extra expenses arising from "
              "it, like the contingencies of the trip, will be borne by me (or by my family, if I am a minor)."),
        ]
        items = Markup("<ol>{}</ol>").format(Markup().join(Markup("<li>{}</li>").format(item) for item in commitments))
        terms = Markup("<ul>{}</ul>").format(Markup().join(Markup("<li>{}</li>").format(item) for item in accepted))
        return Markup("<p>{}</p>{}<p>{}</p>{}<p><em>{}</em></p>").format(
            _("I declare that I know the rules of the call for Erasmus+ internship grants and I commit to:"), items,
            _("And I accept that:"), terms,
            _("If the student is a minor, their father, mother or legal guardian also accepts this letter from their "
              "EMS access and, by doing so, authorises them to take part in the stay."))

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
            # A staff call asks for the form only (the 2026-11-03 review: no CV nor identity document).
            if call.audience == 'student' and not call.document_ids.filtered(
                    lambda document: document.requirement == 'required'):
                raise UserError(_("Add at least one required document before publishing the call."))
        self._ems_set_state('draft', 'published')
        # The 2026-11-04 usage test: a staff call opens without its places (they are added later,
        # with the projects), but it was only noticed when preparing the resolution: warned now.
        without_places = self.filtered(lambda call: call.audience == 'staff'
                                       and not sum(call.modality_ids.mapped('places')))
        if not without_places:
            return None
        return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
            'type': 'warning', 'sticky': True,
            'message': _("Published without places: add them to the modalities before preparing the resolution "
                         "lists (%s).", ", ".join(without_places.mapped('name'))),
            'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'}}}

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
        action['context'] = {'default_call_id': self.id}
        if self.audience == 'staff':
            action['views'] = [(self.env.ref('ems.view_erasmus_staff_ranking_list').id, 'list'), (False, 'form')]
        return action

    def action_announce(self):
        """The notice of the open call: the Erasmus team checks how many people get it and sends it."""
        self.ensure_one()
        self._ems_check_manager()
        action = self.env['ir.actions.act_window']._for_xml_id('ems.action_erasmus_call_announce')
        action['context'] = {'default_call_id': self.id}
        return action

    def _ems_send_announce(self):
        """Email the notice of the open call to whoever can apply. Again if asked again: the team
        decides (for example after adding a level)."""
        self.ensure_one()
        self._ems_check_manager()
        if self.state != 'published' or self.date_close <= self._ems_now():
            raise UserError(_("Only a published call that has not closed yet can be announced."))
        count = self._ems_announce(self._ems_eligible_partners(), 'ems.email_template_erasmus_call_open')
        self.sudo().write({'announce_date': self._ems_now(), 'announce_count': count})
        self.sudo().chatter(_("Notice of the open call emailed to %(count)s people.", count=count))

    @api.model
    def _cron_remind_closing(self):
        """The reminder before the closing date, once per call: on the first run from `reminder_days`
        days before the closing day on, to whoever can apply and has not submitted an application
        (a draft counts as not submitted). Only for a call whose notice was sent, so that a call
        announced some other way never emails anybody on its own. Hourly, from 9:00 in the centre:
        never a mass email at night."""
        local_now = self.env['ems.datetime_utils'].get_local_datetime()
        if local_now.hour < REMINDER_HOUR:
            return
        today = local_now.date()
        calls = self.search([('state', '=', 'published'), ('announce_date', '!=', False),
                             ('reminder_date', '=', False), ('reminder_days', '>', 0)])
        for call in calls.filtered('is_accepting'):
            if today < call._ems_local_date(call.date_close) - timedelta(days=call.reminder_days):
                continue
            submitted = call.application_ids.filtered(lambda application: application.state != 'draft').partner_id
            count = call._ems_announce(call._ems_eligible_partners() - submitted,
                                       'ems.email_template_erasmus_call_reminder')
            call.write({'reminder_date': call._ems_now(), 'reminder_count': count})
            call.chatter(_("Reminder before the closing date emailed to %(count)s people.", count=count))

    def _ems_announce(self, partners, xmlid):
        """Email the template `xmlid` (rendered on the call) to each of `partners` with an address:
        one email each, so nobody sees the others' addresses, rendered once per language. Returns
        how many were emailed."""
        self.ensure_one()
        template = self.env.ref(xmlid).sudo()
        partners = partners.filtered('email')
        Mail = self.env['mail.mail'].sudo()
        for lang, recipients in partners.grouped('lang').items():
            first = Mail.browse(template.with_context(lang=lang).send_mail(
                self.id, email_values={'email_to': recipients[0].email}))
            values = {name: first[name] for name in ('subject', 'body_html', 'email_from', 'reply_to', 'auto_delete',
                                                      'model', 'res_id')}
            Mail.create([{**values, 'email_to': partner.email} for partner in recipients[1:]])
        return len(partners)

    def _ems_eligible_partners(self):
        """Whoever can apply to the call, by the portal's rule (res.partner._ems_erasmus_calls): the
        students of its modalities' levels (conduct warnings rule nobody out: art. 6, the team may
        exclude an application, application.conduct_review), or the internal
        users of the teachers of its levels and of the Direction that validates the activities
        (_ems_staff_can_apply). A few queries for the whole centre, never one per person."""
        self.ensure_one()
        if self.audience == 'staff':
            teachers = self.env['hr.employee'].sudo().search([
                ('employee_type', '=', 'teacher'), ('teaching_ids.group_id.level_id', 'in', self.staff_level_ids.ids)])
            return (teachers.user_id | self.validator_ids).filtered(lambda user: not user.share).partner_id
        students = self.env['res.partner'].sudo().search([
            ('contact_type', '=', 'student'), ('main_group_id.level_id', 'in', self.modality_ids.level_ids.ids)])
        return students

    def _ems_local_date(self, value):
        """The day a stored (UTC) datetime falls on in the centre."""
        return self.env['ems.datetime_utils'].utc_datetime_to_local(value.replace(tzinfo=UTC)).date()

    def action_schedule_interviews(self):
        """The issue-#682 review: many interviews at once, in consecutive slots."""
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('ems.action_erasmus_interview_schedule')
        action['context'] = {'default_call_id': self.id}
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
                # In each member's language: an offer expired by the cron runs as the system user.
                call.activity_schedule(
                    activity_type_id=activity_type.id, user_id=user.id,
                    summary=call.with_context(lang=user.lang or self.env.lang)._ems_free_place_summary(names))

    def _ems_free_place_summary(self, names):
        return _("Erasmus+: a place is free in %s: offer it to the next reserve", ", ".join(names))

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

    def _ems_call_action(self, xmlid, call_field='call_id'):
        """An Erasmus+ list action narrowed to this call: the call's form opens each step of its
        process (the issue-#682 review), instead of a menu entry per step."""
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(xmlid)
        action['domain'] = [(call_field, '=', self.id)]
        return action

    def action_view_mobilities(self):
        return self._ems_call_action('ems.action_erasmus_mobility')

    def action_view_applications(self):
        action = self._ems_call_action('ems.action_erasmus_application')
        action['context'] = {'default_call_id': self.id,
                             'group_by': ['modality_id'] if self.audience == 'student' else []}
        return action

    def action_view_interviews(self):
        return self._ems_call_action('ems.action_erasmus_interview', 'application_id.call_id')

    def action_view_plan_ratings(self):
        return self._ems_call_action('ems.action_erasmus_plan_rating', 'application_id.call_id')

    def action_view_claims(self):
        return self._ems_call_action('ems.action_erasmus_claim')

    def action_view_resolutions(self):
        action = self._ems_call_action('ems.action_erasmus_resolution')
        action['context'] = {'default_call_id': self.id}
        return action

    def action_view_offers(self):
        return self._ems_call_action('ems.action_erasmus_offer')

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
        start = self._ems_course_start(course)
        if not start or partner.contact_type != 'student':
            return 0
        return self.env['ems.strike'].sudo().search_count([('student_id', '=', partner.id), ('date', '>=', start)])

    @api.model
    def _ems_course_start(self, course):
        """The first moment of `course` (empty: the current one) in the centre, as Odoo stores it."""
        course = course or self.env.company.current_course_id
        if not course:
            return False
        utils = self.env['ems.datetime_utils']
        first_day = datetime.combine(course.date_range()[0], time.min, tzinfo=utils.current_tz())
        return utils.datetime_to_odoo(first_day.astimezone(UTC))

    @api.model
    def _ems_conduct_blocked_count(self, count):
        """As many conduct warnings this course as the number that sends the case to the
        coexistence team (res.company.strike_escalation_threshold), or more: a serious conduct
        record. It only warns the team, who may exclude the application (art. 6). No threshold, no
        rule."""
        threshold = self.env.company.strike_escalation_threshold
        return threshold > 0 and count >= threshold

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

    def _ems_offer_destinations(self):
        """The destinations of the modality shown with a place offer (portal and emails), so the
        student knows what they may choose before accepting. Not personal data: read as sudo, as
        the offer is rendered for the student or by the queue."""
        self.ensure_one()
        return self.sudo().call_id.destination_ids.filtered(lambda destination: destination.modality_id == self)


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
        ('curricular', "Required for curricular work placement"), ('short_blended', "Short blended mobilities only"),
        ('fewer_opportunities', "Required if fewer opportunities are declared")],
        help="Required for curricular work placement: when the student's stay is a work placement managed in sBID "
             "(the mobility's Placement type); optional for an extracurricular stay or a recent graduate. Short "
             "blended mobilities only: asked for in a KA131-HED stay of 30 days or fewer, and not shown otherwise. "
             "Required if fewer opportunities are declared: the portal shows it only once the student ticks that "
             "they can prove a situation of fewer opportunities.")
    # The 2026-11-03 review: what the applicant hands in, and a link for its instructions.
    upload_kind = fields.Selection(string="Handed in as", required=True, default='file', selection=[
        ('file', "Files"), ('pdf', "PDF only"), ('link', "A link (e.g. a video on Google Drive)")],
        help="A link: the applicant pastes it on the portal instead of uploading a file.")
    help_url = fields.Char(string="Instructions link",
                           help="Shown with the instructions, e.g. the Europass CV editor.")
    # The 2026-11-04 usage test: uploading a CV twice showed two files with the same name, and
    # nobody knew which one counted. A document handed in as one file counts its newest upload; the
    # earlier ones stay, shown as earlier versions. Some take several (one certificate per language).
    single_file = fields.Boolean(string="One file", default=True,
                                 help="Only the newest file counts: the earlier ones stay as earlier versions and the "
                                      "receipt lists only the newest. Untick it for a document with several files, "
                                      "e.g. one certificate per language.")
    # The 2026-11-04 usage test: a model to download (e.g. the family authorisation of a minor),
    # instead of every family writing its own.
    template_file = fields.Binary(string="Model to download", attachment=True,
                                  help="The applicant downloads it from the portal, fills it in and hands it in.")
    template_filename = fields.Char(string="Model file name")
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


class EmsErasmusCallAnnounce(models.TransientModel):
    """The notice of the open call (the issue-#682 review): how many people get it, and when it
    was last sent, before the Erasmus team confirms."""
    _name = 'ems.erasmus.call.announce'
    _description = 'Erasmus+ notice of an open call'

    call_id = fields.Many2one(string="Call", comodel_name='ems.erasmus.call', required=True, ondelete='cascade')
    audience = fields.Selection(string="Applicants", related='call_id.audience')
    recipient_count = fields.Integer(string="People who can apply", compute='_compute_recipients')
    without_email_count = fields.Integer(string="Without an email address", compute='_compute_recipients')
    announce_date = fields.Datetime(string="Notice sent on", related='call_id.announce_date')
    announce_count = fields.Integer(string="Notice sent to", related='call_id.announce_count')
    reminder_days = fields.Integer(string="Reminder (days before closing)", related='call_id.reminder_days')

    @api.depends('call_id')
    def _compute_recipients(self):
        for wizard in self:
            partners = wizard.call_id._ems_eligible_partners() if wizard.call_id else self.env['res.partner']
            wizard.recipient_count = len(partners)
            wizard.without_email_count = len(partners.filtered(lambda partner: not partner.email))

    def action_send(self):
        self.ensure_one()
        self.call_id._ems_send_announce()
        return {'type': 'ir.actions.act_window_close'}
