# -*- coding: utf-8 -*-

from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from .application import STAFF_ACTIVITIES

# A mobility still going on: its place is held and a graduate keeps the portal (issue #687).
OPEN_STATES = ('choosing', 'preparing')
STAGES = [('preparation', "Before leaving"), ('return', "On return")]
PROPOSAL_FIELDS = ('proposal_activity', 'proposal_host', 'proposal_contact', 'proposal_country_id', 'proposal_city',
                   'proposal_dates', 'proposal_notes')
# What the Director writes on a staff proposal before validating or rejecting it.
DECISION_FIELDS = {'decision_note'}


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
                                        domain="[('is_company', '=', True)]")
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
    modality_ids = fields.Many2many(string="Only for modalities", comodel_name='ems.erasmus.call.modality',
                                    domain="[('call_id', '=', call_id)]", help="Empty: every modality.")
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
                             selection=[('choosing', "Choosing the destination"), ('preparing', "Preparing"),
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
    proposal_dates = fields.Char(string="Proposed dates")
    proposal_notes = fields.Text(string="Proposal notes")
    proposal_attachment_ids = fields.Many2many(string="Proposal files", comodel_name='ir.attachment',
                                               relation='ems_erasmus_mobility_proposal_attachment_rel',
                                               help="Students: the host entity's written commitment.")
    proposal_date = fields.Datetime(string="Proposal sent on", readonly=True)
    decision_note = fields.Text(string="Reason of the decision",
                                help="Required to reject a proposal; the participant reads it on the portal.")
    decided_by_id = fields.Many2one(string="Decided by", comodel_name='res.users', readonly=True)
    decision_date = fields.Datetime(string="Decided on", readonly=True)

    # The mobility as it will happen.
    country_id = fields.Many2one(string="Country", comodel_name='res.country', tracking=True)
    city = fields.Char(string="City", tracking=True)
    host_partner_id = fields.Many2one(string="Host entity", comodel_name='res.partner', tracking=True,
                                      domain="[('is_company', '=', True)]")
    host_contact_id = fields.Many2one(string="Host contact person", comodel_name='res.partner',
                                      domain="[('parent_id', '=', host_partner_id)]")
    date_start = fields.Date(string="Start", tracking=True)
    date_end = fields.Date(string="End", tracking=True)

    document_ids = fields.One2many(string="Documents", comodel_name='ems.erasmus.application.document',
                                   inverse_name='mobility_id')
    task_ids = fields.One2many(string="Checklist", comodel_name='ems.erasmus.mobility.task',
                               inverse_name='mobility_id')
    preparation_deadline = fields.Datetime(string="Documents before leaving by",
                                           related='call_id.preparation_deadline')
    return_deadline = fields.Date(string="Return documents by", compute='_compute_return_deadline')
    preparation_complete = fields.Boolean(string="Ready to leave", compute='_compute_complete')
    return_complete = fields.Boolean(string="Return complete", compute='_compute_complete')
    can_validate = fields.Boolean(string="Can validate the proposal", compute='_compute_can_validate')

    @api.depends('date_end', 'call_id.return_days')
    def _compute_return_deadline(self):
        for mobility in self:
            mobility.return_deadline = mobility.date_end and mobility.date_end + timedelta(
                days=mobility.call_id.return_days)

    @api.depends('document_ids.review_state', 'document_ids.is_required', 'task_ids.done')
    def _compute_complete(self):
        for mobility in self:
            for stage in ('preparation', 'return'):
                lines = mobility.document_ids.filtered(lambda line: line.stage == stage and line.is_required)
                tasks = mobility.task_ids.filtered(lambda task: task.stage == stage)
                mobility[f'{stage}_complete'] = (all(line.review_state == 'valid' for line in lines)
                                                 and all(tasks.mapped('done')))

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
        return super().write(vals)

    # --- creation ----------------------------------------------------------------------------

    @api.model
    def _ems_create_for(self, applications):
        """A mobility for each application whose place was just accepted. Staff start with the
        activity they proposed in the application, waiting for the Director's validation."""
        mobilities = self.sudo().create([{
            'application_id': application.id,
            'level_id': application.partner_id.main_group_id.level_id.id,
            **(application.audience == 'staff' and {
                'proposal_state': 'pending', 'proposal_date': fields.Datetime.now(),
                'proposal_activity': application.staff_activity, 'proposal_host': application.host_entity,
                'proposal_city': application.destination, 'proposal_dates': application.preferred_dates,
            } or {}),
        } for application in applications])
        mobilities._ems_sync_requirements()
        mobilities.filtered('proposal_state')._ems_ask_validation()
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
                return not record.modality_ids or modality in record.modality_ids

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

    def _ems_assign(self, destination):
        self._ems_set_state('preparing', destination_id=destination.id, turn_deadline=False,
                            country_id=destination.country_id.id, city=destination.city,
                            date_start=destination.date_start, date_end=destination.date_end)
        self._ems_send('ems.email_template_erasmus_mobility_assigned')

    def action_back_to_reserve(self):
        """The participant rejects every destination with places, or is not available for any of
        them: back to the reserve list with their score; the place is offered to the next reserve
        by the team (art. 15)."""
        for mobility in self:
            if mobility not in mobility._ems_choosing():
                raise UserError(_("You can only go back to the reserve list while choosing the destination."))
        self._ems_cancel(_("Rejected the destinations with places: back to the reserve list."), 'returned', 'reserve')

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

    def _ems_portal_propose(self, values, files=()):
        """The participant sends a proposal: a student, their own destination with the host's
        written commitment; staff, a new activity after the Director rejected the previous one."""
        self.ensure_one()
        if self.state != 'choosing' or self.proposal_state == 'pending' or (
                self.audience == 'staff' and self.proposal_state != 'rejected'):
            raise UserError(_("You cannot send a proposal now."))
        values = {key: value for key, value in values.items() if key in PROPOSAL_FIELDS}
        if values.get('proposal_activity') not in (False, None, *dict(STAFF_ACTIVITIES)):
            raise UserError(_("Choose one of the activities of the call."))
        if not (values.get('proposal_host') and values.get('proposal_country_id')):
            raise UserError(_("Say the host entity and the country."))
        if self.audience == 'student' and not (files or self.proposal_attachment_ids):
            raise UserError(_("Upload the host entity's written commitment."))
        attachments = self.env['ir.attachment'].sudo().create([{
            'name': name, 'raw': content, 'res_model': self._name, 'res_id': self.id} for name, content in files])
        self._ems_set_state('choosing', **values, proposal_state='pending', turn_deadline=False,
                            proposal_date=fields.Datetime.now(), decision_note=False, decided_by_id=False,
                            decision_date=False, proposal_attachment_ids=[(4, attachment.id) for attachment in attachments])
        self._ems_ask_validation()
        self.call_id._ems_advance_choice()

    def action_validate_proposal(self):
        for mobility in self:
            mobility._ems_check_decision()
        self._ems_activities_done()
        for mobility in self:
            mobility._ems_set_state('preparing', proposal_state='validated', decided_by_id=self.env.uid,
                                    decision_date=fields.Datetime.now(), country_id=mobility.proposal_country_id.id,
                                    city=mobility.proposal_city)
        self._ems_sync_requirements()
        self._ems_send('ems.email_template_erasmus_mobility_assigned')

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
            raise AccessError(_("Only the Director validates a staff activity, and the Erasmus team a student's "
                                "own destination."))
        if self.state != 'choosing' or self.proposal_state != 'pending':
            raise UserError(_("There is no proposal waiting for validation."))

    def _ems_can_validate(self):
        """Staff activities: the Director (staff call art. 4); a student's own destination: the
        Erasmus team (students' call art. 15). The administrator, always."""
        self.ensure_one()
        user = self.env.user
        if self.env.su or user.has_group('ems.group_academic_admin'):
            return True
        if self.audience == 'staff':
            return user.has_group('ems.group_director')
        return user.has_group('ems.group_erasmus')

    def _ems_validators(self):
        self.ensure_one()
        group = self.env.ref('ems.group_director' if self.audience == 'staff' else 'ems.group_erasmus')
        return group.sudo().users.filtered(lambda user: not user.share)

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
        lines = {line.call_document_id.id: line for line in self.document_ids}
        for document_id, files in uploads.items():
            if files and document_id in lines:
                lines[document_id]._ems_add_files(files)

    def _ems_choices(self):
        """The destinations the participant can choose now."""
        self.ensure_one()
        return self.call_id.destination_ids.filtered(lambda destination: destination._ems_suits(self))

    def _ems_documents_to_correct(self):
        self.ensure_one()
        return self.document_ids.filtered(
            lambda line: line.review_state == 'needs_change' or (line.is_required and not line.attachment_ids))

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
        self._ems_cancel(False, 'renounced', 'renounced')

    def action_renounce(self, reason=False):
        """The participant renounces the place from the portal (art. 18 of the call)."""
        self._ems_cancel(reason or _("Renounced by the participant."), 'renounced', 'renounced')

    def _ems_cancel(self, reason, offer_state, application_state):
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
                {'state': offer_state})
            mobility.application_id._ems_set_state(application_state)
        self.partner_id._ems_erasmus_release_graduate()
        self.call_id.filtered('choice_open')._ems_advance_choice()

    # --- helpers -----------------------------------------------------------------------------

    def _ems_set_state(self, state, **vals):
        self.with_context(ems_erasmus_state=True).sudo().write({'state': state, **vals})

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
    done = fields.Boolean(string="Done")
    done_user_id = fields.Many2one(string="Ticked by", comodel_name='res.users', readonly=True)
    done_date = fields.Datetime(string="Ticked on", readonly=True)
    note = fields.Char(string="Note")

    def write(self, vals):
        if 'done' in vals:
            vals.update({'done_user_id': vals['done'] and self.env.uid, 'done_date': vals['done'] and fields.Datetime.now()})
        return super().write(vals)
