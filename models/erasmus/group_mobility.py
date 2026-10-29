# -*- coding: utf-8 -*-

import secrets
from datetime import timedelta

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools import format_date
from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG

from .resolution import mask_document_id
from .workflow import check_kept, check_workflow_create, check_workflow_write

STATES = [('draft', "Draft"), ('enrolment', "Enrolment"), ('selection', "Selection"),
          ('validation', "Waiting for validation"), ('preparation', "Preparation"), ('stay', "During the stay"),
          ('return', "On return"), ('done', "Closed"), ('cancelled', "Cancelled")]
# States once the selection is approved: the participants' files are open.
FILE_STATES = ('preparation', 'stay', 'return')
RESULTS = [('selected', "Selected"), ('reserve', "Reserve"), ('excluded', "Excluded"), ('renounced', "Renounced")]
EXCLUSIONS = [('group', "Not in the eligible group"), ('conduct', "Too many conduct warnings this course")]
# What the Erasmus team enters for a student with no grades in EMS (issue #702).
GRADE_FIELDS = ('grade_manual', 'grade_average_manual', 'grade_manual_reason')
ROLES = [('student', "Student"), ('leader', "Leader teacher"), ('companion', "Accompanying teacher")]
# Who a group mobility's document is for.
GROUP_AUDIENCES = [('collective', "The group (shared)"), ('student', "Each student"),
                   ('teacher', "Each accompanying teacher"), ('participant', "Every participant")]
# A required document still to hand in (or to correct): it counts as missing on the overviews.
MISSING_STATES = ('missing', 'needs_change')
# The leader's answer on return: did the group learning programme go as planned?
PROGRAMME_EXECUTION = [('as_planned', "Yes, as planned"), ('changed', "No, with changes")]
LOG_KINDS = [('attendance', "Attendance"), ('incident', "Incident"), ('change', "Change"),
             ('evidence', "Evidence"), ('communication', "Communication")]
# What the leader teacher may change on their mobility, and the accompanying teacher; the rest is
# the Erasmus team's. The follow-up and the shared documents are edited from the mobility's form:
# their own record rules decide which lines each one may change.
# What the commitment letter states: changing it once a letter is accepted asks for a new acceptance.
COMMITMENT_TERMS = ('city', 'country_id', 'host_partner_id', 'date_start', 'date_end', 'travel_date_out',
                    'travel_date_back', 'leader_id', 'companion_ids', 'commitment_extra')
COMPANION_FIELDS = {'log_ids'}
LEADER_FIELDS = COMPANION_FIELDS | {'programme', 'leader_notes', 'eu_survey_attachment_ids', 'closure_note',
                                    'proposal_note', 'document_ids', 'programme_execution', 'programme_changes'}


