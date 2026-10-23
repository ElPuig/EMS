# -*- coding: utf-8 -*-

from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from .application import STAFF_ACTIVITIES
from .call import PROJECTS

# A mobility still going on: its place is held and a graduate keeps the portal (issue #687).
OPEN_STATES = ('choosing', 'preparing')
STAGES = [('preparation', "Before leaving"), ('return', "On return")]
PROPOSAL_FIELDS = ('proposal_activity', 'proposal_host', 'proposal_contact', 'proposal_country_id', 'proposal_city',
                   'proposal_date_start', 'proposal_date_end', 'proposal_notes')
# What the Direction writes on a staff proposal before validating or rejecting it.
DECISION_FIELDS = {'decision_note'}
# A KA131-HED stay of this many days or fewer is a short blended mobility: it has a virtual component.
SHORT_BLENDED_MAX_DAYS = 30
# A student's stay: curricular work placement (sBID, with academic recognition), or not.
PLACEMENT_TYPES = [('curricular', "Curricular work placement (sBID)"), ('extracurricular', "Extracurricular"),
                   ('graduate', "Recent graduate")]
TASK_REQUIREMENTS = [('required', "Required"), ('short_blended', "Short blended mobilities only")]


class EmsErasmusDestination(models.Model):
    """Issue #687 - a destination the centre offers in a modality of a students' call, with its
    places and the levels it suits (art. 15 of the students' call)."""
    _name = 'ems.erasmus.destination'
    _description = 'Erasmus+ destination'
    _order = 'call_id, modality_id, sequence, id'

    call_id = fields.Many2one(string="Call", comodel_name='ems.erasmus.call', required=True, ondelete='cascade',
                              index=True)
    modality_id = fields.Many2one(string="Modality", comodel_name='ems.erasmus.call.modality', required=True,
                                  ondelete='cascade', domain="[('call_id', '=', call_id)]")
    sequence = fields.Integer(string="Sequence", default=10)
    name = fields.Char(string="Name", required=True)
    country_id = fields.Many2one(string="Country", comodel_name='res.country')
    city = fields.Char(string="City")
    places = fields.Integer(string="Places")
    level_ids = fields.Many2many(string="Levels", comodel_name='ems.level',
                                 help="The levels whose students this destination suits. Empty: every level of the "
                                      "modality.")
    date_start = fields.Date(string="Start")
    date_end = fields.Date(string="End")
    host_partner_ids = fields.Many2many(string="Host entities", comodel_name='res.partner',
                                        domain="[('is_erasmus_host', '=', True)]")
    notes = fields.Text(string="Notes", help="Shown to the students when they choose.")
    mobility_ids = fields.One2many(string="Mobilities", comodel_name='ems.erasmus.mobility',
                                   inverse_name='destination_id')
    free_places = fields.Integer(string="Free places", compute='_compute_free_places')

    @api.depends('places', 'mobility_ids.state')
    def _compute_free_places(self):
        for destination in self:
            taken = destination.mobility_ids.filtered(lambda mobility: mobility.state != 'cancelled')
            destination.free_places = destination.places - len(taken)

    @api.constrains('modality_id', 'call_id')
    def _check_modality(self):
        for destination in self:
            if destination.modality_id.call_id != destination.call_id:
                raise ValidationError(_("A destination belongs to a modality of its own call."))

    def _ems_suits(self, mobility):
        """Free and suitable for `mobility`'s level and modality."""
        self.ensure_one()
        return (self.modality_id == mobility.modality_id and self.free_places > 0
                and (not self.level_ids or mobility.level_id in self.level_ids))


class EmsErasmusCallTask(models.Model):
    """Issue #687 - a step of the checklist of a mobility that is not a document (preparation
    sessions, OLS, EU Survey...), for every modality or only some."""
    _name = 'ems.erasmus.call.task'
    _description = 'Erasmus+ call checklist step'
    _order = 'call_id, stage, sequence, id'

    call_id = fields.Many2one(string="Call", comodel_name='ems.erasmus.call', required=True, ondelete='cascade',
                              index=True)
    sequence = fields.Integer(string="Sequence", default=10)
    name = fields.Char(string="Name", required=True)
    stage = fields.Selection(string="When", selection=STAGES, required=True, default='preparation')
    requirement = fields.Selection(string="Requirement", selection=TASK_REQUIREMENTS, required=True, default='required',
                                   help="Short blended mobilities only: KA131-HED stays of 30 days or fewer (e.g. "
                                        "the virtual component).")
    modality_ids = fields.Many2many(string="Only for modalities", comodel_name='ems.erasmus.call.modality',
                                    domain="[('call_id', '=', call_id)]", help="Empty: every modality.")
    project = fields.Selection(string="Only for project", selection=PROJECTS,
                               help="Only for the modalities of this project. Empty: both projects.")
    description = fields.Text(string="Instructions", help="Shown to the participant on the portal.")


