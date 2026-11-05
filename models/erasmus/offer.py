# -*- coding: utf-8 -*-

from datetime import timedelta

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .resolution import FINAL_KINDS
from .workflow import check_applicant_action

# Offers that hold a place: waiting for an answer, or accepted.
HOLDING_STATES = ('pending', 'accepted')


class EmsErasmusOffer(models.Model):
    """Issue #685 - a place offered to an applicant and their answer. The selected get one when
    the definitive resolution is published; a place freed by a renunciation is offered to the
    next reserve only when the Erasmus team confirms it (wizard below), never on its own. No
    answer by the deadline counts as a renunciation (`_cron_expire_offers`). Every answer, and the
    lack of one, is confirmed to the applicant by email, with a copy to a minor's family."""
    _name = 'ems.erasmus.offer'
    _description = 'Erasmus+ place offer'
    _inherit = ['ems.base']
    _order = 'offer_date desc, id desc'

    application_id = fields.Many2one(string="Application", comodel_name='ems.erasmus.application', required=True,
                                     ondelete='restrict', index=True)
    call_id = fields.Many2one(string="Call", related='application_id.call_id', store=True)
    modality_id = fields.Many2one(string="Modality", related='application_id.modality_id', store=True)
    partner_id = fields.Many2one(string="Applicant", related='application_id.partner_id', store=True)
    rank = fields.Integer(string="Rank", related='application_id.rank')
    offer_date = fields.Datetime(string="Offered on", required=True, readonly=True, default=fields.Datetime.now)
    deadline = fields.Datetime(string="Answer before", required=True, readonly=True)
    from_reserve = fields.Boolean(string="Offered to a reserve", readonly=True)
    state = fields.Selection(string="State", required=True, default='pending', readonly=True, tracking=True,
                             selection=[('pending', "Waiting for an answer"), ('accepted', "Place accepted"),
                                        ('renounced', "Renounced"), ('expired', "No answer"),
                                        ('cancelled', "Withdrawn")])
    answer_date = fields.Datetime(string="Answered on", readonly=True)
    renounce_reason = fields.Text(string="Reason for renouncing", readonly=True)

    def _compute_display_name(self):
        for offer in self:
            offer.display_name = f"{offer.partner_id.name} - {offer.modality_id.name or offer.call_id.name}"

    @api.model
    def _ems_offer(self, applications, deadline, from_reserve=False, notify=True):
        """Offer a place to each of `applications`, to answer before `deadline`."""
        offers = self.sudo().create([{'application_id': application.id, 'deadline': deadline,
                                      'from_reserve': from_reserve} for application in applications])
        if notify:
            self.env['ems.erasmus.application']._ems_mail(offers, 'ems.email_template_erasmus_offer', family_copy=True)
        return offers

    def action_accept(self):
        """The applicant accepts in writing from the portal, before the deadline. Issue #687: the
        mobility starts."""
        check_applicant_action(self)
        self._ems_answer('accepted', 'accepted')
        self.env['ems.erasmus.mobility']._ems_create_for(self.application_id)
        self._ems_notify_tutor()

    def action_renounce(self, reason=False):
        check_applicant_action(self)
        self._ems_answer('renounced', 'renounced', renounce_reason=reason)
        self.call_id._ems_sync_free_place_tasks()

    def action_cancel(self):
        """The Erasmus team withdraws an offer still waiting for an answer (e.g. made by mistake)."""
        if not self.env['ems.erasmus.application']._ems_can_manage():
            raise UserError(_("Only the Erasmus team withdraws an offer."))
        if self.filtered(lambda offer: offer.state != 'pending'):
            raise UserError(_("Only an offer waiting for an answer can be withdrawn."))
        self.sudo().write({'state': 'cancelled'})

    def _ems_answer(self, state, application_state, **vals):
        now = fields.Datetime.now()
        for offer in self:
            if offer.state != 'pending':
                raise UserError(_("This offer has already been answered."))
            if offer.deadline <= offer.call_id._ems_now():
                raise UserError(_("The deadline to answer this offer has passed."))
        self.sudo().write({'state': state, 'answer_date': now, **vals})
        self.application_id._ems_set_state(application_state)
        self._ems_send_answer()

    def _ems_send_answer(self):
        """The applicant's proof of their answer, or of not answering in time."""
        self.env['ems.erasmus.application']._ems_mail(self, 'ems.email_template_erasmus_offer_answer', family_copy=True)

    def _ems_notify_tutor(self):
        """A student's group tutor learns that they will go on an Erasmus+ stay. Nothing for them
        to do, so a notice and not a to-do, on the student (as for a convalidation)."""
        for offer in self.sudo().filtered(lambda offer: offer.call_id.audience == 'student'):
            tutor = offer.partner_id.main_group_id.tutor_id.user_id
            if not tutor.active:
                continue
            student = offer.partner_id.with_context(lang=tutor.lang or self.env.lang)
            env = student.env
            student.message_notify(
                partner_ids=tutor.partner_id.ids,
                subject=env._("Erasmus+: %s", student.name),
                body=Markup("<p>{}</p>").format(env._(
                    "%(student)s has accepted a place in %(modality)s of the Erasmus+ call %(call)s. There is nothing "
                    "for you to do now: the Erasmus team will tell the teaching staff the dates of the stay once they "
                    "are set.", student=student.name, modality=offer.modality_id.name, call=offer.call_id.name)))

    @api.model
    def _cron_expire_offers(self):
        """No answer by the deadline = renounced (art. 15 of the call)."""
        Call = self.env['ems.erasmus.call']
        offers = self.sudo().search([('state', '=', 'pending'), ('deadline', '<=', Call._ems_now())])
        offers.write({'state': 'expired'})
        offers.application_id._ems_set_state('renounced')
        for offer in offers:
            offer.application_id.chatter(_("No answer to the place offer by the deadline: renounced."))
        offers._ems_send_answer()
        offers.call_id._ems_sync_free_place_tasks()