class EmsErasmusGroupMobility(models.Model):
    """Issue #701 - a group mobility of students (KA121-VET): a group of a real EMS group (or
    several, e.g. the morning ones) that leaves together with its accompanying teachers, one of
    them the leader. The students enrol from the portal with one click; EMS ranks them when the
    enrolment closes (issue #702) and, once the coordinator approves the selection, each
    participant gets a file on the Erasmus+ document engine (issue #703). See
    docs/en/developers/erasmus/group_mobility.md."""
    _name = 'ems.erasmus.group.mobility'
    _description = 'Erasmus+ group mobility'
    _inherit = ['ems.base', 'ems.erasmus.eu.survey']
    _order = 'date_start_planned desc, id desc'

    name = fields.Char(string="Name", required=True, tracking=True)
    course_id = fields.Many2one(string="Course", comodel_name='ems.course', ondelete='restrict', tracking=True,
                                default=lambda self: self.env.company.current_course_id)
    project_id = fields.Many2one(string="Project", comodel_name='ems.erasmus.project', required=True, tracking=True,
                                 ondelete='restrict', domain=[('kind', '=', 'ka121_vet')],
                                 help="The KA121-VET project the mobility is charged to.")
    state = fields.Selection(string="State", selection=STATES, required=True, default='draft', tracking=True,
                             readonly=True, copy=False, index=True)
    shift = fields.Selection(string="Shift", selection=[('morning', "Morning"), ('afternoon', "Afternoon")],
                             help="Only to find the groups: the eligible groups are what counts.")
    group_ids = fields.Many2many(string="Eligible groups", comodel_name='ems.group', tracking=True,
                                 relation='ems_erasmus_group_mobility_group_rel',
                                 help="The students whose main group is one of these can enrol.")
    student_places = fields.Integer(string="Student places", default=8, tracking=True)
    teacher_places = fields.Integer(string="Accompanying teachers", default=2, tracking=True,
                                    help="How many teachers go with the group, the leader included.")
    leader_id = fields.Many2one(string="Leader teacher", comodel_name='hr.employee', tracking=True,
                                ondelete='restrict',
                                help="Prepares the selection, follows up the group and answers the EU Survey.")
    companion_ids = fields.Many2many(string="Other accompanying teachers", comodel_name='hr.employee',
                                     relation='ems_erasmus_group_mobility_companion_rel')
    enrolment_open = fields.Datetime(string="Enrolment opens", tracking=True)
    enrolment_close = fields.Datetime(string="Enrolment closes", tracking=True)
    description = fields.Html(string="Information for students", help="Shown on the portal, with the enrolment.")
    tie_break = fields.Text(
        string="Selection criteria", tracking=True,
        default=lambda self: _(
            "Enrolled within the period, in the eligible group and with fewer conduct warnings this course than the "
            "number that rules a student out. Ordered by the record average, from highest to lowest. Tie-break: the "
            "fewer opportunities accredited by the Erasmus team. If the tie persists, it is resolved by a draw."),
        help="Published on the portal before the enrolment opens. EMS ranks by the record average, then the fewer "
             "opportunities accredited, then the draw the Erasmus coordinator runs in EMS for a remaining tie.")
    # Destination, host entity and dates: may be pending during the enrolment.
    country_id = fields.Many2one(string="Country", comodel_name='res.country', tracking=True)
    city = fields.Char(string="City", tracking=True)
    host_partner_id = fields.Many2one(string="Host entity", comodel_name='res.partner', tracking=True,
                                      domain="[('is_erasmus_host', '=', True)]")
    host_contact_id = fields.Many2one(string="Host contact person", comodel_name='res.partner',
                                      domain="[('parent_id', '=', host_partner_id)]")
    date_start_planned = fields.Date(string="Planned start", tracking=True)
    date_end_planned = fields.Date(string="Planned end", tracking=True)
    date_start = fields.Date(string="Start", tracking=True, help="The final dates of the stay.")
    date_end = fields.Date(string="End", tracking=True)
    travel_date_out = fields.Date(string="Outbound travel", tracking=True)
    travel_date_back = fields.Date(string="Return travel", tracking=True)
    programme = fields.Html(string="Activity programme", help="The group's programme and calendar.")
    leader_notes = fields.Text(string="Leader's notes")
    programme_execution = fields.Selection(
        string="Programme carried out as planned?", selection=PROGRAMME_EXECUTION, tracking=True, copy=False,
        help="The leader answers it on return. The executed group learning agreement, signed by both centres, "
             "states the real dates, activities and participants.")
    programme_changes = fields.Text(string="What changed in the programme", tracking=True, copy=False)
    commitment_extra = fields.Html(
        string="Additional conditions",
        help="Added to the common commitment letter of this mobility, which each student (and the family of a minor) "
             "accepts on the portal. A letter already accepted keeps the text it was accepted with.")
    cancel_reason = fields.Text(string="Reason for cancelling", tracking=True)

    registration_ids = fields.One2many(string="Enrolments", comodel_name='ems.erasmus.group.registration',
                                       inverse_name='group_mobility_id')
    participant_ids = fields.One2many(string="Participants", comodel_name='ems.erasmus.group.participant',
                                      inverse_name='group_mobility_id')
    requirement_ids = fields.One2many(string="Documents asked for", comodel_name='ems.erasmus.call.document',
                                      inverse_name='group_mobility_id', copy=True)
    document_ids = fields.One2many(string="Shared documents", comodel_name='ems.erasmus.application.document',
                                   inverse_name='group_mobility_id', domain=[('group_participant_id', '=', False)])
    log_ids = fields.One2many(string="Follow-up", comodel_name='ems.erasmus.group.log',
                              inverse_name='group_mobility_id')
    invoice_ids = fields.One2many(string="Collective expenses", comodel_name='ems.erasmus.invoice',
                                  inverse_name='group_mobility_id')

    # The selection, kept as evidence (issue #702).
    ranking_date = fields.Datetime(string="Ranked on", readonly=True, copy=False,
                                   help="When the enrolment closed and EMS froze the data of the ranking.")
    proposal_date = fields.Datetime(string="Proposal sent on", readonly=True, copy=False)
    proposal_user_id = fields.Many2one(string="Proposal sent by", comodel_name='res.users', readonly=True, copy=False)
    proposal_note = fields.Text(string="Leader's comment on the proposal", copy=False)
    return_note = fields.Text(string="Why the proposal was sent back", copy=False, tracking=True)
    claims_deadline = fields.Datetime(string="Claims deadline", tracking=True, copy=False,
                                      help="Until when the students can claim against the provisional list, by "
                                           "replying to its email.")
    resolution_ids = fields.One2many(string="Published lists", comodel_name='ems.erasmus.resolution',
                                     inverse_name='group_mobility_id', readonly=True)
    provisional_published = fields.Boolean(string="Provisional list published",
                                           compute='_compute_provisional_published')
    approval_date = fields.Datetime(string="Selection approved on", readonly=True, copy=False)
    approval_user_id = fields.Many2one(string="Selection approved by", comodel_name='res.users', readonly=True,
                                       copy=False)
    destination_date = fields.Date(string="Files opened on", readonly=True, copy=False,
                                   help="When the selection was approved: the documents' deadlines count from it.")

    # EU Survey and closure (issue #704).
    eu_survey_user_id = fields.Many2one(string="Answers the EU Survey", comodel_name='res.users', tracking=True,
                                        domain=[('share', '=', False)],
                                        help="Empty: the leader teacher.")
    eu_survey_attachment_ids = fields.Many2many(string="EU Survey evidence", comodel_name='ir.attachment',
                                                relation='ems_erasmus_group_mobility_survey_attachment_rel')
    closure_proposed_date = fields.Datetime(string="Closure proposed on", readonly=True, copy=False)
    closure_note = fields.Text(string="Closure notes", copy=False)

    # Overview (issue #704).
    registration_count = fields.Integer(string="Enrolled", compute='_compute_counts')
    selected_count = fields.Integer(string="Selected students", compute='_compute_counts')
    reserve_count = fields.Integer(string="Reserves", compute='_compute_counts')
    documents_missing = fields.Integer(string="Documents missing", compute='_compute_counts',
                                       help="Required documents with no file, or needing changes.")
    documents_to_review = fields.Integer(string="Documents to review", compute='_compute_counts')
    is_enrolling = fields.Boolean(string="Accepting enrolments", compute='_compute_is_enrolling')
    needs_draw = fields.Boolean(string="Tie to resolve", compute='_compute_counts')
    grade_incidents = fields.Integer(string="Students with no grades", compute='_compute_counts',
                                     help="Eligible enrolments with no evaluated module: the Erasmus team resolves "
                                          "each one before the ranking can be closed.")
    commitments_pending = fields.Integer(string="Commitment letters pending", compute='_compute_counts',
                                         help="Selected students whose letter is not accepted yet, by them or, for a "
                                              "minor, by their family.")
    draw_ids = fields.One2many(string="Draws", comodel_name='ems.erasmus.group.draw',
                               inverse_name='group_mobility_id', readonly=True)
    next_reserve = fields.Char(string="Next reserve", compute='_compute_counts',
                               help="With a place free, the best-ranked reserve without a substitution proposed.")
    user_role = fields.Selection(string="Your role", selection=[('team', "Erasmus team"), *ROLES[1:]],
                                 compute='_compute_user_role')
    currency_id = fields.Many2one(string="Currency", comodel_name='res.currency', compute='_compute_currency_id')
    expense_amount = fields.Monetary(string="Total of the collective expenses", compute='_compute_expense_amount')

    @api.depends('registration_ids.state', 'registration_ids.result', 'registration_ids.proposed_result',
                 'registration_ids.needs_draw', 'registration_ids.grade_incident',
                 'registration_ids.substitution_state', 'participant_ids.state',
                 'participant_ids.commitment_pending', 'participant_ids.commitment_guardian_pending',
                 'participant_ids.document_ids.file_state', 'document_ids.file_state', 'student_places')
    def _compute_counts(self):
        """Counted as the Erasmus team: an accompanying teacher sees the figures, never the
        enrolments themselves."""
        for mobility in self:
            role = mobility._ems_role()
            mobility = mobility.sudo()
            registrations = mobility.registration_ids.filtered(lambda registration: registration.state == 'enrolled')
            results = registrations.mapped(lambda registration: registration.result or registration.proposed_result)
            mobility.registration_count = len(registrations)
            mobility.selected_count = results.count('selected')
            mobility.reserve_count = results.count('reserve')
            mobility.needs_draw = any(registrations.mapped('needs_draw'))
            mobility.grade_incidents = len(registrations.filtered('grade_incident'))
            mobility.commitments_pending = len(mobility.participant_ids.filtered(
                lambda participant: participant.state == 'active' and participant.role == 'student'
                and (participant.commitment_pending or participant.commitment_guardian_pending)))
            lines = mobility.document_ids | mobility.participant_ids.filtered(
                lambda participant: participant.state == 'active').document_ids
            mobility.documents_missing = len(lines.filtered(lambda line: line.file_state in MISSING_STATES))
            mobility.documents_to_review = len(lines.filtered(lambda line: line.file_state == 'to_review'))
            mobility.next_reserve = role in ('team', 'leader') and mobility._ems_next_reserve().partner_id.name

    @api.depends('resolution_ids.kind', 'resolution_ids.state')
    def _compute_provisional_published(self):
        for mobility in self:
            mobility.provisional_published = bool(mobility.sudo()._ems_published_list('provisional'))

    @api.depends('state', 'enrolment_open', 'enrolment_close')
    def _compute_is_enrolling(self):
        now = self.env['ems.erasmus.call']._ems_now()
        for mobility in self:
            mobility.is_enrolling = mobility.state == 'enrolment' and bool(
                mobility.enrolment_open and mobility.enrolment_close
                and mobility.enrolment_open <= now < mobility.enrolment_close)

    @api.depends_context('uid')
    @api.depends('leader_id', 'companion_ids')
    def _compute_user_role(self):
        for mobility in self:
            mobility.user_role = mobility._ems_role()

    def _compute_currency_id(self):
        self.currency_id = self.env.company.currency_id

    @api.depends('invoice_ids.amount')
    def _compute_expense_amount(self):
        for mobility in self:
            mobility.expense_amount = sum(mobility.invoice_ids.mapped('amount'))

    @api.constrains('student_places', 'teacher_places')
    def _check_places(self):
        for mobility in self:
            if mobility.student_places < 1 or mobility.teacher_places < 1:
                raise ValidationError(_("A group mobility has at least one student place and one teacher."))

    @api.constrains('project_id')
    def _check_project(self):
        for mobility in self:
            if mobility.project_id.kind != 'ka121_vet':
                raise ValidationError(_("A group mobility of students goes on a KA121-VET project."))

    @api.constrains('leader_id', 'companion_ids', 'teacher_places')
    def _check_teachers(self):
        for mobility in self:
            if mobility.leader_id in mobility.companion_ids:
                raise ValidationError(_("The leader teacher is not one of the other accompanying teachers too."))
            if len(mobility.leader_id | mobility.companion_ids) > mobility.teacher_places:
                raise ValidationError(_("%(name)s has places for %(count)s accompanying teachers.",
                                        name=mobility.name, count=mobility.teacher_places))

    @api.constrains('enrolment_open', 'enrolment_close', 'date_start', 'date_end', 'date_start_planned',
                    'date_end_planned')
    def _check_dates(self):
        for mobility in self:
            for start, end in (('enrolment_open', 'enrolment_close'), ('date_start', 'date_end'),
                               ('date_start_planned', 'date_end_planned')):
                if mobility[start] and mobility[end] and mobility[end] < mobility[start]:
                    raise ValidationError(_("An end date cannot be before its start."))

    @api.onchange('host_partner_id')
    def _onchange_host_partner_id(self):
        if self.host_contact_id.parent_id != self.host_partner_id:
            self.host_contact_id = self.env['ems.erasmus.mobility']._ems_single_contact(self.host_partner_id)

    @api.model_create_multi
    def create(self, vals_list):
        """A new group mobility asks for the documents of a KA121-VET group mobility by default."""
        check_workflow_create(self, vals_list)
        for vals in vals_list:
            if 'requirement_ids' not in vals:
                vals['requirement_ids'] = self._ems_default_requirements()
        mobilities = super().create(vals_list)
        mobilities._ems_sync_teachers()
        return mobilities

    def write(self, vals):
        check_workflow_write(self, vals)
        if not self.env.su:
            for mobility in self:
                role = mobility._ems_role()
                allowed = LEADER_FIELDS if role == 'leader' else COMPANION_FIELDS if role == 'companion' else set()
                if role != 'team' and set(vals) - allowed:
                    raise AccessError(_("Only the Erasmus team changes this of a group mobility."))
        terms = {mobility: mobility._ems_commitment_terms() for mobility in self} \
            if set(COMMITMENT_TERMS) & set(vals) else {}
        provisional = {participant.id: participant.commitment_provisional
                       for participant in self.sudo().participant_ids} if terms else {}
        result = super().write(vals)
        if {'leader_id', 'companion_ids'} & set(vals):
            self._ems_sync_teachers()
        for mobility, before in terms.items():
            if mobility._ems_commitment_terms() != before:
                mobility.sudo().participant_ids._ems_commitment_supersede(
                    _("destination, dates, teachers or additional conditions"), provisional)
        return result

    def unlink(self):
        """Once anyone enrolled, signed or uploaded a file, the group mobility is evidence: its
        draws, enrolments and records would go in cascade, skipping the draws' own guard. It is
        cancelled instead."""
        check_kept(self, self.filtered(lambda mobility: mobility._ems_has_evidence()))
        return super().unlink()

    def _ems_has_evidence(self):
        self.ensure_one()
        mobility = self.sudo().with_context(active_test=False)
        return bool(mobility.draw_ids or mobility.registration_ids or mobility.log_ids
                    or mobility.eu_survey_attachment_ids or mobility.document_ids._ems_evidence()
                    or mobility.participant_ids.filtered(lambda participant: participant._ems_has_evidence()))

    def _ems_commitment_terms(self):
        """What the students' commitment letter states about this mobility."""
        self.ensure_one()
        mobility = self.sudo()
        return tuple(mobility[name].ids if name.endswith('_ids') or name.endswith('_id') else mobility[name]
                     for name in COMMITMENT_TERMS)

    # --- roles -----------------------------------------------------------------------------------

    def _ems_role(self):
        """The logged-in user's role in this mobility: the Erasmus team (and the administrator),
        its leader teacher, an accompanying teacher, or none."""
        self.ensure_one()
        user = self.env.user
        if self.env.su or self.env['ems.erasmus.application']._ems_can_manage():
            return 'team'
        mobility = self.sudo()
        if mobility.leader_id.user_id == user:
            return 'leader'
        if user in mobility.companion_ids.user_id:
            return 'companion'
        return False

    def _ems_check_role(self, *roles):
        for mobility in self:
            if mobility._ems_role() not in roles:
                raise AccessError(_("You cannot do this in the group mobility %s.", mobility.name))

    def _ems_check_coordinator(self):
        user = self.env.user
        if not (self.env.su or user.has_group('ems.group_erasmus_coordinator')
                or user.has_group('ems.group_academic_admin')):
            raise AccessError(_("Only the Erasmus coordinator approves a selection."))

    def _ems_check_state(self, *states):
        for mobility in self:
            if mobility.state not in states:
                raise UserError(_("The group mobility %s is not in the right state for this.", mobility.name))

    def _ems_set_state(self, state, **vals):
        self.sudo().write({'state': state, **vals})

    def _ems_sync_teachers(self):
        """One participant per accompanying teacher, the leader marked as such; a teacher removed
        keeps their file, withdrawn. The hidden group that opens *Erasmus+ > My group mobilities*
        follows."""
        Participant = self.env['ems.erasmus.group.participant'].sudo()
        users = self.env['res.users']
        for mobility in self.sudo():
            teachers = mobility.participant_ids.filtered(lambda participant: participant.role != 'student')
            users |= teachers.employee_id.user_id
            wanted = {mobility.leader_id: 'leader', **{employee: 'companion' for employee in mobility.companion_ids}}
            wanted.pop(self.env['hr.employee'], None)
            for employee, role in wanted.items():
                participant = teachers.filtered(lambda participant: participant.employee_id == employee)
                vals = {'role': role, 'state': 'active'}
                if participant:
                    participant.write(vals)
                else:
                    participant = Participant.create({
                        'group_mobility_id': mobility.id, 'employee_id': employee.id,
                        'partner_id': (employee.user_id.partner_id or employee.work_contact_id).id, **vals})
                if mobility.state in FILE_STATES:
                    participant._ems_sync_documents()
                users |= employee.user_id
            teachers.filtered(lambda participant: participant.employee_id not in wanted).write(
                {'state': 'withdrawn'})
        users._ems_sync_erasmus_group_teacher_group()

    def _ems_team_users(self):
        return self.env['ems.erasmus.call']._ems_erasmus_team()

    def _ems_coordinators(self):
        users = self.env.ref('ems.group_erasmus_coordinator').sudo().users.filtered(lambda user: not user.share)
        return users - self.env.ref('base.user_root') or self._ems_team_users()

    def _ems_activities_done(self):
        self.sudo().activity_ids.action_feedback()

    # --- enrolment (issue #701) ------------------------------------------------------------------

    def _ems_is_eligible(self, partner):
        """A student of one of the eligible groups."""
        self.ensure_one()
        return partner.contact_type == 'student' and partner.main_group_id in self.sudo().group_ids

    def _ems_conduct_blocked(self, partner):
        """Same rule as the internship call (art. 6): as many conduct warnings this course as the
        number that sends the case to the coexistence team, or more."""
        Call = self.env['ems.erasmus.call']
        return Call._ems_conduct_blocked_count(Call._ems_partner_course_strike_count(partner, self.sudo().course_id))

    def action_open_enrolment(self):
        self._ems_check_role('team')
        self._ems_check_state('draft')
        for mobility in self:
            if not (mobility.group_ids and mobility.enrolment_open and mobility.enrolment_close):
                raise UserError(_("Say the eligible groups and the enrolment period of %s first.", mobility.name))
            if not (mobility.tie_break or '').strip():
                raise UserError(_("Publish the selection criteria before opening the enrolment."))
        self._ems_set_state('enrolment')

    def action_back_to_draft(self):
        self._ems_check_role('team')
        self._ems_check_state('enrolment')
        for mobility in self:
            if mobility.registration_ids:
                raise UserError(_("%s already has enrolments: it cannot go back to draft.", mobility.name))
        self._ems_set_state('draft')

    def action_close_enrolment(self):
        """Close the enrolment now (EMS does it by itself when the period ends)."""
        self._ems_check_role('team')
        self._ems_check_state('enrolment')
        self._ems_close_enrolment()

    @api.model
    def _cron_close_enrolments(self):
        self.sudo().search([('state', '=', 'enrolment'), ('enrolment_close', '<=', self.env[
            'ems.erasmus.call']._ems_now())])._ems_close_enrolment()

    def _ems_close_enrolment(self):
        """Freeze what the selection is based on (issue #702) and rank: the leader prepares the
        proposal from here."""
        for mobility in self.sudo():
            mobility.registration_ids.filtered(lambda registration: registration.state == 'enrolled')._ems_freeze()
            mobility._ems_set_state('selection', ranking_date=fields.Datetime.now())
            mobility._ems_rank()
            mobility.chatter(_("Enrolment closed: %s students enrolled, ranking calculated.",
                               mobility.registration_count))
            leader = mobility.leader_id.user_id or mobility._ems_team_users()
            mobility._ems_schedule(leader, _("Erasmus+: review the selection of %s", mobility.name))

    # --- ranking and selection (issue #702) ------------------------------------------------------

    def _ems_rank(self):
        """The rank of the eligible enrolments: record average descending, then the fewer
        opportunities accredited, then the draw order the coordination sets for a tie it resolves.
        The first ones, as many as places, are proposed as selected; the rest, as reserves in that
        order. Not eligible: excluded. An eligible student with no average (no evaluated module and
        none entered by the Erasmus team) is not ranked: never as a 0, it is an incident to resolve.
        A tie is resolved once every one in it has a different draw position: someone joining an
        already drawn tie (a later accreditation, an average entered) reopens it for a new draw.
        Only before the selection is approved: then it is frozen."""
        for mobility in self.sudo():
            if mobility.state not in ('selection', 'validation'):
                continue
            enrolled = mobility.registration_ids.filtered(lambda registration: registration.state == 'enrolled')
            eligible = enrolled.filtered('eligible')
            ranked = eligible.filtered('has_average').sorted(lambda registration: registration._ems_rank_key())
            ties = ranked.grouped(lambda registration: registration._ems_tie_key())
            for registration in enrolled - eligible:
                registration._ems_write({'rank': 0, 'needs_draw': False, 'proposed_result': 'excluded'})
            for registration in eligible - ranked:
                registration._ems_write({'rank': 0, 'needs_draw': False, 'proposed_result': False})
            for index, registration in enumerate(ranked):
                tie = ties[registration._ems_tie_key()]
                orders = tie.mapped('draw_order')
                registration._ems_write({
                    'rank': index + 1, 'needs_draw': len(tie) > 1 and (0 in orders or len(set(orders)) < len(tie)),
                    'proposed_result': 'selected' if index < mobility.student_places else 'reserve'})

    def _ems_check_selection_ready(self):
        """What has to be resolved before the leader sends the proposal and before the
        coordinator approves it."""
        for mobility in self:
            registrations = mobility.sudo().registration_ids.filtered(
                lambda registration: registration.state == 'enrolled')
            if registrations.filtered(lambda registration: registration.eligible and registration.fewer_opportunities
                                      and registration.fewer_opportunities_check == 'pending'):
                raise UserError(_("The Erasmus team still has to check a declared situation of fewer opportunities."))
            incidents = registrations.filtered('grade_incident')
            if incidents:
                raise UserError(_(
                    "These students have no evaluated module, so they have no record average: the Erasmus team "
                    "enters it by hand with the reason, or the coordinator excludes them with a reason. %s",
                    ", ".join(incidents.partner_id.mapped('name'))))
            if mobility.needs_draw:
                raise UserError(_("There is a tie the Erasmus coordination has to resolve first."))

    def action_submit_proposal(self):
        """The leader sends the proposal to the Erasmus coordinator: every tie resolved and every
        declared fewer-opportunities situation checked and every student with no grades resolved
        first."""
        self._ems_check_role('team', 'leader')
        self._ems_check_state('selection')
        self._ems_check_selection_ready()
        self._ems_activities_done()
        self._ems_set_state('validation', proposal_date=fields.Datetime.now(), proposal_user_id=self.env.uid,
                            return_note=False)
        for mobility in self:
            mobility._ems_schedule(mobility._ems_coordinators(),
                                   _("Erasmus+: validate the selection of %s", mobility.name))

    def action_draw_ties(self):
        """The Erasmus coordinator resolves the ties that remain after the record average and the
        fewer opportunities by a draw: EMS orders each tied set at random (a cryptographically
        secure generator) and keeps, as a record nobody can change (ems.erasmus.group.draw), who
        ran it, when, the exact set of students tied with what they were tied on, and the order
        drawn; also summed up in the chatter. Ties only: it never moves anyone else."""
        self._ems_check_coordinator()
        self._ems_check_state('selection', 'validation')
        for mobility in self.sudo():
            tied = mobility.registration_ids.filtered(lambda registration: registration.state == 'enrolled'
                                                      and registration.needs_draw)
            if not tied:
                raise UserError(_("There is no tie to draw in %s.", mobility.name))
            mobility.env['ems.erasmus.group.draw']._ems_run(mobility, [
                (registrations, {'grade_average': registrations[0]._ems_average(),
                                 'fewer_opportunities': registrations[0].fewer_opportunities_check == 'yes'})
                for registrations in tied.grouped(lambda registration: registration._ems_tie_key()).values()])
            mobility._ems_rank()

    def action_return_proposal(self):
        """The coordinator sends the proposal back to the leader, saying why."""
        self._ems_check_coordinator()
        self._ems_check_state('validation')
        for mobility in self:
            if not (mobility.return_note or '').strip():
                raise UserError(_("Write why the proposal goes back first."))
        self._ems_activities_done()
        self._ems_set_state('selection')
        for mobility in self:
            leader = mobility.leader_id.user_id or mobility._ems_team_users()
            mobility._ems_schedule(leader, _("Erasmus+: review the selection of %s again", mobility.name))

    def _ems_published_list(self, kind):
        self.ensure_one()
        return self.resolution_ids.filtered(lambda resolution: resolution.state == 'published'
                                            and resolution.kind == kind)

    def _ems_publish_list(self, kind):
        """Publish the provisional or the definitive list of admitted, excluded and reserves with the
        calls' resolutions (ems.erasmus.resolution): frozen lines, identity documents masked, a PDF
        for the project's dossier, approved by the coordinator."""
        self.ensure_one()
        resolution = self.env['ems.erasmus.resolution'].sudo().create({'group_mobility_id': self.id, 'kind': kind})
        resolution.action_prepare()
        resolution.action_publish()
        return resolution

    def action_publish_provisional(self):
        """The coordinator publishes the provisional list: each student gets their provisional
        result and can claim, by replying to the email, until the claims deadline."""
        self._ems_check_coordinator()
        self._ems_check_state('validation')
        self._ems_check_selection_ready()
        for mobility in self:
            if not (mobility.claims_deadline and mobility.claims_deadline > self.env['ems.erasmus.call']._ems_now()):
                raise UserError(_("Set a future claims deadline before publishing the provisional list."))
            mobility._ems_publish_list('provisional')
            mobility.sudo().chatter(_("Provisional list published."))

    def action_approve_selection(self):
        """The coordinator approves the selection once the provisional list is published: the
        results are frozen, the definitive list is published, each student gets their own result,
        and every participant's file opens."""
        self._ems_check_coordinator()
        self._ems_check_state('validation')
        self._ems_check_selection_ready()
        for mobility in self:
            if not mobility.sudo()._ems_published_list('provisional'):
                raise UserError(_("Publish the provisional list of %s first.", mobility.name))
        self._ems_activities_done()
        today = self.env['ems.datetime_utils'].get_local_today()
        for mobility in self.sudo():
            registrations = mobility.registration_ids.filtered(lambda registration: registration.state == 'enrolled')
            for registration in registrations:
                registration._ems_write({'result': registration.result_override or registration.proposed_result})
            selected = registrations.filtered(lambda registration: registration.result == 'selected')
            if len(selected) > mobility.student_places:
                raise UserError(_("%(name)s has %(count)s student places.", name=mobility.name,
                                  count=mobility.student_places))
            mobility._ems_set_state('preparation', approval_date=fields.Datetime.now(), approval_user_id=self.env.uid,
                                    destination_date=today)
            mobility._ems_publish_list('definitive')
            selected._ems_open_file()
            mobility.participant_ids.filtered(lambda participant: participant.role != 'student')._ems_sync_documents()
            mobility._ems_sync_collective_documents()
            registrations._ems_send_result()
            mobility.chatter(_("Selection approved and published: %s selected.", len(selected)))

    def _ems_next_reserve(self):
        """With a place free, the best-ranked reserve with no substitution proposed yet."""
        self.ensure_one()
        if self.state not in FILE_STATES:
            return self.env['ems.erasmus.group.registration']
        registrations = self.sudo().registration_ids
        taken = registrations.filtered(lambda registration: registration.result == 'selected'
                                       or registration.substitution_state == 'proposed')
        if len(taken) >= self.student_places:
            return self.env['ems.erasmus.group.registration']
        return registrations.filtered(lambda registration: registration.result == 'reserve' and registration.state ==
                                      'enrolled' and not registration.substitution_state).sorted('rank')[:1]

    def action_propose_substitution(self):
        """A selected student renounced: the leader proposes the next reserve to the coordinator."""
        self._ems_check_role('team', 'leader')
        self._ems_check_state(*FILE_STATES)
        for mobility in self:
            reserve = mobility._ems_next_reserve()
            if not reserve:
                raise UserError(_("There is no free place or no reserve left in %s.", mobility.name))
            vacancy = mobility.sudo().registration_ids.filtered(
                lambda registration: registration.result == 'renounced' and not registration.substitute_id)[:1]
            reserve._ems_write({'substitution_state': 'proposed', 'substitute_for_id': vacancy.id,
                                'substitution_proposed_by_id': self.env.uid,
                                'substitution_proposed_date': fields.Datetime.now()})
            mobility.sudo().chatter(_("Substitution proposed: %(reserve)s (reserve %(rank)s) for %(vacancy)s.",
                               reserve=reserve.partner_id.name, rank=reserve.reserve_position,
                               vacancy=vacancy.partner_id.name or _("a free place")))
            mobility._ems_activities_done()
            mobility._ems_schedule(mobility._ems_coordinators(),
                                   _("Erasmus+: validate the substitution in %s", mobility.name))

    # --- the files (issue #703) ------------------------------------------------------------------

    @api.model
    def _ems_default_requirements(self):
        """What a KA121-VET group mobility asks for by default (editable on each mobility). Every
        document is prepared outside EMS: EMS keeps the files, the signatures, the review and the
        record. The group learning agreement covers every student (no individual one) and lists the
        participants, in two versions signed by both centres: planned, before leaving, and executed,
        after the stay. Each participant: grant agreement and insurance (their own policy, or the
        group's collective one); students also the health card, the official authorisation for
        minors to travel abroad and, recommended, the Europass mobility document; teachers,
        optionally, the certificate of stay. The family's authorisation to take part is the
        commitment letter, accepted on the portal (ems.erasmus.commitment), and the image rights
        are the student's authorisation of the course (res.partner.auth_image): neither is a
        document."""
        team = {'handled_by': 'team'}
        both_centres = {'sign_coordinator': True, 'sign_host': True}
        documents = [
            {'group_audience': 'collective', 'name': _("Group learning agreement (planned)"), **team, **both_centres,
             'due_basis': 'before_start', 'description': _(
                 "The learning programme of the whole group agreed with the host entity before leaving: objectives, "
                 "learning outcomes, calendar, activities and the participants. One document shared by every "
                 "student.")},
            {'group_audience': 'collective', 'stage': 'return', 'name': _("Group learning agreement (executed)"),
             **team, **both_centres, 'description': _(
                 "The same programme, signed by both centres after the stay: the real start and end dates, the "
                 "activities carried out, the methodologies and the final list of participants (students and "
                 "accompanying teachers of every centre). If nothing changed, it ratifies the planned one with the "
                 "real dates and participants.")},
            {'group_audience': 'collective', 'name': _("Agreements with the host entity"), **team,
             'requirement': 'optional'},
            {'group_audience': 'collective', 'name': _("Group travel documents"), **team, 'requirement': 'optional',
             'file_category': '03_Durant_la_mobilitat'},
            {'group_audience': 'collective', 'name': _("Collective insurance policy"), **team,
             'requirement': 'insurance', 'due_basis': 'before_start', 'description': _(
                 "Only when one policy covers all or part of the participants: mark them as covered by the "
                 "collective policy, and their own policy is no longer asked for.")},
            {'group_audience': 'collective', 'name': _("Group inclusion documentation"), **team,
             'requirement': 'optional', 'confidential': True, 'file_category': '01_Dades_i_autoritzacions',
             'description': _(
                 "Evidence that participants belong to a category of fewer opportunities recognised by SEPIE and, "
                 "when there are real inclusion costs, why the support was needed. The invoices and payment proofs "
                 "go in the collective expenses. Only the Erasmus team sees it.")},
            {'group_audience': 'collective', 'stage': 'return', 'name': _("Green Travel: sworn statement and evidence"),
             **team, 'requirement': 'optional', 'sign_director': True, 'description': _(
                 "Only if Green Travel is declared: the sworn statement signed by the centre and the evidence of the "
                 "journey.")},
            {'group_audience': 'collective', 'stage': 'return', 'name': _("Common evidence of the stay"), **team,
             'requirement': 'optional', 'file_category': '03_Durant_la_mobilitat'},
            {'group_audience': 'participant', 'name': _("Grant agreement"), 'handled_by': 'team_to_sign',
             'sign_participant': True, 'sign_director': True, 'sign_guardian': True, 'due_basis': 'before_start',
             'description': _("The Erasmus team uploads it filled in: download it, sign it and upload it signed.")},
            {'group_audience': 'participant', 'name': _("Insurance policy"), **team, 'requirement': 'insurance',
             'due_basis': 'before_start', 'description': _(
                 "The Erasmus team uploads it for you to keep. Not asked for when the group's collective policy "
                 "covers you.")},
            # Health information: confidential, only the Erasmus team sees it (as in the calls).
            {'group_audience': 'student', 'name': _("European Health Insurance Card"),
             'file_category': '01_Dades_i_autoritzacions', 'confidential': True,
             'description': _("Both sides, valid for the whole stay.")},
            {'group_audience': 'student', 'name': _("Authorisation for minors to travel abroad"),
             'requirement': 'minor', 'file_category': '01_Dades_i_autoritzacions',
             'description': _("Processed with the Mossos d'Esquadra.")},
            {'group_audience': 'student', 'stage': 'return', 'name': _("Europass mobility document"), **team,
             'requirement': 'optional', 'sign_coordinator': True, 'description': _(
                 "Recommended, not required: it certifies what you learned during the stay. The Erasmus team "
                 "uploads it for you to download.")},
            {'group_audience': 'teacher', 'stage': 'return', 'name': _("Certificate of stay"), 'sign_host': True,
             'requirement': 'optional', 'description': _(
                 "Optional: the accompanying teachers are in the executed group learning agreement.")},
            {'group_audience': 'teacher', 'name': _("Travel and accommodation documents"), 'requirement': 'optional',
             'file_category': '03_Durant_la_mobilitat'},
        ]
        defaults = {'preparation': 'destination', 'return': 'after_end'}
        return [(0, 0, {'sequence': index, 'stage': vals.get('stage', 'preparation'), 'requirement': 'required',
                        'due_days': 30, 'due_basis': defaults[vals.get('stage', 'preparation')], **vals})
                for index, vals in enumerate(documents, 1)]

    def _ems_sync_collective_documents(self):
        """One shared line per collective document still missing. Never removes a line."""
        Line = self.env['ems.erasmus.application.document'].sudo()
        for mobility in self.sudo():
            documents = mobility.requirement_ids.filtered(lambda document: document.group_audience == 'collective')
            Line.create([{'group_mobility_id': mobility.id, 'call_document_id': document.id}
                         for document in documents - mobility.document_ids.call_document_id])

    def action_sync_requirements(self):
        """After changing the documents asked for."""
        self._ems_check_role('team')
        for mobility in self.filtered(lambda mobility: mobility.state in FILE_STATES):
            mobility._ems_sync_collective_documents()
            mobility.participant_ids.filtered(lambda participant: participant.state == 'active')._ems_sync_documents()

    # --- stay, EU Survey and closure (issue #704) ------------------------------------------------

    def action_start_stay(self):
        self._ems_check_role('team', 'leader')
        self._ems_check_state('preparation')
        self._ems_set_state('stay')

    def action_end_stay(self):
        """Back home: the return documents and the EU Survey, a task for whoever answers it."""
        self._ems_check_role('team', 'leader')
        self._ems_check_state('stay')
        today = self.env['ems.datetime_utils'].get_local_today()
        for mobility in self:
            deadline = mobility.eu_survey_deadline or today + timedelta(days=30)
            mobility._ems_set_state('return', eu_survey_deadline=deadline)
            mobility._ems_schedule(mobility._ems_eu_survey_user(), _("Erasmus+: answer the EU Survey of %s",
                                                                     mobility.name), deadline)
            mobility._ems_schedule(mobility.leader_id.user_id or mobility._ems_team_users(), _(
                "Erasmus+: say whether the programme of %s was carried out as planned", mobility.name))

    def _ems_check_programme_answered(self):
        """On return the leader says whether the programme went as planned, and what changed."""
        for mobility in self:
            if not mobility.programme_execution:
                raise UserError(_("Say first whether the programme of %s was carried out as planned.", mobility.name))
            if mobility.programme_execution == 'changed' and not (mobility.programme_changes or '').strip():
                raise UserError(_("Write what changed in the programme of %s.", mobility.name))

    def _ems_eu_survey_user(self):
        self.ensure_one()
        mobility = self.sudo()
        return mobility.eu_survey_user_id or mobility.leader_id.user_id or mobility._ems_team_users()

    def action_eu_survey_done(self):
        """Whoever answers the EU Survey says so (with evidence if any); the team validates it."""
        for mobility in self:
            if not (mobility._ems_role() in ('team', 'leader') or self.env.user == mobility._ems_eu_survey_user()):
                raise AccessError(_("Only who answers the EU Survey says it is done."))
        self._ems_check_state('return')
        self._ems_activities_done()
        self._ems_eu_survey_answered()

    def action_eu_survey_validate(self):
        self._ems_check_role('team')
        self._ems_eu_survey_validate()
        self._ems_activities_done()

    def action_propose_closure(self):
        """The leader says the group's part is over; the team closes the file."""
        self._ems_check_role('team', 'leader')
        self._ems_check_state('return')
        self._ems_check_programme_answered()
        self._ems_set_state('return', closure_proposed_date=fields.Datetime.now())
        for mobility in self:
            mobility.sudo().chatter(_("Closure proposed by the leader teacher."))
            mobility._ems_schedule(mobility._ems_team_users(), _("Erasmus+: close %s", mobility.name))

    def action_close(self):
        self._ems_check_role('team')
        self._ems_check_state('return')
        self._ems_check_programme_answered()
        for mobility in self:
            missing = (mobility.document_ids | mobility.participant_ids.filtered(
                lambda participant: participant.state == 'active').document_ids).filtered(
                lambda line: line.is_required and line.file_state != 'complete')
            if missing:
                raise UserError(_("Every required document must be complete first: %s",
                                  ", ".join(sorted(set(missing.mapped('name'))))))
            if mobility.eu_survey_state != 'validated':
                raise UserError(_("Validate the EU Survey first."))
        self._ems_activities_done()
        self._ems_set_state('done')

    def action_cancel(self):
        self._ems_check_role('team')
        for mobility in self:
            if mobility.state in ('done', 'cancelled'):
                raise UserError(_("%s is already closed.", mobility.name))
            if not (mobility.cancel_reason or '').strip():
                raise UserError(_("Write the reason for cancelling first."))
        self._ems_activities_done()
        self._ems_set_state('cancelled')

    def action_export_participants(self):
        """The participants' spreadsheet (the selected students and the accompanying teachers),
        served by EmsErasmusExportController in the same format as the calls' one."""
        self.ensure_one()
        participants = self._ems_export_participants()
        return {
            'type': 'ir.actions.act_url',
            'url': f"/ems/erasmus/group/participants?participant_ids={','.join(map(str, participants.ids))}",
            'target': 'download',
        }

    def _ems_export_participants(self):
        self._ems_check_role('team')
        participants = self.sudo().participant_ids.filtered(lambda participant: participant.state == 'active')
        if not participants:
            raise UserError(_("%s has no participants yet.", self.name))
        return participants

    def action_export_dossier(self):
        """The group mobility's documents as a ZIP (logged as an export): its common documents and
        every participant's record."""
        self.ensure_one()
        return self.env['ems.erasmus.export']._ems_open_wizard(group_mobility_id=self.id,
                                                               project_id=self.project_id.id)

    def action_view_participants(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('ems.action_erasmus_group_participant')
        action['domain'] = [('group_mobility_id', '=', self.id)]
        action['context'] = {'default_group_mobility_id': self.id}
        return action


class EmsErasmusGroupRegistration(models.Model):
    """Issue #701 - a student's enrolment in a group mobility, from the portal; issue #702, the
    data the selection was based on, frozen when the enrolment closes, and its result. A
    withdrawal keeps the record."""
    _name = 'ems.erasmus.group.registration'
    _description = 'Erasmus+ group mobility enrolment'
    _inherit = ['ems.base']
    _order = 'group_mobility_id, state, rank, id'
    _sql_constraints = [
        ('registration_unique', 'unique(group_mobility_id, partner_id)', "A student enrols once in a mobility."),
    ]

    group_mobility_id = fields.Many2one(string="Group mobility", comodel_name='ems.erasmus.group.mobility',
                                        required=True, ondelete='cascade', index=True, readonly=True)
    partner_id = fields.Many2one(string="Student", comodel_name='res.partner', required=True, ondelete='restrict',
                                 index=True, readonly=True)
    group_id = fields.Many2one(string="Group", related='partner_id.main_group_id')
    state = fields.Selection(string="Enrolment", required=True, default='enrolled', tracking=True, readonly=True,
                             selection=[('enrolled', "Enrolled"), ('withdrawn', "Withdrawn")])
    enrol_date = fields.Datetime(string="Enrolled on", readonly=True)
    enrol_user_id = fields.Many2one(string="Enrolled by", comodel_name='res.users', readonly=True)
    withdraw_date = fields.Datetime(string="Withdrawn on", readonly=True)
    fewer_opportunities = fields.Boolean(string="Declares fewer opportunities", readonly=True,
                                         groups='ems.group_erasmus,ems.group_academic_admin')
    fewer_opportunities_check = fields.Selection(
        string="Fewer opportunities accredited", selection=[('pending', "Pending"), ('yes', "Yes"), ('no', "No")],
        default='pending', tracking=True, groups='ems.group_erasmus,ems.group_academic_admin',
        help="Checked by the Erasmus team: the tie-break after the record average.")

    # Frozen when the enrolment closes (issue #702).
    frozen_date = fields.Datetime(string="Data frozen on", readonly=True)
    frozen_group_id = fields.Many2one(string="Group at closing", comodel_name='ems.group', readonly=True)
    grade_average = fields.Float(string="Record average", digits=(4, 2), readonly=True,
                                 help="Calculated by EMS as in the internship call, frozen at closing.")
    grade_found = fields.Boolean(string="Has grades", readonly=True,
                                 help="Without any evaluated module there is no average: an incident the Erasmus "
                                      "team resolves before the ranking can be closed, never a 0.")
    grade_manual = fields.Boolean(string="Average entered by hand", tracking=True,
                                  help="The Erasmus team enters the record average of a student EMS has no grades of "
                                       "(e.g. from the academic record), with the reason.")
    grade_average_manual = fields.Float(string="Average entered", digits=(4, 2), tracking=True)
    grade_manual_reason = fields.Text(string="Where the average comes from", tracking=True)
    has_average = fields.Boolean(string="Has an average", compute='_compute_grade_incident', store=True)
    grade_incident = fields.Boolean(
        string="No grades", compute='_compute_grade_incident', store=True,
        help="Eligible with no evaluated module: until the team enters the average by hand or the coordinator "
             "excludes the student with a reason, the ranking cannot be closed.")
    strike_count = fields.Integer(string="Conduct warnings this course", readonly=True,
                                  groups='ems.group_erasmus,ems.group_academic_admin')
    exclusion = fields.Selection(string="Reason not eligible", selection=EXCLUSIONS, readonly=True,
                                 groups='ems.group_erasmus,ems.group_academic_admin')
    eligible = fields.Boolean(string="Meets the requirements", readonly=True)
    rank = fields.Integer(string="Rank", readonly=True)
    needs_draw = fields.Boolean(string="Tied", readonly=True)
    draw_order = fields.Integer(string="Draw", tracking=True, readonly=True,
                                help="Position in the draw that resolved a tie (the Erasmus coordinator runs it). "
                                     "Lower goes first.")
    proposed_result = fields.Selection(string="Proposed", selection=RESULTS, readonly=True)
    result_override = fields.Selection(string="Exception", selection=RESULTS[:3], tracking=True,
                                       help="Only the Erasmus coordination, with a reason: replaces the proposed "
                                            "result.")
    override_reason = fields.Text(string="Reason for the exception", tracking=True)
    exception_request = fields.Text(string="Exception requested by the leader", tracking=True)
    result = fields.Selection(string="Result", selection=RESULTS, readonly=True, tracking=True,
                              help="Published when the coordinator approves the selection.")
    reserve_position = fields.Integer(string="Reserve number", compute='_compute_reserve_position')
    renounce_date = fields.Datetime(string="Renounced on", readonly=True)
    renounce_reason = fields.Text(string="Reason for renouncing", readonly=True)
    substitution_state = fields.Selection(string="Substitution", readonly=True, tracking=True,
                                          selection=[('proposed', "Proposed"), ('approved', "Approved")])
    substitute_for_id = fields.Many2one(string="Replaces", comodel_name='ems.erasmus.group.registration',
                                        readonly=True)
    substitute_id = fields.Many2one(string="Replaced by", comodel_name='ems.erasmus.group.registration',
                                    compute='_compute_substitute_id')
    substitution_proposed_by_id = fields.Many2one(string="Substitution proposed by", comodel_name='res.users',
                                                  readonly=True)
    substitution_proposed_date = fields.Datetime(string="Substitution proposed on", readonly=True)
    substitution_approved_by_id = fields.Many2one(string="Substitution approved by", comodel_name='res.users',
                                                  readonly=True)
    substitution_approved_date = fields.Datetime(string="Substitution approved on", readonly=True)
    participant_id = fields.Many2one(string="Participant file", comodel_name='ems.erasmus.group.participant', readonly=True)

    @api.depends('result', 'rank', 'group_mobility_id.registration_ids.result')
    def _compute_reserve_position(self):
        for registration in self:
            reserves = registration.group_mobility_id.registration_ids.filtered(
                lambda other: other.result == 'reserve' or other.proposed_result == 'reserve' and not other.result)
            ranks = sorted(reserves.mapped('rank'))
            registration.reserve_position = ranks.index(registration.rank) + 1 if registration in reserves else 0

    @api.depends('state', 'eligible', 'grade_found', 'grade_manual', 'result_override')
    def _compute_grade_incident(self):
        for registration in self:
            registration.has_average = registration.grade_found or registration.grade_manual
            registration.grade_incident = (registration.state == 'enrolled' and registration.eligible
                                           and not registration.has_average
                                           and registration.result_override != 'excluded')

    def _compute_substitute_id(self):
        for registration in self:
            registration.substitute_id = self.search([('substitute_for_id', '=', registration.id)], limit=1)

    def _compute_display_name(self):
        for registration in self:
            registration.display_name = f"{registration.partner_id.name} - {registration.group_mobility_id.name}"

    def write(self, vals):
        """The Erasmus team checks the fewer opportunities and sets tie orders and exceptions (the
        coordinator alone, before approving); the leader only requests an exception. The rest
        changes through the actions."""
        if not self.env.su:
            for registration in self:
                role = registration.group_mobility_id._ems_role()
                allowed = {'fewer_opportunities_check', 'result_override', 'override_reason', 'exception_request',
                           *GRADE_FIELDS} if role == 'team' else {'exception_request'} if role == 'leader' else set()
                if set(vals) - allowed:
                    raise AccessError(_("You cannot change this enrolment."))
                if registration.group_mobility_id.state not in ('selection', 'validation'):
                    raise UserError(_("The selection of %s is already decided.", registration.group_mobility_id.name))
            if {'result_override', 'override_reason'} & set(vals):
                self.group_mobility_id._ems_check_coordinator()
        result = super().write(vals)
        if {'fewer_opportunities_check', *GRADE_FIELDS} & set(vals):
            self.group_mobility_id._ems_rank()
        return result

    @api.constrains('grade_manual', 'grade_average_manual', 'grade_manual_reason')
    def _check_grade_manual(self):
        for registration in self.filtered('grade_manual'):
            if not (registration.grade_manual_reason or '').strip():
                raise ValidationError(_("An average entered by hand needs to say where it comes from."))
            if not 0 <= registration.grade_average_manual <= 10:
                raise ValidationError(_("A record average goes from 0 to 10."))

    @api.constrains('result_override', 'override_reason')
    def _check_override_reason(self):
        for registration in self:
            if registration.result_override and not (registration.override_reason or '').strip():
                raise ValidationError(_("An exception to the ranking needs a reason."))

    def _ems_write(self, vals):
        self.sudo().write(vals)

    # --- portal ----------------------------------------------------------------------------------

    @api.model
    def _ems_portal_enrol(self, mobility, partner, fewer_opportunities=False):
        """`partner` enrols with one click while the enrolment is open (again, after withdrawing)."""
        mobility = mobility.sudo()
        if not mobility._ems_is_eligible(partner):
            raise UserError(_("You cannot enrol in this mobility."))
        if not mobility.is_enrolling:
            raise UserError(_("The enrolment of this mobility is not open."))
        if mobility._ems_conduct_blocked(partner):
            raise UserError(_("You cannot enrol: you have too many conduct warnings this course."))
        registration = self.sudo().search([('group_mobility_id', '=', mobility.id), ('partner_id', '=', partner.id)])
        if registration.state == 'enrolled':
            raise UserError(_("You are already enrolled."))
        vals = {'state': 'enrolled', 'enrol_date': fields.Datetime.now(), 'enrol_user_id': self.env.uid,
                'withdraw_date': False, 'fewer_opportunities': bool(fewer_opportunities),
                'fewer_opportunities_check': 'pending'}
        if registration:
            registration._ems_write(vals)
            registration.chatter(_("Enrolled again."))
        else:
            registration = self.sudo().create(
                {'group_mobility_id': mobility.id, 'partner_id': partner.id, **vals})
        return registration

    def action_withdraw(self):
        """The student withdraws while the enrolment is open (portal, as sudo), or the team on
        their behalf; the record stays."""
        for registration in self:
            if not self.env.su:
                registration.group_mobility_id._ems_check_role('team')
            if registration.state != 'enrolled' or not registration.group_mobility_id.is_enrolling:
                raise UserError(_("The enrolment can only be withdrawn while it is open."))
        self._ems_write({'state': 'withdrawn', 'withdraw_date': fields.Datetime.now()})

    # --- selection -------------------------------------------------------------------------------

    def _ems_freeze(self):
        """What the ranking is based on, as EMS has it now, never recomputed: the group, the record
        average (the internship call's) and this course's conduct warnings."""
        Application = self.env['ems.erasmus.application']
        for registration in self.sudo():
            mobility, partner = registration.group_mobility_id, registration.partner_id
            course = mobility.course_id or self.env.company.current_course_id
            grades = Application._ems_partner_grade_values(partner, course.name)
            average, hours = Application._ems_grade_average(grades)
            strikes = self.env['ems.erasmus.call']._ems_partner_course_strike_count(partner, course)
            exclusion = False if mobility._ems_is_eligible(partner) else 'group'
            if not exclusion and self.env['ems.erasmus.call']._ems_conduct_blocked_count(strikes):
                exclusion = 'conduct'
            registration._ems_write({
                'frozen_date': fields.Datetime.now(), 'frozen_group_id': partner.main_group_id.id,
                'grade_average': average, 'grade_found': bool(hours), 'strike_count': strikes,
                'exclusion': exclusion, 'eligible': not exclusion,
            })

    def _ems_average(self):
        """The record average the ranking uses: EMS's, or the one the team entered by hand."""
        self.ensure_one()
        return self.grade_average_manual if self.grade_manual else self.grade_average

    def _ems_list_result(self):
        """The result a published list shows: the approved one, else the proposal with the
        coordinator's exception."""
        self.ensure_one()
        return self.result or self.result_override or self.proposed_result

    def _ems_exclusion_reason(self):
        """Why a student is excluded, for them only: the coordinator's reason for an exception, or
        the requirement not met."""
        self.ensure_one()
        if self.result_override == 'excluded':
            return self.override_reason
        return dict(self._fields['exclusion']._description_selection(self.env)).get(self.exclusion, '')

    def _ems_identity_document(self):
        partner = self.sudo().partner_id
        return partner.document_id or partner.passport_id or ''

    def _ems_tie_key(self):
        """What a tie is: the same average and the same accreditation of fewer opportunities."""
        self.ensure_one()
        return -self._ems_average(), self.sudo().fewer_opportunities_check != 'yes'

    def _ems_rank_key(self):
        self.ensure_one()
        return *self._ems_tie_key(), self.draw_order

    def action_request_exception(self):
        """The leader asks the coordinator for an exception (written in Exception requested)."""
        for registration in self:
            registration.group_mobility_id._ems_check_role('team', 'leader')
            if not (registration.exception_request or '').strip():
                raise UserError(_("Write the exception you request and why first."))
            mobility = registration.group_mobility_id
            mobility._ems_schedule(mobility._ems_coordinators(), _("Erasmus+: exception requested for %s in %s",
                                                                   registration.partner_id.name, mobility.name))

    def _ems_open_file(self):
        """The participant file of each selected student."""
        Participant = self.env['ems.erasmus.group.participant'].sudo()
        for registration in self.sudo():
            participant = registration.participant_id or Participant.search([
                ('group_mobility_id', '=', registration.group_mobility_id.id),
                ('partner_id', '=', registration.partner_id.id)])
            if participant:
                participant.write({'state': 'active'})
            else:
                participant = Participant.create({'group_mobility_id': registration.group_mobility_id.id,
                                                  'partner_id': registration.partner_id.id, 'role': 'student'})
            registration._ems_write({'participant_id': participant.id})
            participant._ems_sync_documents()
            participant._ems_remind_guardians()

    def _ems_send_result(self):
        """Each student's own result, to their own address (noted in the chatter when there is none)."""
        template = self.env.ref('ems.email_template_erasmus_group_result')
        for registration in self.sudo():
            partner = registration.partner_id
            if partner.email:
                template.with_context(lang=partner.lang).send_mail(
                    registration.id, force_send=False, email_values={'email_to': partner.email})
            else:
                registration.chatter(_("No email sent: the student has no email address."))

    def action_renounce(self, reason=False):
        """A selected student renounces (from the portal, or the team or the leader on their
        behalf, with the reason): the place is free for the next reserve. The file and its
        documents are kept, closed."""
        for registration in self:
            if not self.env.su:
                registration.group_mobility_id._ems_check_role('team', 'leader')
            if registration.result != 'selected' or registration.group_mobility_id.state not in ('preparation',
                                                                                                  'stay'):
                raise UserError(_("Only a selected student renounces, before the mobility ends."))
        for registration in self:
            registration._ems_write({'result': 'renounced', 'renounce_date': fields.Datetime.now(),
                                     'renounce_reason': reason or _("Renounced by the student.")})
            registration.participant_id.sudo().write({'state': 'withdrawn'})
            mobility = registration.group_mobility_id
            mobility.sudo().chatter(_("%s renounced the place.", registration.partner_id.name))
            leader = mobility.sudo().leader_id.user_id or mobility._ems_team_users()
            mobility._ems_schedule(leader, _("Erasmus+: propose a substitute in %s", mobility.name))

    def action_approve_substitution(self):
        self.group_mobility_id._ems_check_coordinator()
        for registration in self:
            if registration.substitution_state != 'proposed':
                raise UserError(_("No substitution of %s is waiting for approval.", registration.partner_id.name))
        self.group_mobility_id._ems_activities_done()
        for registration in self:
            registration._ems_write({'result': 'selected', 'substitution_state': 'approved',
                                     'substitution_approved_by_id': self.env.uid,
                                     'substitution_approved_date': fields.Datetime.now()})
            registration.group_mobility_id.sudo().chatter(_("Substitution approved: %s joins the group.",
                                                     registration.partner_id.name))
        self._ems_open_file()
        self._ems_send_result()

    def action_reject_substitution(self):
        self.group_mobility_id._ems_check_coordinator()
        for registration in self:
            if registration.substitution_state != 'proposed':
                raise UserError(_("No substitution of %s is waiting for approval.", registration.partner_id.name))
        self.group_mobility_id._ems_activities_done()
        self._ems_write({'substitution_state': False, 'substitute_for_id': False})
        for registration in self:
            registration.group_mobility_id.sudo().chatter(_("Substitution of %s not approved.", registration.partner_id.name))


class EmsErasmusGroupParticipant(models.Model):
    """Issue #703 - a participant's file in a group mobility: a selected student, or an
    accompanying teacher (who joins without any staff call). Its documents are lines of the
    Erasmus+ document engine with no application. A student accepts the mobility's commitment
    letter on the portal, and the family of a minor too (ems.erasmus.commitment, the same
    mechanism as the internship mobilities)."""
    _name = 'ems.erasmus.group.participant'
    _description = 'Erasmus+ group mobility participant'
    _inherit = ['ems.base', 'ems.erasmus.commitment']
    _ems_commitment_guardian_template = 'ems.email_template_erasmus_group_commitment_guardian'
    _order = 'group_mobility_id, role desc, partner_id'
    _sql_constraints = [
        ('participant_unique', 'unique(group_mobility_id, partner_id)', "A person takes part once in a mobility."),
    ]

    group_mobility_id = fields.Many2one(string="Group mobility", comodel_name='ems.erasmus.group.mobility',
                                        required=True, ondelete='cascade', index=True, readonly=True)
    mobility_state = fields.Selection(string="Mobility state", related='group_mobility_id.state')
    role = fields.Selection(string="Role", selection=ROLES, required=True, readonly=True)
    partner_id = fields.Many2one(string="Participant", comodel_name='res.partner', required=True, readonly=True,
                                 ondelete='restrict', index=True)
    employee_id = fields.Many2one(string="Employee", comodel_name='hr.employee', readonly=True)
    group_id = fields.Many2one(string="Group", related='partner_id.main_group_id')
    email = fields.Char(string="Email", related='partner_id.email')
    phone = fields.Char(string="Phone", related='partner_id.mobile')
    state = fields.Selection(string="State", required=True, default='active', readonly=True, tracking=True,
                             selection=[('active', "Taking part"), ('withdrawn', "Withdrawn")])
    is_minor = fields.Boolean(string="Minor", compute='_compute_is_minor')
    insurance_collective = fields.Boolean(
        string="Covered by the collective policy", tracking=True,
        help="The group's collective insurance policy covers this participant: their own policy is not asked for.")
    auth_image = fields.Boolean(string="Image rights", related='partner_id.auth_image',
                                help="The student's image rights authorisation of the course, the same EMS uses for "
                                     "everything else: no other one is asked for the mobility.")
    audience = fields.Selection(string="Kind", selection=[('student', "Student"), ('staff', "Staff")],
                                compute='_compute_audience')
    document_ids = fields.One2many(string="Documents", comodel_name='ems.erasmus.application.document',
                                   inverse_name='group_participant_id')
    registration_ids = fields.One2many(string="Enrolment", comodel_name='ems.erasmus.group.registration',
                                       inverse_name='participant_id')
    documents_missing = fields.Integer(string="Documents missing", compute='_compute_documents',
                                       help="Required documents with no file yet, or needing changes.")
    documents_valid = fields.Integer(string="Documents complete", compute='_compute_documents')
    record_progress = fields.Char(string="Record", compute='_compute_documents',
                                  help="Required documents complete out of those required.")
    record_missing = fields.Integer(string="Required documents not complete", compute='_compute_documents',
                                    help="Missing, pending review or needing changes.")
    preparation_complete = fields.Boolean(string="Ready to leave", compute='_compute_documents')

    @api.depends('partner_id.birth_date', 'role')
    def _compute_is_minor(self):
        for participant in self:
            participant.is_minor = participant.role == 'student' and not participant.partner_id.is_adult

    @api.depends('role')
    def _compute_audience(self):
        for participant in self:
            participant.audience = 'student' if participant.role == 'student' else 'staff'

    @api.depends('document_ids.file_state', 'document_ids.is_required', 'commitment_pending',
                 'commitment_guardian_pending', 'commitment_provisional')
    def _compute_documents(self):
        """Ready to leave: every required document before leaving complete (`file_state`, the same as
        the individual mobilities: a document to sign only once the team checked it) and, for a
        student, the commitment letter accepted (also by the family of a minor), not provisionally."""
        for participant in self:
            lines = participant.document_ids
            required = lines.filtered('is_required')
            complete = required.filtered(lambda line: line.file_state == 'complete')
            participant.documents_missing = len(lines.filtered(lambda line: line.file_state in MISSING_STATES))
            participant.documents_valid = len(lines.filtered(lambda line: line.file_state == 'complete'))
            participant.record_progress = f"{len(complete)} / {len(required)}"
            participant.record_missing = len(required - complete)
            participant.preparation_complete = not (
                (required - complete).filtered(lambda line: line.stage == 'preparation')
                or participant.commitment_pending or participant.commitment_guardian_pending
                or participant.commitment_provisional)

    def _compute_display_name(self):
        for participant in self:
            participant.display_name = f"{participant.partner_id.name} - {participant.group_mobility_id.name}"

    @api.model_create_multi
    def create(self, vals_list):
        check_workflow_create(self, vals_list)
        return super().create(vals_list)

    def write(self, vals):
        """Who takes part, as what, whether withdrawn and the commitment letter's signatures only
        change through the actions (audit R-25)."""
        check_workflow_write(self, vals)
        return super().write(vals)

    def unlink(self):
        check_kept(self, self.filtered(lambda participant: participant._ems_has_evidence()))
        return super().unlink()

    def _ems_has_evidence(self):
        """A file, a signature or an earlier version of the letter: a withdrawn participant keeps them."""
        self.ensure_one()
        participant = self.sudo()
        return bool(participant.document_ids._ems_evidence() or participant.commitment_signed_date
                    or participant.commitment_guardian_signed_date or participant.commitment_version_ids
                    or participant.registration_ids)

    # --- the commitment letter (ems.erasmus.commitment) -------------------------------------------

    def _ems_commitment_depends(self):
        return super()._ems_commitment_depends() + ['role', 'partner_id.birth_date', 'group_mobility_id.city',
                                                    'group_mobility_id.country_id', 'group_mobility_id.date_start']

    def _ems_commitment_letter(self):
        """A student's letter: the common template with the mobility's data now (destination and
        dates once confirmed) and its additional conditions, in the reader's language. Whole
        sentences with named placeholders, so each one translates as a unit."""
        self.ensure_one()
        if self.role != 'student':
            return False
        participant = self.sudo()
        mobility = participant.group_mobility_id
        minor = participant.is_minor
        place = ', '.join(filter(None, [mobility.city, mobility.country_id.name]))
        if mobility.host_partner_id:
            place = f"{place} ({mobility.host_partner_id.name})" if place else mobility.host_partner_id.name
        values = {'student': participant.partner_id.name, 'mobility': mobility.name,
                  'project': mobility.project_id.display_name or '', 'place': place,
                  'start': format_date(self.env, mobility.date_start), 'end': format_date(self.env, mobility.date_end),
                  'out': format_date(self.env, mobility.travel_date_out),
                  'back': format_date(self.env, mobility.travel_date_back),
                  'teachers': ', '.join((mobility.leader_id | mobility.companion_ids).mapped('name'))}
        if place and mobility.date_start:
            participation = (_("The family authorises %(student)s to take part in this mobility, in %(place)s, from "
                               "%(start)s to %(end)s.", **values) if minor else
                             _("%(student)s takes part in this mobility, in %(place)s, from %(start)s to %(end)s.",
                               **values))
            if mobility.travel_date_out:
                participation += " " + _("The group travels out on %(out)s and comes back on %(back)s.", **values)
        else:
            participation = (_("The family authorises %(student)s to take part in this mobility.", **values) if minor
                             else _("%(student)s takes part in this mobility.", **values))
            participation += " " + _("The destination and the final dates are still to be confirmed: the Erasmus "
                                     "team will communicate them before leaving.")
        if values['teachers']:
            participation += " " + _("The group travels with its accompanying teachers: %(teachers)s.", **values)
        commitments = [
            participation,
            _("The student commits to take part in every activity of the programme, on the dates and at the times "
              "set."),
            _("The student commits to respect the centre's rules of coexistence, those of the host entity and of the "
              "accommodation, and to follow the instructions of the accompanying teachers at all times."),
            _("A serious breach of these commitments or of those rules may lead to the measures that the centre's "
              "rules of organisation and operation and its applicable protocols provide for."),
            _("The family and the student commit to communicate and collaborate with the centre: to keep their "
              "contact details up to date, to be reachable during the stay and to tell the accompanying teachers and "
              "the Erasmus team about any incident, health need or circumstance that may affect the mobility.")
            if minor else
            _("The student commits to communicate and collaborate with the centre: to keep their contact details up "
              "to date, to be reachable during the stay and to tell the accompanying teachers and the Erasmus team "
              "about any incident, health need or circumstance that may affect the mobility."),
        ]
        intro = (_("Commitments accepted by %(student)s and their family or legal guardians for the Erasmus+ group "
                   "mobility %(mobility)s (project %(project)s):", **values) if minor else
                 _("Commitments accepted by %(student)s for the Erasmus+ group mobility %(mobility)s (project "
                   "%(project)s):", **values))
        letter = Markup("<p>{}</p><ol>{}</ol>").format(
            intro, Markup("").join(Markup("<li>{}</li>").format(item) for item in commitments))
        if mobility.commitment_extra:
            letter += Markup("<p><strong>{}</strong></p>{}").format(
                _("Additional conditions of this mobility"), mobility.commitment_extra)
        if minor:
            letter += Markup("<p><em>{}</em></p>").format(_(
                "This letter does not replace the official authorisation for minors to travel abroad: when it is "
                "needed, it is processed separately and handed in as its own document of the student's file."))
        return letter

    def _ems_commitment_has_letter(self):
        return self.role == 'student'

    def _ems_commitment_is_minor(self):
        return self.is_minor

    def _ems_commitment_is_final(self):
        """The destination and the dates confirmed: an acceptance before is provisional (the letter
        says they are still to be confirmed)."""
        mobility = self.sudo().group_mobility_id
        return bool((mobility.city or mobility.country_id or mobility.host_partner_id) and mobility.date_start)

    def _ems_commitment_open(self):
        """Before leaving, while the student takes part."""
        return self.state == 'active' and self.group_mobility_id.state == 'preparation'

    def _ems_sync_documents(self):
        """The documents asked for this participant's role still missing. Never removes a line."""
        Line = self.env['ems.erasmus.application.document'].sudo()
        audiences = {'student': ('student', 'participant'), 'leader': ('teacher', 'participant'),
                     'companion': ('teacher', 'participant')}
        for participant in self.sudo():
            documents = participant.group_mobility_id.requirement_ids.filtered(
                lambda document: document.group_audience in audiences[participant.role])
            Line.create([{'group_mobility_id': participant.group_mobility_id.id, 'group_participant_id': participant.id,
                          'call_document_id': document.id}
                         for document in documents - participant.document_ids.call_document_id])

    def _ems_participant_row(self):
        """The row of the participants' spreadsheet (PARTICIPANT_HEADERS, the calls' format): a
        student's from their contact, with their cycle and year (an accompanying teacher's stay
        empty, which tells them apart); a teacher's from their employee file, like a staff call's.
        No bank details: a group mobility pays its expenses collectively, nothing is transferred
        to a participant from EMS."""
        self.ensure_one()
        Application = self.env['ems.erasmus.application']
        participant = self.sudo()
        if participant.role == 'student':
            return Application._ems_student_row(participant.partner_id, participant.is_minor, bank=False)
        return Application._ems_staff_row(participant.employee_id, participant.partner_id, bank=False)

    def _ems_participants_xlsx(self):
        """The participants' spreadsheet of these files (one mobility's): students first, by name."""
        if not self:
            raise UserError(_("There are no participants to export."))
        self.group_mobility_id._ems_check_role('team')
        participants = self.sudo().filtered(lambda participant: participant.state == 'active').sorted(
            lambda participant: (participant.role != 'student', participant.partner_id.name or ''))
        content = self.env['ems.erasmus.application']._ems_participants_workbook(
            [participant._ems_participant_row() for participant in participants])
        self.env['ems.erasmus.export']._ems_log_spreadsheet(self.group_mobility_id, len(participants))
        return content

    def _ems_portal_upload(self, uploads):
        """Files a student uploads from the portal: {call document id: [(name, bytes)]}, while the
        file is open."""
        self.ensure_one()
        if self.state != 'active' or self.group_mobility_id.state not in FILE_STATES:
            raise UserError(_("The documents of this mobility can no longer be changed."))
        lines = {line.call_document_id.id: line for line in self.document_ids
                 if line.handled_by != 'team' and line._ems_is_open()}
        for document_id, files in uploads.items():
            if files and document_id in lines:
                lines[document_id]._ems_add_files(files)


class EmsErasmusGroupDraw(models.Model):
    """Issue #702 - a draw the Erasmus coordinator ran to resolve one tie: who, when, what the
    students were tied on, the exact set tied and the order drawn. Created by EMS only, never
    changed nor deleted: the evidence of the selection. A group mobility's (issue #702) or, since
    audit D-13, a call's: the ties left in its ranking after every tie-break."""
    _name = 'ems.erasmus.group.draw'
    _description = 'Erasmus+ draw'
    _order = 'date desc, id desc'
    _sql_constraints = [
        ('one_owner', 'CHECK((call_id IS NULL) != (group_mobility_id IS NULL))',
         "A draw belongs to a call or to a group mobility."),
    ]

    group_mobility_id = fields.Many2one(string="Group mobility", comodel_name='ems.erasmus.group.mobility',
                                        ondelete='cascade', index=True, readonly=True)
    call_id = fields.Many2one(string="Call", comodel_name='ems.erasmus.call', ondelete='cascade', index=True,
                              readonly=True)
    score_total = fields.Float(string="Tied on the total", digits=(5, 2), readonly=True)
    user_id = fields.Many2one(string="Run by", comodel_name='res.users', required=True, readonly=True,
                              ondelete='restrict')
    date = fields.Datetime(string="Run on", required=True, readonly=True)
    grade_average = fields.Float(string="Tied on the average", digits=(4, 2), readonly=True)
    fewer_opportunities = fields.Boolean(string="Fewer opportunities accredited", readonly=True)
    line_ids = fields.One2many(string="Order drawn", comodel_name='ems.erasmus.group.draw.line',
                               inverse_name='draw_id', readonly=True)
    tied_count = fields.Integer(string="Students tied", compute='_compute_tied_count')

    @api.depends('line_ids')
    def _compute_tied_count(self):
        for draw in self:
            draw.tied_count = len(draw.line_ids)

    def write(self, vals):
        raise UserError(_("A draw is the evidence of the selection: it cannot be changed."))

    def unlink(self):
        if not self.env.context.get(MODULE_UNINSTALL_FLAG):
            raise UserError(_("A draw is the evidence of the selection: it cannot be deleted."))
        return super().unlink()

    @api.model
    def _ems_run(self, owner, ties):
        """Order each tied set at random (a cryptographically secure generator), write the order drawn
        on its records (`draw_order`, 1 goes first) and keep one draw per set; summed up in `owner`'s
        chatter. `owner`: the group mobility or the call; `ties`: [(records tied, the draw's values, i.e.
        what they were tied on)], registrations or applications. Ties only: it never moves anyone else."""
        randomizer = secrets.SystemRandom()
        now = fields.Datetime.now()
        owner_field = 'call_id' if owner._name == 'ems.erasmus.call' else 'group_mobility_id'
        lines = []
        for records, vals in ties:
            record_field = 'application_id' if records._name == 'ems.erasmus.application' else 'registration_id'
            drawn = list(records.sorted(lambda record: record.partner_id.name))
            randomizer.shuffle(drawn)
            for order, record in enumerate(drawn, 1):
                record.sudo().write({'draw_order': order})
            self.sudo().create({
                owner_field: owner.id, 'user_id': self.env.uid, 'date': now, **vals,
                'line_ids': [(0, 0, {record_field: record.id, 'partner_id': record.partner_id.id, 'position': order})
                             for order, record in enumerate(drawn, 1)],
            })
            lines.append(", ".join(f"{order}. {record.partner_id.name}" for order, record in enumerate(drawn, 1)))
        owner.sudo().chatter(Markup("{}{}").format(_("Draw of the ties, run by %s:", self.env.user.name),
                                                   self.env['ems.base'].build_html_list(lines)))


class EmsErasmusGroupDrawLine(models.Model):
    """A student of a draw and the position drawn (1 goes first)."""
    _name = 'ems.erasmus.group.draw.line'
    _description = 'Erasmus+ group mobility draw position'
    _order = 'draw_id, position'

    draw_id = fields.Many2one(string="Draw", comodel_name='ems.erasmus.group.draw', required=True,
                              ondelete='cascade', index=True, readonly=True)
    position = fields.Integer(string="Position", required=True, readonly=True)
    registration_id = fields.Many2one(string="Enrolment", comodel_name='ems.erasmus.group.registration',
                                      ondelete='cascade', readonly=True)
    application_id = fields.Many2one(string="Application", comodel_name='ems.erasmus.application',
                                     ondelete='cascade', readonly=True)
    partner_id = fields.Many2one(string="Student", comodel_name='res.partner', required=True, readonly=True,
                                 ondelete='restrict')

    def _compute_display_name(self):
        for line in self:
            line.display_name = f"{line.position}. {line.partner_id.name}"

    def write(self, vals):
        raise UserError(_("A draw is the evidence of the selection: it cannot be changed."))

    def unlink(self):
        if not self.env.context.get(MODULE_UNINSTALL_FLAG):
            raise UserError(_("A draw is the evidence of the selection: it cannot be deleted."))
        return super().unlink()


class EmsErasmusGroupLog(models.Model):
    """Issue #704 - the group's follow-up during the stay, written by its teachers: attendance,
    incidents (apart from the academic conduct warnings), changes, evidence and communications."""
    _name = 'ems.erasmus.group.log'
    _description = 'Erasmus+ group mobility follow-up'
    _order = 'date desc, id desc'

    group_mobility_id = fields.Many2one(string="Group mobility", comodel_name='ems.erasmus.group.mobility',
                                        required=True, ondelete='cascade', index=True)
    date = fields.Date(string="Date", required=True,
                       default=lambda self: self.env['ems.datetime_utils'].get_local_today())
    kind = fields.Selection(string="Kind", selection=LOG_KINDS, required=True, default='evidence')
    name = fields.Char(string="Summary", required=True)
    description = fields.Text(string="Details")
    participant_ids = fields.Many2many(string="Participants", comodel_name='ems.erasmus.group.participant',
                                       domain="[('group_mobility_id', '=', group_mobility_id)]",
                                       help="Attendance: who was absent. Otherwise, who it is about.")
    attachment_ids = fields.Many2many(string="Files", comodel_name='ir.attachment',
                                      relation='ems_erasmus_group_log_attachment_rel')
    author_id = fields.Many2one(string="Written by", comodel_name='res.users', readonly=True,
                                default=lambda self: self.env.user)

    @api.model_create_multi
    def create(self, vals_list):
        logs = super().create(vals_list)
        logs.group_mobility_id._ems_check_role('team', 'leader', 'companion')
        return logs


class EmsErasmusCallDocument(models.Model):
    """Issue #701 - a document a group mobility asks for: it has a group mobility instead of a call,
    and is for the whole group (one shared document) or for each participant of a role."""
    _inherit = 'ems.erasmus.call.document'
    _sql_constraints = [
        ('one_owner', 'CHECK((call_id IS NULL) != (group_mobility_id IS NULL))',
         "A document belongs to a call or to a group mobility."),
    ]

    call_id = fields.Many2one(required=False)
    group_mobility_id = fields.Many2one(string="Group mobility", comodel_name='ems.erasmus.group.mobility',
                                        ondelete='cascade', index=True)
    requirement = fields.Selection(selection_add=[('insurance', "Insurance: own policy or the collective one")],
                                   ondelete={'insurance': 'set default'})
    group_audience = fields.Selection(string="For", selection=GROUP_AUDIENCES, default='student',
                                      help="Group mobilities: one document shared by the whole group (e.g. the group "
                                           "learning agreement), or one from each student, teacher or participant.")


class EmsErasmusApplicationDocument(models.Model):
    """Issue #701 - a group mobility's document, with no application: the line of a participant
    (`group_participant_id`), or the group's shared one (no participant). Same review, files and
    deadlines as any other line; the deadlines count from the group mobility's dates."""
    _inherit = 'ems.erasmus.application.document'
    _sql_constraints = [
        ('one_owner', 'CHECK((application_id IS NULL) != (group_mobility_id IS NULL))',
         "A document belongs to an application or to a group mobility."),
    ]

    application_id = fields.Many2one(required=False)
    group_mobility_id = fields.Many2one(string="Group mobility", comodel_name='ems.erasmus.group.mobility',
                                        ondelete='cascade', index=True)
    group_participant_id = fields.Many2one(string="Participant", comodel_name='ems.erasmus.group.participant',
                                           ondelete='cascade', index=True)

    @api.constrains('group_mobility_id', 'group_participant_id')
    def _check_participant(self):
        for line in self:
            if line.group_participant_id and line.group_participant_id.group_mobility_id != line.group_mobility_id:
                raise ValidationError(_("A participant's document belongs to their own group mobility."))

    @api.depends('group_participant_id.is_minor', 'group_participant_id.insurance_collective',
                 'group_mobility_id.participant_ids.insurance_collective', 'group_mobility_id.participant_ids.state')
    def _compute_is_required(self):
        """A group's insurance: each participant's own policy, unless the collective one covers
        them; the collective policy once it covers anyone."""
        super()._compute_is_required()
        for line in self.filtered('group_mobility_id'):
            requirement, participant = line.call_document_id.requirement, line.group_participant_id
            if requirement == 'minor' and participant:
                line.is_required = participant.is_minor
            elif requirement == 'insurance':
                line.is_required = not participant.insurance_collective if participant else any(
                    line.group_mobility_id.participant_ids.filtered(lambda other: other.state == 'active')
                    .mapped('insurance_collective'))

    @api.depends('group_mobility_id.destination_date', 'group_mobility_id.date_start', 'group_mobility_id.date_end')
    def _compute_deadline(self):
        super()._compute_deadline()
        for line in self.filtered('group_mobility_id'):
            document, mobility = line.call_document_id, line.group_mobility_id
            basis = {'destination': mobility.destination_date, 'before_start': mobility.date_start,
                     'after_end': mobility.date_end}.get(document.due_basis)
            sign = -1 if document.due_basis == 'before_start' else 1
            line.deadline = basis and basis + timedelta(days=sign * document.due_days)

    @api.depends('group_mobility_id.date_start')
    def _compute_open_date(self):
        super()._compute_open_date()
        for line in self.filtered('group_mobility_id'):
            start, days = line.group_mobility_id.date_start, line.call_document_id.open_days
            line.open_date = days and start and start - timedelta(days=days)

    def write(self, vals):
        """A group mobility's line: only the Erasmus team and the leader teacher review it."""
        if 'review_state' in vals and not self.env.su:
            for mobility in self.group_mobility_id:
                mobility._ems_check_role('team', 'leader')
        return super().write(vals)

    def _ems_record_closed(self):
        return super()._ems_record_closed() or self.group_mobility_id.state in ('done', 'cancelled')

    def _ems_check_reviewer(self):
        """A group mobility's documents: the Erasmus team and the leader teacher."""
        if self.env.su:
            return
        for mobility in self.group_mobility_id:
            mobility._ems_check_role('team', 'leader')
        if self - self.filtered('group_mobility_id'):
            super(EmsErasmusApplicationDocument, self - self.filtered('group_mobility_id'))._ems_check_reviewer()

    def _ems_is_minor(self):
        return self.group_participant_id.is_minor if self.group_mobility_id else super()._ems_is_minor()

    def _ems_record_owner(self):
        """A group line's review is written in its group mobility's chatter (the participant's name
        first, for an individual one)."""
        return self.group_mobility_id or super()._ems_record_owner()

    def _ems_record_label(self):
        if self.group_participant_id:
            return f"{self.group_participant_id.partner_id.name} - {self.name}"
        return super()._ems_record_label()


class EmsErasmusInvoice(models.Model):
    """Issue #704 - an invoice of the group as a whole (e.g. the group's flights or accommodation):
    charged to its project and linked to the group mobility, never split by EMS among its
    participants."""
    _inherit = 'ems.erasmus.invoice'

    group_mobility_id = fields.Many2one(string="Group mobility", comodel_name='ems.erasmus.group.mobility',
                                        ondelete='set null', index=True,
                                        domain="[('project_id', '=', project_id)]")


class EmsErasmusProject(models.Model):
    """A project's group mobilities and their participants' records, counted with the individual
    ones (see docs/en/developers/erasmus/records.md)."""
    _inherit = 'ems.erasmus.project'

    group_mobility_ids = fields.One2many(string="Group mobilities", comodel_name='ems.erasmus.group.mobility',
                                         inverse_name='project_id')

    def _compute_record_counts(self):
        """Each active participant of a group mobility (draft and cancelled ones apart) is one more
        record; the group's common documents count as missing too."""
        super()._compute_record_counts()
        Export = self.env['ems.erasmus.export']
        for project in self:
            groups = Export._ems_project_group_mobilities(project)
            participants = groups.participant_ids.filtered(lambda participant: participant.state == 'active')
            project.record_count += len(participants)
            project.record_complete_count += len(participants.filtered(lambda participant: not participant.record_missing))
            project.record_missing_count += sum(Export._ems_group_missing(group) for group in groups)


class EmsErasmusResolution(models.Model):
    """A group mobility's provisional and definitive lists of admitted, excluded and reserves, with
    the calls' resolutions: frozen lines, only the masked identity document published, approved by
    the Erasmus coordinator, kept as a PDF in the project's dossier. Published by the mobility's
    actions (action_publish_provisional, action_approve_selection)."""
    _inherit = 'ems.erasmus.resolution'
    _sql_constraints = [
        ('one_owner', 'CHECK((call_id IS NULL) != (group_mobility_id IS NULL))',
         "A resolution belongs to a call or to a group mobility."),
    ]

    call_id = fields.Many2one(required=False)
    group_mobility_id = fields.Many2one(string="Group mobility", comodel_name='ems.erasmus.group.mobility',
                                        ondelete='restrict', index=True)

    @api.depends('group_mobility_id.name')
    def _compute_name(self):
        super()._compute_name()
        kinds = self._ems_kind_labels()
        for resolution in self.filtered('group_mobility_id'):
            resolution.name = f"{kinds.get(resolution.kind, '')} - {resolution.group_mobility_id.name}"

    def _ems_check_can_prepare(self):
        """A group mobility: its provisional list while the coordinator validates the selection, its
        definitive one once approved, each published once."""
        if not self.group_mobility_id:
            return super()._ems_check_can_prepare()
        mobility = self.group_mobility_id.sudo()
        kinds = self._ems_kind_labels()
        if self.kind not in ('provisional', 'definitive'):
            raise UserError(_("A group mobility publishes a provisional and a definitive list only."))
        published = mobility.resolution_ids.filtered(lambda resolution: resolution.state == 'published') - self
        if self.kind in published.mapped('kind'):
            raise UserError(_("This group mobility already has a published %s.", kinds[self.kind].lower()))
        if self.kind == 'provisional' and mobility.state != 'validation':
            raise UserError(_("The provisional list is published while the coordinator validates the selection."))
        if self.kind == 'definitive' and ('provisional' not in published.mapped('kind')
                                          or mobility.state not in FILE_STATES):
            raise UserError(_("The definitive list is published when the coordinator approves the selection."))
        missing = self._ems_registrations().filtered(
            lambda registration: not mask_document_id(registration._ems_identity_document()))
        if missing:
            raise UserError(_("Record the identity document of: %s", ", ".join(missing.partner_id.mapped('name'))))

    def _ems_check_can_publish(self):
        if not self.group_mobility_id:
            super()._ems_check_can_publish()

    def _ems_after_publish(self):
        """A group's provisional list: each student's own result by email, to claim by replying. The
        definitive one is the approval, which emails each student their result."""
        if not self.group_mobility_id:
            return super()._ems_after_publish()
        if self.kind != 'provisional':
            return
        template = self.env.ref('ems.email_template_erasmus_resolution_published')
        for line in self.line_ids:
            if line.partner_id.email:
                template.with_context(lang=line.partner_id.lang).sudo().send_mail(
                    line.id, force_send=False, email_values={'email_to': line.partner_id.email})
            else:
                line.group_registration_id.chatter(_("No email sent: the student has no email address."))

    def _ems_registrations(self):
        return self.group_mobility_id.sudo().registration_ids.filtered(
            lambda registration: registration.state == 'enrolled')

    def _ems_list_groups(self):
        return [('', self.line_ids)] if self.group_mobility_id else super()._ems_list_groups()

    def _ems_line_values(self):
        """Every enrolment still standing: rank and record average for the admitted (selected or
        reserve), the reason only for the student when excluded."""
        if not self.group_mobility_id:
            return super()._ems_line_values()
        values = []
        for registration in self._ems_registrations().sorted(lambda registration: (
                registration._ems_list_result() == 'excluded', registration.rank or 999999,
                registration.partner_id.name or '')):
            result = registration._ems_list_result()
            vals = {'group_registration_id': registration.id, 'result': result, 'sequence': len(values) + 1,
                    'public_id': mask_document_id(registration._ems_identity_document())}
            if result == 'excluded':
                vals['exclusion_reason'] = registration._ems_exclusion_reason()
            else:
                vals.update(rank=registration.rank, score_total=registration._ems_average())
            values.append(vals)
        return values


class EmsErasmusResolutionLine(models.Model):
    """A student of a group mobility in one of its lists."""
    _inherit = 'ems.erasmus.resolution.line'
    _sql_constraints = [
        ('one_owner', 'CHECK((application_id IS NULL) != (group_registration_id IS NULL))',
         "A result belongs to an application or to a group mobility enrolment."),
    ]

    application_id = fields.Many2one(required=False)
    group_registration_id = fields.Many2one(string="Enrolment", comodel_name='ems.erasmus.group.registration',
                                            ondelete='restrict', index=True)

    @api.depends('group_registration_id.partner_id')
    def _compute_partner_id(self):
        super()._compute_partner_id()
        for line in self.filtered('group_registration_id'):
            line.partner_id = line.group_registration_id.partner_id


class ResUsers(models.Model):
    _inherit = 'res.users'

    def _ems_sync_erasmus_group_teacher_group(self):
        """*Erasmus+ > My group mobilities* is for whoever leads or accompanies a group mobility
        (ems.group_erasmus_group_teacher, managed by EMS only)."""
        group = self.env.ref('ems.group_erasmus_group_teacher')
        mobilities = self.env['ems.erasmus.group.mobility'].sudo().search([
            '|', ('leader_id.user_id', 'in', self.ids), ('companion_ids.user_id', 'in', self.ids)])
        assigned = mobilities.leader_id.user_id | mobilities.companion_ids.user_id
        (self & (assigned - group.users)).sudo().write({'groups_id': [(4, group.id)]})
        ((self - assigned) & group.users).sudo().write({'groups_id': [(3, group.id)]})


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def _ems_erasmus_group_mobilities(self):
        """Issue #701: the group mobilities this student sees on the portal: those enrolling for one
        of their groups, and those they enrolled in (withdrawn included) or take part in."""
        self.ensure_one()
        Mobility = self.env['ems.erasmus.group.mobility'].sudo()
        if self.contact_type not in ('student', 'alumni'):
            return Mobility
        mobilities = Mobility.search([('state', '=', 'enrolment'), ('group_ids', 'in', self.main_group_id.ids)]) \
            if self.main_group_id else Mobility
        return mobilities | Mobility.search([('state', 'not in', ('draft', 'cancelled')), '|',
                                             ('registration_ids.partner_id', '=', self.id),
                                             ('participant_ids.partner_id', '=', self.id)])

    def _ems_erasmus_guardian_group_participants(self):
        """Issue #703: the group mobility files of the minors this family acts for, whose commitment
        letter it accepts too (pending, or already accepted)."""
        self.ensure_one()
        Participant = self.env['ems.erasmus.group.participant'].sudo()
        if self.contact_type != 'family':
            return Participant
        students = self.get_portal_students().filtered(self._ems_portal_can_act_for)
        return Participant.search([('partner_id', 'in', students.ids), ('role', '=', 'student'),
                                   ('state', '=', 'active'),
                                   ('group_mobility_id.state', 'in', FILE_STATES)]).filtered(
            lambda participant: participant.commitment_guardian_pending or participant.commitment_guardian_signed_date)

    def _ems_erasmus_portal_visible(self):
        return super()._ems_erasmus_portal_visible() or bool(self._ems_erasmus_group_mobilities()) \
            or bool(self._ems_erasmus_guardian_group_participants())