class EmsErasmusMobility(models.Model):
    """Issue #687 - what happens after a place is accepted: the destination (chosen by turns on the
    portal, or an own proposal the Erasmus team validates; for staff, the activity the Director
    validates), the host entity and dates, and the documents and checklist before leaving and on
    return. See docs/en/developers/erasmus/erasmus.md."""
    _name = 'ems.erasmus.mobility'
    _description = 'Erasmus+ mobility'
    _inherit = ['ems.base']
    _order = 'call_id desc, modality_id, rank, id'
    _sql_constraints = [
        ('application_unique', 'unique(application_id)', "An application has only one mobility."),
    ]

    application_id = fields.Many2one(string="Application", comodel_name='ems.erasmus.application', required=True,
                                     ondelete='restrict', index=True, readonly=True)
    call_id = fields.Many2one(string="Call", related='application_id.call_id', store=True, index=True)
    audience = fields.Selection(string="Applicants", related='application_id.audience', store=True)
    partner_id = fields.Many2one(string="Participant", related='application_id.partner_id', store=True, index=True)
    modality_id = fields.Many2one(string="Modality", related='application_id.modality_id', store=True)
    rank = fields.Integer(string="Rank", related='application_id.rank', store=True)
    level_id = fields.Many2one(string="Level", comodel_name='ems.level', readonly=True,
                               help="The participant's level when the place was accepted: which destinations suit.")
    state = fields.Selection(string="State", required=True, default='choosing', tracking=True, readonly=True,
                             selection=[('choosing', "Defining the mobility"), ('preparing', "Preparing"),
                                        ('done', "Closed"), ('cancelled', "Cancelled")])
    cancel_reason = fields.Text(string="Reason for cancelling", tracking=True)

    # Students: destination choice by turns (art. 15).
    destination_id = fields.Many2one(string="Destination", comodel_name='ems.erasmus.destination', readonly=True,
                                     tracking=True, domain="[('call_id', '=', call_id)]")
    turn_deadline = fields.Datetime(string="Choose before", readonly=True,
                                    help="Set while it is this participant's turn to choose the destination.")
    turn_missed = fields.Boolean(string="Missed their turn", readonly=True,
                                 help="Did not choose in their turn: chooses among the destinations left once the "
                                      "others have chosen.")
    free_choice = fields.Boolean(string="Choosing among what is left", readonly=True,
                                 help="Missed their turn and the others have already chosen: can choose any destination "
                                      "still free, without a deadline.")

    # Own proposal (students) or the activity proposal (staff), and its decision.
    proposal_state = fields.Selection(string="Proposal", readonly=True, tracking=True, selection=[
        ('pending', "Waiting for validation"), ('validated', "Validated"), ('rejected', "Not validated")])
    proposal_activity = fields.Selection(string="Proposed activity", selection=STAFF_ACTIVITIES)
    proposal_host = fields.Char(string="Proposed host entity or course")
    proposal_contact = fields.Char(string="Host contact", help="Name and email of the person at the host entity.")
    proposal_country_id = fields.Many2one(string="Proposed country", comodel_name='res.country')
    proposal_city = fields.Char(string="Proposed city")
    proposal_date_start = fields.Date(string="Proposed start")
    proposal_date_end = fields.Date(string="Proposed end")
    proposal_notes = fields.Text(string="Proposal notes")
    proposal_attachment_ids = fields.Many2many(string="Proposal files", comodel_name='ir.attachment',
                                               relation='ems_erasmus_mobility_proposal_attachment_rel',
                                               help="Students: the host entity's written commitment.")
    proposal_date = fields.Datetime(string="Proposal sent on", readonly=True)
    decision_note = fields.Text(string="Comment on the decision",
                                help="Required to reject a proposal, optional to validate it; the participant reads "
                                     "it on the portal and in the email.")
    decided_by_id = fields.Many2one(string="Decided by", comodel_name='res.users', readonly=True)
    decision_date = fields.Datetime(string="Decided on", readonly=True)

    # The mobility as it will happen.
    country_id = fields.Many2one(string="Country", comodel_name='res.country', tracking=True)
    city = fields.Char(string="City", tracking=True)
    host_partner_id = fields.Many2one(string="Host entity", comodel_name='res.partner', tracking=True,
                                      domain="[('is_erasmus_host', '=', True)]")
    host_contact_id = fields.Many2one(string="Host contact person", comodel_name='res.partner',
                                      domain="[('parent_id', '=', host_partner_id)]")
    date_start = fields.Date(string="Start", tracking=True)
    date_end = fields.Date(string="End", tracking=True)
    project_kind = fields.Selection(string="Project of the modality", related='modality_id.project')
    placement_type = fields.Selection(
        string="Placement type", selection=PLACEMENT_TYPES, compute='_compute_placement_type', store=True,
        readonly=False, tracking=True,
        help="Students: a curricular work placement managed in sBID requires the sBID documents and, in KA131-HED, "
             "the recognition of ECTS credits; an extracurricular stay or a recent graduate's does not.")
    is_short_blended = fields.Boolean(
        string="Short blended mobility", compute='_compute_is_short_blended',
        help="KA131-HED stay of 30 days or fewer: it has a virtual component.")
    project_id = fields.Many2one(string="Project", comodel_name='ems.erasmus.project', tracking=True,
                                 domain="[('kind', '=', project_kind)]",
                                 help="The Erasmus+ project the mobility is charged to: CFGM on a KA121-VET project, "
                                      "CFGS on a KA131-HED one.")
    commitment_signed_date = fields.Datetime(string="Commitment letter signed on", readonly=True)
    commitment_signed_by_id = fields.Many2one(string="Commitment letter signed by", comodel_name='res.users',
                                              readonly=True)
    commitment_signed_ip = fields.Char(string="Signed from IP address", readonly=True)
    commitment_signed_text = fields.Html(string="Commitment letter signed", readonly=True, sanitize=True,
                                         help="The text accepted, as it was when it was signed.")
    commitment_pending = fields.Boolean(string="Commitment letter pending", compute='_compute_commitment_pending')
    commitment_guardian_signed_date = fields.Datetime(string="Signed by the family on", readonly=True)
    commitment_guardian_signed_by_id = fields.Many2one(string="Signed by the family member", comodel_name='res.users',
                                                       readonly=True)
    commitment_guardian_signed_ip = fields.Char(string="Family signed from IP address", readonly=True)
    commitment_guardian_pending = fields.Boolean(
        string="Family signature pending", compute='_compute_commitment_pending',
        help="A minor student's commitment letter is signed by their family too, on its own portal.")
    destination_date = fields.Date(string="Destination set on", readonly=True,
                                   help="When the destination was chosen, agreed or validated: the documents before "
                                        "leaving are due counting from it.")

    document_ids = fields.One2many(string="Documents", comodel_name='ems.erasmus.application.document',
                                   inverse_name='mobility_id')
    task_ids = fields.One2many(string="Checklist", comodel_name='ems.erasmus.mobility.task',
                               inverse_name='mobility_id')
    leave_id = fields.Many2one(string="Training absence", comodel_name='hr.leave', readonly=True, copy=False,
                               help="Staff: the absence for training EMS requests for the dates the Direction "
                                    "validated, approved as any other absence.")
    leave_declaration = fields.Boolean(
        string="Responsible declaration", readonly=True,
        help="Staff: given when sending the proposal; it is the staff member's declaration on the absence for "
             "training EMS requests once the Direction validates the dates.")
    preparation_complete = fields.Boolean(string="Ready to leave", compute='_compute_complete')
    return_complete = fields.Boolean(string="Return complete", compute='_compute_complete')
    can_validate = fields.Boolean(string="Can validate the proposal", compute='_compute_can_validate')

    # Issue #697: the grant, the services the centre pays out of it, and what the Secretary transfers.
    currency_id = fields.Many2one(string="Currency", comodel_name='res.currency', compute='_compute_currency_id')
    grant_amount = fields.Monetary(string="Grant", tracking=True,
                                   help="The participant's grant, as calculated in the Beneficiary Module.")
    prefinancing_percent = fields.Float(string="Prefinancing (%)", default=80.0, tracking=True,
                                        help="Part of the grant paid before leaving; the rest, on return. 100: a "
                                             "single payment.")
    provision_ids = fields.One2many(string="Provision of services", comodel_name='ems.erasmus.provision',
                                    inverse_name='mobility_id',
                                    help="What the centre pays directly out of the grant: flights, accommodation, "
                                         "course fees...")
    provision_amount = fields.Monetary(string="Paid by the centre", compute='_compute_grant_net')
    grant_net = fields.Monetary(string="To transfer to the participant", compute='_compute_grant_net',
                                help="The grant minus the services the centre pays directly.")
    payment_ids = fields.One2many(string="Payments", comodel_name='ems.erasmus.payment', inverse_name='mobility_id')
    can_request_prefinancing = fields.Boolean(string="Can request the first payment",
                                              compute='_compute_can_request_payment')
    can_request_final = fields.Boolean(string="Can request the final payment", compute='_compute_can_request_payment')
    host_contact_email = fields.Char(string="Contact person's email", related='host_contact_id.email')

    @api.depends('call_id.commitment_text', 'commitment_signed_date', 'commitment_guardian_signed_date',
                 'partner_id.birth_date')
    def _compute_commitment_pending(self):
        for mobility in self:
            letter = bool(mobility.call_id.commitment_text)
            mobility.commitment_pending = letter and not mobility.commitment_signed_date
            mobility.commitment_guardian_pending = (
                letter and mobility.audience == 'student' and not mobility.partner_id.is_adult
                and not mobility.commitment_guardian_signed_date)

    @api.depends('audience')
    def _compute_placement_type(self):
        """A student's stay is a curricular work placement unless the team says otherwise."""
        for mobility in self:
            mobility.placement_type = mobility.placement_type or (mobility.audience == 'student' and 'curricular')

    @api.depends('project_kind', 'date_start', 'date_end')
    def _compute_is_short_blended(self):
        for mobility in self:
            mobility.is_short_blended = bool(
                mobility.project_kind == 'ka131_hed' and mobility.date_start and mobility.date_end
                and (mobility.date_end - mobility.date_start).days + 1 <= SHORT_BLENDED_MAX_DAYS)

    @api.depends('document_ids.review_state', 'document_ids.is_required', 'document_ids.prepared_attachment_ids',
                 'task_ids.done', 'task_ids.is_required', 'commitment_pending', 'commitment_guardian_pending')
    def _compute_complete(self):
        """A document the team provides is complete once it is uploaded; the others, once valid.
        Before leaving, the commitment letter must be signed too (also by the family of a minor)."""
        for mobility in self:
            for stage in ('preparation', 'return'):
                lines = mobility.document_ids.filtered(lambda line: line.stage == stage and line.is_required)
                tasks = mobility.task_ids.filtered(lambda task: task.stage == stage and task.is_required)
                mobility[f'{stage}_complete'] = (
                    all(line.prepared_attachment_ids if line.handled_by == 'team' else line.review_state == 'valid'
                        for line in lines)
                    and all(tasks.mapped('done'))
                    and not (stage == 'preparation'
                             and (mobility.commitment_pending or mobility.commitment_guardian_pending)))

    @api.constrains('project_id', 'modality_id')
    def _check_project(self):
        for mobility in self:
            kind = mobility.modality_id.project
            if mobility.project_id and kind and mobility.project_id.kind != kind:
                raise ValidationError(_("The mobility of %(name)s goes on a %(kind)s project.", name=mobility.partner_id.name,
                                        kind=dict(self.env['ems.erasmus.project']._fields['kind'].selection)[kind]))

    def _compute_currency_id(self):
        self.currency_id = self.env.company.currency_id

    @api.depends('grant_amount', 'provision_ids.amount')
    def _compute_grant_net(self):
        for mobility in self:
            mobility.provision_amount = sum(mobility.provision_ids.mapped('amount'))
            mobility.grant_net = mobility.grant_amount - mobility.provision_amount

    @api.depends('payment_ids.kind', 'grant_amount')
    def _compute_can_request_payment(self):
        for mobility in self:
            first = mobility.payment_ids.filtered(lambda payment: payment.kind in ('prefinancing', 'single'))
            mobility.can_request_prefinancing = bool(mobility.grant_amount) and not first
            mobility.can_request_final = bool(first) and not mobility.payment_ids.filtered(
                lambda payment: payment.kind == 'final')

    @api.onchange('host_partner_id')
    def _onchange_host_partner_id(self):
        """Issue #697: the host entity's tutor, when it has only one contact."""
        if self.host_contact_id.parent_id != self.host_partner_id:
            self.host_contact_id = self._ems_single_contact(self.host_partner_id)

    @api.constrains('prefinancing_percent')
    def _check_prefinancing_percent(self):
        for mobility in self:
            if not 0 < mobility.prefinancing_percent <= 100:
                raise ValidationError(_("The prefinancing is a percentage above 0 and up to 100."))

    @api.depends_context('uid')
    @api.depends('audience')
    def _compute_can_validate(self):
        for mobility in self:
            mobility.can_validate = mobility._ems_can_validate()

    def _compute_display_name(self):
        for mobility in self:
            mobility.display_name = f"{mobility.partner_id.name} - {mobility.call_id.name}"

    def write(self, vals):
        if not self.env.su and not self.env.context.get('ems_erasmus_state'):
            touched = set(vals)
            if touched & DECISION_FIELDS and not (self._ems_can_manage() or all(
                    mobility._ems_can_validate() for mobility in self)):
                raise AccessError(_("Only who validates the proposal writes the reason of the decision."))
            if touched - DECISION_FIELDS and not self._ems_can_manage():
                raise AccessError(_("Only the Erasmus team changes a mobility."))
        result = super().write(vals)
        if {'date_start', 'date_end', 'state'} & set(vals):
            self._ems_sync_training_leave()
        return result

    # --- creation ----------------------------------------------------------------------------

    @api.model
    def _ems_create_for(self, applications):
        """A mobility for each application whose place was just accepted. Staff start with a
        proposal filled from their application, which they complete with the exact dates and send
        to the Direction from the portal."""
        mobilities = self.sudo().create([{
            'application_id': application.id,
            'level_id': application.partner_id.main_group_id.level_id.id,
            **(application.audience == 'staff' and {
                'proposal_activity': application.staff_activity, 'proposal_host': application.host_entity,
                'proposal_city': application.destination, 'proposal_notes': application.preferred_dates,
            } or {}),
        } for application in applications])
        mobilities._ems_sync_requirements()
        mobilities.call_id.filtered('choice_open')._ems_advance_choice()
        return mobilities

    def _ems_sync_requirements(self):
        """Add the preparation and return documents and checklist steps of the call that apply to
        the mobility's modality and are still missing. Never removes a line."""
        Line = self.env['ems.erasmus.application.document'].sudo()
        Task = self.env['ems.erasmus.mobility.task'].sudo()
        for mobility in self:
            call, modality = mobility.call_id, mobility.modality_id

            def applies(record):
                return (not record.modality_ids or modality in record.modality_ids) and \
                    (not record.project or record.project == modality.project)

            documents = call.preparation_document_ids.filtered(applies) - mobility.document_ids.call_document_id
            Line.create([{'application_id': mobility.application_id.id, 'mobility_id': mobility.id,
                          'call_document_id': document.id} for document in documents])
            tasks = call.task_ids.filtered(applies) - mobility.task_ids.call_task_id
            Task.create([{'mobility_id': mobility.id, 'call_task_id': task.id} for task in tasks])

    def action_sync_requirements(self):
        """After changing the call's documents or checklist, or a staff member's modality."""
        self._ems_check_manager()
        self.filtered(lambda mobility: mobility.state in OPEN_STATES)._ems_sync_requirements()

    # --- destination choice (students, art. 15) -----------------------------------------------

    def _ems_choosing(self):
        """Mobilities choosing a centre destination: not waiting for an own proposal's validation."""
        return self.filtered(lambda mobility: mobility.state == 'choosing' and mobility.audience == 'student'
                             and mobility.proposal_state != 'pending')

    def action_choose_destination(self, destination):
        """The participant chooses `destination` during their turn (portal)."""
        self.ensure_one()
        if not (self in self._ems_choosing() and (self.turn_deadline or self.free_choice)):
            raise UserError(_("It is not your turn to choose a destination."))
        if self.turn_deadline and self.turn_deadline <= self.call_id._ems_now():
            raise UserError(_("Your turn to choose has ended."))
        if not destination._ems_suits(self):
            raise UserError(_("This destination has no place for you."))
        self._ems_assign(destination)
        self.call_id._ems_advance_choice()

    @api.model
    def _ems_single_contact(self, host):
        """The host entity's tutor, when it has only one contact."""
        contacts = host.child_ids.filtered(lambda contact: contact.type == 'contact')
        return contacts if len(contacts) == 1 else contacts.browse()

    def _ems_assign(self, destination):
        """The destination's place, dates and, when it has only one, its host entity (and tutor)."""
        host = destination.host_partner_ids
        host_vals = {'host_partner_id': host.id, 'host_contact_id': self._ems_single_contact(host).id} \
            if len(host) == 1 else {}
        self._ems_set_state('preparing', destination_id=destination.id, turn_deadline=False,
                            country_id=destination.country_id.id, city=destination.city,
                            date_start=destination.date_start, date_end=destination.date_end, **host_vals)
        self._ems_send('ems.email_template_erasmus_mobility_assigned')

    def action_agree_destination(self):
        """The Erasmus team sets the destination it agreed with the participant (e.g. one through
        an intermediary organisation, when none of the centre's suited them, art. 15): the place,
        host entity and dates written on the mobility."""
        self._ems_check_manager()
        for mobility in self:
            if mobility.state != 'choosing':
                raise UserError(_("The destination of %s is already set.", mobility.partner_id.name))
            if not mobility.country_id:
                raise UserError(_("Write the country of the destination first."))
        self._ems_activities_done()
        for mobility in self:
            mobility._ems_set_state('preparing', turn_deadline=False, free_choice=False,
                                    **(mobility.proposal_state == 'pending' and {'proposal_state': False} or {}))
        self._ems_send('ems.email_template_erasmus_mobility_assigned')
        self.call_id.filtered('choice_open')._ems_advance_choice()

    @api.model
    def _cron_expire_turns(self):
        """No answer in the turn: the turn passes to the next one, and this participant chooses
        among the destinations left once the others have chosen (art. 15). The place is kept."""
        Call = self.env['ems.erasmus.call']
        expired = self.sudo().search([('state', '=', 'choosing'), ('turn_deadline', '<=', Call._ems_now())])
        expired.with_context(ems_erasmus_state=True).write({'turn_deadline': False, 'turn_missed': True})
        for mobility in expired:
            mobility.chatter(_("No destination chosen in the turn: chooses among what is left at the end."))
        expired.call_id._ems_advance_choice()

    # --- proposals -----------------------------------------------------------------------------

    def _ems_can_change_proposal(self):
        """Staff can change a validated activity (another course, other dates) until it starts:
        the Direction validates the change again (issue #697)."""
        self.ensure_one()
        return self.audience == 'staff' and self.state == 'preparing' and self.proposal_state != 'pending' and (
            not self.date_start or self.date_start > self.env['ems.datetime_utils'].get_local_today())

    def _ems_portal_propose(self, values, files=(), declaration=False):
        """The participant sends a proposal: a student, their own destination with the host's
        written commitment; staff, their activity with its exact dates, again after a rejection,
        or a change of the validated one before it starts (it stays as validated until then)."""
        self.ensure_one()
        changing = self._ems_can_change_proposal()
        if not changing and (self.state != 'choosing' or self.proposal_state == 'pending'):
            raise UserError(_("You cannot send a proposal now."))
        values = {key: value for key, value in values.items() if key in PROPOSAL_FIELDS}
        if values.get('proposal_activity') not in (False, None, *dict(STAFF_ACTIVITIES)):
            raise UserError(_("Choose one of the activities of the call."))
        if not (values.get('proposal_host') and values.get('proposal_country_id')):
            raise UserError(_("Say the host entity and the country."))
        if self.audience == 'student' and not (files or self.proposal_attachment_ids):
            raise UserError(_("Upload the host entity's written commitment."))
        start, end = values.get('proposal_date_start'), values.get('proposal_date_end')
        if self.audience == 'staff' and not (start and end):
            raise UserError(_("Say the exact start and end dates."))
        if start and end and fields.Date.to_date(end) < fields.Date.to_date(start):
            raise UserError(_("The end date cannot be before the start date."))
        if self.audience == 'staff':
            if not declaration:
                raise UserError(_("Accept the responsible declaration first."))
            values['leave_declaration'] = True
        attachments = self.env['ir.attachment'].sudo().create([{
            'name': name, 'raw': content, 'res_model': self._name, 'res_id': self.id} for name, content in files])
        self._ems_set_state(self.state if changing else 'choosing', **values, proposal_state='pending',
                            turn_deadline=False, proposal_date=fields.Datetime.now(), decision_note=False,
                            decided_by_id=False, decision_date=False,
                            proposal_attachment_ids=[(4, attachment.id) for attachment in attachments])
        self._ems_ask_validation()
        self.call_id._ems_advance_choice()

    def action_request_revalidation(self):
        """The Erasmus team changed a staff member's validated proposal in the backend: the
        Direction validates it again."""
        self._ems_check_manager()
        for mobility in self:
            if not mobility._ems_can_change_proposal():
                raise UserError(_("Only a staff activity already decided and not started yet is validated again."))
        self._ems_set_state('preparing', proposal_state='pending', proposal_date=fields.Datetime.now(),
                            decision_note=False, decided_by_id=False, decision_date=False)
        self._ems_ask_validation()

    def action_validate_proposal(self):
        for mobility in self:
            mobility._ems_check_decision()
        self._ems_activities_done()
        for mobility in self:
            mobility._ems_set_state('preparing', proposal_state='validated', decided_by_id=self.env.uid,
                                    decision_date=fields.Datetime.now(), country_id=mobility.proposal_country_id.id,
                                    city=mobility.proposal_city, date_start=mobility.proposal_date_start,
                                    date_end=mobility.proposal_date_end)
        self._ems_sync_requirements()
        staff = self.filtered(lambda mobility: mobility.audience == 'staff')
        staff._ems_send('ems.email_template_erasmus_proposal_validated')
        (self - staff)._ems_send('ems.email_template_erasmus_mobility_assigned')

    def action_reject_proposal(self):
        """Not validated, with a reason: a student goes back to the centre's destinations; staff
        propose another activity on the portal."""
        for mobility in self:
            mobility._ems_check_decision()
            if not (mobility.decision_note or '').strip():
                raise UserError(_("Write the reason of the decision first."))
        self._ems_activities_done()
        self.sudo().with_context(ems_erasmus_state=True).write({
            'proposal_state': 'rejected', 'decided_by_id': self.env.uid, 'decision_date': fields.Datetime.now()})
        self._ems_send('ems.email_template_erasmus_proposal_rejected')
        self.call_id.filtered('choice_open')._ems_advance_choice()

    def _ems_check_decision(self):
        self.ensure_one()
        if not self._ems_can_validate():
            raise AccessError(_("Only the Direction validates a staff activity, and the Erasmus team a student's "
                                "own destination."))
        if self.state not in ('choosing', 'preparing') or self.proposal_state != 'pending':
            raise UserError(_("There is no proposal waiting for validation."))

    def _ems_can_validate(self):
        """Staff activities: the call's Direction (staff call art. 4, `_ems_validators`); a
        student's own destination: the Erasmus team (students' call art. 15). The administrator,
        always."""
        self.ensure_one()
        user = self.env.user
        if self.env.su or user.has_group('ems.group_academic_admin'):
            return True
        if self.audience == 'staff':
            return user in self._ems_validators()
        return user.has_group('ems.group_erasmus')

    def _ems_validators(self):
        """Who validates the proposal. Staff: the call's Direction (`validator_ids`: the Director
        and the Head of Studies of FP, whatever the organisation chart says), never the participant
        themselves; without anyone, the administrators. Students: the Erasmus team."""
        self.ensure_one()
        if self.audience != 'staff':
            return self.env['ems.erasmus.call']._ems_erasmus_team()
        users = self.sudo().call_id.validator_ids - self.sudo().application_id.employee_id.user_id
        return users or self.env['res.users'].sudo().search(
            [('groups_id', '=', self.env.ref('ems.group_academic_admin').id), ('share', '=', False)])

    def _ems_ask_validation(self):
        activity_type = self.env.ref('mail.mail_activity_data_todo')
        for mobility in self:
            for user in mobility._ems_validators():
                mobility.sudo().activity_schedule(
                    activity_type_id=activity_type.id, user_id=user.id,
                    summary=_("Erasmus+: validate the proposal of %s", mobility.partner_id.name))

    def _ems_activities_done(self):
        self.sudo().activity_ids.action_feedback()

    # --- preparation and return ---------------------------------------------------------------

    @api.model
    def _cron_remind_documents(self):
        """Weekly: remind every participant preparing a mobility of the documents still missing or
        needing changes (the European Health Insurance Card above all) and of the commitment letter
        still to sign; and the family of a minor, of the letter it has to sign too."""
        mobilities = self.sudo().search([('state', '=', 'preparing')])
        mobilities.filtered(lambda mobility: mobility._ems_documents_to_correct() or mobility.commitment_pending)._ems_send(
            'ems.email_template_erasmus_mobility_documents')
        mobilities._ems_remind_guardians()

    def _ems_remind_guardians(self):
        """Email the family of each minor student whose commitment letter it still has to sign."""
        template = self.env.ref('ems.email_template_erasmus_commitment_guardian')
        for mobility in self.filtered('commitment_guardian_pending'):
            for family in mobility.partner_id._ems_family_contacts().filtered('email'):
                template.with_context(lang=family.lang).sudo().send_mail(
                    mobility.id, force_send=False, email_values={'email_to': family.email})

    def action_sign_commitment(self, accepted=False, ip_address=False, guardian=False):
        """The participant, or the family of a minor (`guardian`), accepts and signs the commitment
        letter (annex 3) in EMS, from the portal; in any order. The text is kept as it was at the
        first signature, which is what the second one signs, with who, when and from where."""
        self.ensure_one()
        prefix = 'commitment_guardian_' if guardian else 'commitment_'
        if self.state not in OPEN_STATES or not self[f'{prefix}pending']:
            raise UserError(_("There is no commitment letter to sign."))
        if not accepted:
            raise UserError(_("Tick that you accept the commitments first."))
        self.with_context(ems_erasmus_state=True).sudo().write({
            f'{prefix}signed_date': fields.Datetime.now(), f'{prefix}signed_by_id': self.env.uid,
            f'{prefix}signed_ip': ip_address, 'commitment_signed_text': self._ems_commitment_text()})
        self.chatter(_("Commitment letter accepted and signed in EMS by the family.") if guardian
                     else _("Commitment letter accepted and signed in EMS."))

    def _ems_commitment_text(self):
        """The commitment letter to sign: as it was signed first, or the call's current one."""
        return self.commitment_signed_text or self.call_id.commitment_text

    def action_notify_documents(self):
        """Email the participant the documents still missing or needing changes."""
        self._ems_check_manager()
        for mobility in self:
            if mobility.state != 'preparing':
                raise UserError(_("Only a mobility in preparation has documents to ask for."))
            if not mobility._ems_documents_to_correct():
                raise UserError(_("No document of %s is missing or needs changes.", mobility.partner_id.name))
        self._ems_send('ems.email_template_erasmus_mobility_documents')

    def _ems_portal_upload(self, uploads):
        """Files the participant uploads from the portal: {call document id: [(name, bytes)]},
        while the mobility is open."""
        self.ensure_one()
        if self.state not in OPEN_STATES:
            raise UserError(_("The documents of this mobility can no longer be changed."))
        lines = {line.call_document_id.id: line for line in self.document_ids if line.handled_by != 'team'}
        for document_id, files in uploads.items():
            if files and document_id in lines:
                lines[document_id]._ems_add_files(files)

    def _ems_choices(self):
        """The destinations the participant can choose now."""
        self.ensure_one()
        return self.call_id.destination_ids.filtered(lambda destination: destination._ems_suits(self))

    def _ems_sync_training_leave(self):
        """Staff: once the Direction has validated the dates, request the absence for training
        (ems.leave_type_training) for them, with the declaration the staff member gave with the
        proposal; whoever approves their absences approves it as usual. A request not decided yet
        follows the dates and is withdrawn if the mobility is cancelled; a decided one is left alone
        and the team is told to correct it."""
        for mobility in self.filtered(lambda mobility: mobility.audience == 'staff'):
            leave = mobility.leave_id.sudo()
            pending = leave and leave.state in ('confirm', 'validate1')
            if mobility.state == 'cancelled':
                if pending:
                    leave.unlink()
                elif leave and leave.state == 'validate':
                    mobility.chatter(_("The mobility was cancelled: cancel its training absence too."))
                continue
            if mobility.state != 'preparing' or not (mobility.date_start and mobility.date_end):
                continue
            dates = {'request_date_from': mobility.date_start, 'request_date_to': mobility.date_end}
            if (not leave or leave.state in ('refuse', 'cancel')) and mobility.leave_declaration:
                leave = self.env['hr.leave'].sudo().create({
                    'employee_id': mobility.application_id.employee_id.id,
                    'holiday_status_id': self.env.ref('ems.leave_type_training').id,
                    'private_name': _("Erasmus+ mobility: %s", mobility.call_id.name),
                    'ems_full_day': True, 'ems_submitted': True, 'ems_responsible_declaration': True, **dates})
                mobility.with_context(ems_erasmus_state=True).sudo().leave_id = leave
            elif leave and (leave.request_date_from, leave.request_date_to) != (mobility.date_start, mobility.date_end):
                if pending:
                    leave.write(dates)
                else:
                    mobility.chatter(_("The dates of the mobility changed: correct its training absence too."))

    def _ems_documents_to_correct(self):
        """The documents missing or needing changes: those before leaving, and those on return
        once the mobility has ended; one the team fills in, only once it is uploaded to sign."""
        self.ensure_one()
        ended = self.date_end and self.date_end <= self.env['ems.datetime_utils'].get_local_today()
        return self.document_ids.filtered(lambda line: (
            (line.stage == 'preparation' or ended) and line.handled_by != 'team'
            and (line.handled_by != 'team_to_sign' or line.prepared_attachment_ids)
            and (line.review_state == 'needs_change' or (line.is_required and not line.attachment_ids))))

    def action_request_prefinancing(self):
        """Issue #697: the first payment for the Secretary, the prefinancing percentage of what
        the participant receives (a single payment at 100 %)."""
        self._ems_check_manager()
        for mobility in self:
            if not mobility.can_request_prefinancing:
                raise UserError(_("The first payment of %s is already requested, or the grant is not set.",
                                  mobility.partner_id.name))
            kind = 'single' if mobility.prefinancing_percent >= 100 else 'prefinancing'
            mobility._ems_request_payment(kind, mobility.grant_net * mobility.prefinancing_percent / 100)

    def action_request_final_payment(self):
        """Issue #697: the rest, on return: what the participant receives minus what was already
        requested, so a change of the grant or the services after the prefinancing lands here."""
        self._ems_check_manager()
        for mobility in self:
            if not mobility.can_request_final:
                raise UserError(_("Request the first payment of %s before the final one, and only once.",
                                  mobility.partner_id.name))
            mobility._ems_request_payment('final', mobility.grant_net - sum(mobility.payment_ids.mapped('amount')))

    def _ems_request_payment(self, kind, amount):
        self.ensure_one()
        amount = self.currency_id.round(amount)
        if self.currency_id.compare_amounts(amount, 0) <= 0:
            raise UserError(_("There is nothing to pay to %s: check the grant and the services the centre pays.",
                              self.partner_id.name))
        self.env['ems.erasmus.payment'].create({'mobility_id': self.id, 'kind': kind, 'amount': amount})

    def action_close(self):
        """The participant is back and every return document and step is done."""
        self._ems_check_manager()
        for mobility in self:
            if mobility.state != 'preparing':
                raise UserError(_("Only a mobility in preparation can be closed."))
            if not mobility.return_complete:
                raise UserError(_("Every required return document of %s must be valid and every return step done.",
                                  mobility.partner_id.name))
        for mobility in self:
            mobility._ems_set_state('done')
        self.partner_id._ems_erasmus_release_graduate()

    def action_cancel(self):
        """The team cancels the mobility (e.g. travel documents not handed in on time, art. 17)."""
        self._ems_check_manager()
        for mobility in self:
            if not (mobility.cancel_reason or '').strip():
                raise UserError(_("Write the reason for cancelling first."))
        self._ems_cancel(False)

    def action_renounce(self, reason=False):
        """The participant renounces the place from the portal (art. 18 of the call)."""
        self._ems_cancel(reason or _("Renounced by the participant."))

    def _ems_cancel(self, reason):
        """Cancel and free the place: the offer stops holding it, so the team can offer it to the
        next reserve with the usual wizard (never automatic)."""
        for mobility in self:
            if mobility.state not in OPEN_STATES:
                raise UserError(_("The mobility of %s is no longer open.", mobility.partner_id.name))
        self._ems_activities_done()
        for mobility in self:
            mobility._ems_set_state('cancelled', turn_deadline=False,
                                    **(reason and {'cancel_reason': reason} or {}))
            mobility.application_id.offer_ids.filtered(lambda offer: offer.state == 'accepted').sudo().write(
                {'state': 'renounced'})
            mobility.application_id._ems_set_state('renounced')
        self.partner_id._ems_erasmus_release_graduate()
        self.call_id.filtered('choice_open')._ems_advance_choice()

    def _ems_portal_grant(self):
        """Issue #697: the grant as the participant reads it on the portal (art. 5 of the calls:
        what the centre pays directly and what they receive): the provisions as (label, amount),
        the payments as (label, state label, amount, paid date)."""
        self.ensure_one()
        Provision, Payment = self.env['ems.erasmus.provision'], self.env['ems.erasmus.payment']
        concepts = dict(Provision._fields['concept']._description_selection(self.env))
        kinds = dict(Payment._fields['kind']._description_selection(self.env))
        states = dict(Payment._fields['state']._description_selection(self.env))
        provisions = [(" - ".join(filter(None, [concepts[provision.concept], provision.description])), provision.amount)
                      for provision in self.provision_ids]
        payments = [(kinds[payment.kind], states[payment.state], payment.amount, payment.paid_date)
                    for payment in self.payment_ids]
        return provisions, payments

    # --- helpers -----------------------------------------------------------------------------

    def _ems_set_state(self, state, **vals):
        mobilities = self.with_context(ems_erasmus_state=True).sudo()
        if state == 'preparing' and 'destination_date' not in vals:
            # Set when the destination is; a change validated later keeps it.
            mobilities.filtered(lambda mobility: not mobility.destination_date).destination_date = \
                self.env['ems.datetime_utils'].get_local_today()
        mobilities.write({'state': state, **vals})
        if state == 'preparing':
            self._ems_remind_guardians()

    def _ems_can_manage(self):
        return self.env['ems.erasmus.application']._ems_can_manage()

    def _ems_check_manager(self):
        if not self._ems_can_manage():
            raise AccessError(_("Only the Erasmus team manages the mobilities."))

    def _ems_send(self, xmlid):
        self.env['ems.erasmus.application']._ems_mail(self, xmlid)

    def _ems_mail_document_list(self):
        return self.env['ems.erasmus.application']._ems_mail_document_list(self._ems_documents_to_correct())

    def _ems_local_format(self, value):
        return self.env['ems.erasmus.call']._ems_local_format(value)