class EmsErasmusOfferWizard(models.TransientModel):
    """Issue #685 - offer a free place of a modality: EMS proposes the next reserve, the Erasmus
    team confirms it with a new deadline. A staff call offers its places as one pool, without a
    modality (issue #686)."""
    _name = 'ems.erasmus.offer.wizard'
    _description = 'Erasmus+ offer a free place'

    call_id = fields.Many2one(string="Call", comodel_name='ems.erasmus.call', required=True)
    audience = fields.Selection(string="Applicants", related='call_id.audience')
    modality_id = fields.Many2one(string="Modality", comodel_name='ems.erasmus.call.modality',
                                  domain="[('call_id', '=', call_id)]")
    free_places = fields.Integer(string="Free places", compute='_compute_application_id')
    application_id = fields.Many2one(string="Next reserve", comodel_name='ems.erasmus.application',
                                     compute='_compute_application_id')
    rank = fields.Integer(string="Rank", related='application_id.rank')
    deadline = fields.Datetime(string="Answer before", required=True)

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        call = self.env['ems.erasmus.call'].browse(values.get('call_id') or self.env.context.get('active_id'))
        if call:
            values['call_id'] = call.id
            values.setdefault('deadline', self._ems_answer_deadline(call))
            if call.audience == 'staff':
                return values
            modality = call.modality_ids.filtered(lambda modality: modality.free_places > 0
                                                  and modality.next_reserve_id)[:1]
            values.setdefault('modality_id', (modality or call.modality_ids[:1]).id)
        return values

    @api.depends('call_id', 'modality_id')
    def _compute_application_id(self):
        for wizard in self:
            call = wizard.call_id
            if not call or (call.audience == 'student' and not wizard.modality_id):
                wizard.update({'free_places': 0, 'application_id': False})
                continue
            wizard.free_places = call._ems_free_places(wizard.modality_id)
            wizard.application_id = call._ems_next_reserve(wizard.modality_id)

    @api.model
    def _ems_answer_deadline(self, call):
        """The 2026-11-04 usage test: a free place offered later gets as long to answer as the places
        of the definitive resolution had (from its publication to the acceptance deadline), or three
        days."""
        definitive = call.resolution_ids.filtered(lambda resolution: resolution.state == 'published'
                                                  and resolution.kind in FINAL_KINDS
                                                  and resolution.publish_date).sorted('publish_date')[:1]
        span = call.acceptance_deadline and definitive and call.acceptance_deadline - definitive.publish_date
        return call._ems_now() + (span if span and span > timedelta(0) else timedelta(days=3))

    def action_confirm(self):
        self.ensure_one()
        if self.call_id.audience == 'student' and not self.modality_id:
            raise UserError(_("Choose the modality of the free place."))
        if self.free_places <= 0:
            raise UserError(_("There is no free place."))
        if not self.application_id:
            raise UserError(_("There is no reserve left."))
        if self.deadline <= self.call_id._ems_now():
            raise UserError(_("The deadline must be in the future."))
        self.env['ems.erasmus.offer']._ems_offer(self.application_id, self.deadline, from_reserve=True)
        self.call_id._ems_sync_free_place_tasks()
        return {'type': 'ir.actions.act_window_close'}