class EmsErasmusMobilityTask(models.Model):
    """Issue #687 - one checklist step of a mobility, ticked by the Erasmus team."""
    _name = 'ems.erasmus.mobility.task'
    _description = 'Erasmus+ mobility checklist step'
    _order = 'mobility_id, stage, sequence, id'
    _sql_constraints = [
        ('mobility_task_unique', 'unique(mobility_id, call_task_id)', "A step appears once in a mobility."),
    ]

    mobility_id = fields.Many2one(string="Mobility", comodel_name='ems.erasmus.mobility', required=True,
                                  ondelete='cascade', index=True)
    call_task_id = fields.Many2one(string="Step", comodel_name='ems.erasmus.call.task', required=True,
                                   ondelete='restrict')
    name = fields.Char(string="Name", related='call_task_id.name')
    description = fields.Text(string="Instructions", related='call_task_id.description')
    stage = fields.Selection(string="When", related='call_task_id.stage', store=True)
    sequence = fields.Integer(string="Sequence", related='call_task_id.sequence', store=True)
    is_required = fields.Boolean(string="Required", compute='_compute_is_required')
    done = fields.Boolean(string="Done")
    done_user_id = fields.Many2one(string="Ticked by", comodel_name='res.users', readonly=True)
    done_date = fields.Datetime(string="Ticked on", readonly=True)
    note = fields.Char(string="Note")

    @api.depends('call_task_id.requirement', 'mobility_id.is_short_blended')
    def _compute_is_required(self):
        """A short blended step (the virtual component) only counts in a short KA131-HED stay."""
        for task in self:
            requirement = task.call_task_id.requirement
            task.is_required = requirement != 'short_blended' or task.mobility_id.is_short_blended

    def write(self, vals):
        if 'done' in vals:
            vals.update({'done_user_id': vals['done'] and self.env.uid, 'done_date': vals['done'] and fields.Datetime.now()})
        return super().write(vals)
