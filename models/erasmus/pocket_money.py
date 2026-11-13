# -*- coding: utf-8 -*-
"""Issue #764 - the pocket money of a group mobility's participants: what is left of each one's
grant once the group's collective invoices are split equally among them, transferred by the
Secretary as an ordinary grant payment. See docs/en/developers/erasmus/economy.md."""

from collections import defaultdict

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import formatLang

from .economy import ECONOMY_READERS
from .grant import PAYERS, _secretary_users
from .group_mobility import FILE_STATES
from .payee import check_prefinancing_percent, group_iban, normalize_iban, split_amount

# Who reads a participant's grant and pocket money: also the group's leader and accompanying teachers.
POCKET_READERS = f'{ECONOMY_READERS},ems.group_erasmus_group_teacher'
POCKET_STATES = [('none', "Not requested"), ('to_pay', "To pay"), ('paid', "Paid")]
# When the pocket money can be requested: once the selection is approved, the final part on return.
FIRST_STATES = FILE_STATES + ('done',)
FINAL_STATES = ('return', 'done')
BANK_FIELDS = ('bank_account', 'bank_holder')


class EmsErasmusGroupParticipant(models.Model):
    _name = 'ems.erasmus.group.participant'
    _inherit = ['ems.erasmus.group.participant', 'ems.erasmus.payee']

    payment_ids = fields.One2many(string="Payments", comodel_name='ems.erasmus.payment',
                                  inverse_name='group_participant_id', groups=f'{PAYERS},ems.group_director')
    invoice_share = fields.Monetary(string="Paid directly by the centre", compute='_compute_pocket',
                                    groups=POCKET_READERS,
                                    help="The group's collective invoices divided equally among the participants "
                                         "taking part.")
    pocket_amount = fields.Monetary(string="Pocket money", compute='_compute_pocket', groups=POCKET_READERS,
                                    help="The pocket money (art. 16 of the call), what is transferred to the "
                                         "participant: their grant minus their share of the collective invoices.")
    pocket_requested = fields.Monetary(string="Requested", compute='_compute_pocket', groups=POCKET_READERS)
    pocket_paid = fields.Monetary(string="Transferred", compute='_compute_pocket', groups=POCKET_READERS)
    pocket_state = fields.Selection(string="Pocket money state", selection=POCKET_STATES, compute='_compute_pocket',
                                    groups=POCKET_READERS)
    bank_account = fields.Char(string="IBAN", groups=PAYERS, tracking=True,
                               help="The account the pocket money goes to. Empty: the contact's bank account (a "
                                    "student's, from the enrolment).")
    bank_holder = fields.Char(string="Account holder", groups=PAYERS)

    @api.depends('grant_amount', 'state', 'group_mobility_id.invoice_ids.amount',
                 'group_mobility_id.participant_ids.state', 'payment_ids.amount', 'payment_ids.state')
    def _compute_pocket(self):
        shares = defaultdict(float)
        for group in self.sudo().group_mobility_id:
            active = group.participant_ids.filtered(lambda participant: participant.state == 'active')
            for invoice in group.invoice_ids:
                for participant, share in zip(active, split_amount(invoice.amount, len(active), invoice.currency_id)):
                    shares[participant.id] += share
        for participant in self:
            payments = participant.sudo().payment_ids
            participant.invoice_share = shares[participant.id]
            participant.pocket_amount = participant.sudo().grant_amount - participant.invoice_share
            participant.pocket_requested = sum(payments.mapped('amount'))
            participant.pocket_paid = sum(payments.filtered(lambda payment: payment.state == 'paid').mapped('amount'))
            participant.pocket_state = 'none' if not payments else \
                'to_pay' if payments.filtered(lambda payment: payment.state == 'to_pay') else 'paid'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'bank_account' in vals:
                vals['bank_account'] = normalize_iban(vals['bank_account'])
        return super().create(vals_list)

    def write(self, vals):
        if 'bank_account' in vals:
            vals['bank_account'] = normalize_iban(vals['bank_account'])
        return super().write(vals)

    # ems.erasmus.payee
    def _ems_payee_depends(self):
        return super()._ems_payee_depends() + ['payment_ids.kind', 'grant_amount', 'state']

    def _ems_payee_granted(self):
        return self.state == 'active' and self.currency_id.compare_amounts(self.sudo().pocket_amount, 0) > 0

    def _ems_payee_amount(self):
        return self.sudo().pocket_amount

    def _ems_payee_percent(self):
        return self.group_mobility_id.prefinancing_percent

    def _ems_payee_link(self):
        return {'group_participant_id': self.id}

    def _ems_payee_check_state(self):
        if self.state != 'active' or self.group_mobility_id.state not in FIRST_STATES:
            raise UserError(_("No pocket money can be requested for %s in this state of the group mobility.",
                              self.partner_id.name))

    def _ems_payee_bank(self):
        """The account the participant gave, or else the contact's."""
        participant = self.sudo()
        if iban := participant.bank_account:
            return group_iban(iban), participant.bank_holder or participant.partner_id.name
        return super()._ems_payee_bank()

    def _ems_payee_deductions(self):
        share = self.sudo().invoice_share
        return [(_("your share of the group's collective expenses"), share)] if share else []

    def _ems_portal_set_bank(self, bank_account, bank_holder):
        """The participant gives the account for their pocket money (from the portal)."""
        self.ensure_one()
        self.sudo().write({'bank_account': bank_account, 'bank_holder': (bank_holder or '').strip()[:200] or False})


class EmsErasmusGroupMobility(models.Model):
    _inherit = 'ems.erasmus.group.mobility'

    prefinancing_percent = fields.Float(string="Pocket money before leaving (%)", default=100.0, tracking=True,
                                        help="Part of each participant's pocket money paid before leaving; the rest, "
                                             "on return. 100: a single payment.")
    no_direct_costs = fields.Boolean(string="The centre pays nothing directly", tracking=True,
                                     help="No collective invoice: each participant receives their whole grant as "
                                          "pocket money.")
    # Issue #784 (9.15): the same choice asked in positive, as the team reads it on the form.
    travel_paid_by = fields.Selection(
        string="Who pays the travel and accommodation", compute='_compute_travel_paid_by',
        inverse='_inverse_travel_paid_by',
        selection=[('centre', "The centre"), ('participant', "Each participant")],
        help="Each participant: no collective invoice, everyone receives their whole grant as pocket money.")

    # Issue #790 (11.10): the group's pocket money, in the order of the individual mobility's grant.
    pocket_total = fields.Monetary(string="To transfer", compute='_compute_pocket_totals', groups=POCKET_READERS,
                                   help="The pocket money of the participants taking part: their grants minus what the "
                                        "centre pays directly.")
    pocket_paid_total = fields.Monetary(string="Transferred", compute='_compute_pocket_totals', groups=POCKET_READERS)
    pocket_pending_total = fields.Monetary(string="Pending transfer", compute='_compute_pocket_totals',
                                           groups=POCKET_READERS)

    # Issue #787 (9.17, 9.16): what the team must not miss before paying, on top of the form.
    grant_missing = fields.Char(string="Participants without a grant", compute='_compute_pocket_warnings',
                                groups=ECONOMY_READERS)
    pocket_negative = fields.Char(string="Participants with negative pocket money",
                                  compute='_compute_pocket_warnings', groups=ECONOMY_READERS)

    @api.depends('participant_ids.state', 'participant_ids.grant_amount', 'invoice_ids.amount',
                 'participant_ids.payment_ids.amount', 'participant_ids.payment_ids.state')
    def _compute_pocket_totals(self):
        for mobility in self:
            active = mobility.sudo().participant_ids.filtered(lambda participant: participant.state == 'active')
            mobility.pocket_total = sum(active.mapped('pocket_amount'))
            mobility.pocket_paid_total = sum(active.mapped('pocket_paid'))
            mobility.pocket_pending_total = max(mobility.pocket_total - mobility.pocket_paid_total, 0.0)

    @api.depends('participant_ids.state', 'participant_ids.grant_amount', 'invoice_ids.amount')
    def _compute_pocket_warnings(self):
        for mobility in self:
            active = mobility.sudo().participant_ids.filtered(lambda participant: participant.state == 'active')
            mobility.grant_missing = ", ".join(active.filtered(
                lambda participant: not participant.grant_amount).partner_id.mapped('name'))
            mobility.pocket_negative = ", ".join(active.filtered(
                lambda participant: participant.currency_id.compare_amounts(participant.pocket_amount, 0) < 0
            ).partner_id.mapped('name'))

    @api.depends('no_direct_costs')
    def _compute_travel_paid_by(self):
        for mobility in self:
            mobility.travel_paid_by = 'participant' if mobility.no_direct_costs else 'centre'

    def _inverse_travel_paid_by(self):
        for mobility in self:
            mobility.no_direct_costs = mobility.travel_paid_by == 'participant'

    @api.constrains('prefinancing_percent')
    def _check_prefinancing_percent(self):
        check_prefinancing_percent(self)

    @api.constrains('no_direct_costs', 'invoice_ids')
    def _check_no_direct_costs(self):
        for mobility in self:
            if mobility.no_direct_costs and mobility.sudo().invoice_ids:
                raise ValidationError(_("The centre pays nothing directly in %s: it cannot have collective invoices. "
                                        "Remove them, or choose that the centre pays the travel and "
                                        "accommodation.", mobility.name))

    @api.onchange('no_direct_costs', 'travel_paid_by')
    def _onchange_no_direct_costs(self):
        if self.travel_paid_by == 'participant' and self.invoice_ids:
            return {'warning': {'title': _("Collective invoices"), 'message': _(
                "This group mobility has collective invoices: remove them first, the centre pays nothing directly.")}}

    def action_request_pocket_money(self):
        """The team asks the Secretary for every participant's first pocket money payment, once
        the selection is approved; the Secretary gets one task for the whole group."""
        self._ems_check_role('team')
        self._ems_check_state(*FIRST_STATES)
        self._ems_request_pocket_money(lambda participant: participant.can_request_prefinancing,
                                       '_ems_first_payment_vals')

    def action_request_final_pocket_money(self):
        """The rest of the pocket money, on return."""
        self._ems_check_role('team')
        for mobility in self:
            if mobility.state not in FINAL_STATES:
                raise UserError(_("The final pocket money of %s is requested on return.", mobility.name))
        self._ems_request_pocket_money(
            lambda participant: participant.can_request_final and participant.currency_id.compare_amounts(
                participant.pocket_amount - participant.pocket_requested, 0) > 0,
            '_ems_final_payment_vals')

    def _ems_request_pocket_money(self, can_request, vals_method):
        vals_list = []
        for mobility in self:
            participants = mobility.sudo().participant_ids.filtered(
                lambda participant: participant.state == 'active').filtered(can_request)
            if not participants:
                raise UserError(_("There is no pocket money left to request in %s.", mobility.name))
            if missing := participants.filtered(lambda participant: not participant._ems_payee_bank()[0]):
                raise UserError(_("Add the bank account of %s first: students give it on the portal, teachers from "
                                  "My bank account on the group mobility, or the team in their file.",
                                  ", ".join(missing.mapped('partner_id.name'))))
            vals_list += getattr(participants, vals_method)()
        self.env['ems.erasmus.payment'].sudo().create(vals_list)

    def action_my_bank_account(self):
        """A leader or accompanying teacher gives the account for their own pocket money."""
        self.ensure_one()
        participant = self.sudo().participant_ids.filtered(
            lambda participant: participant.partner_id == self.env.user.partner_id and participant.role != 'student')
        if not participant:
            raise UserError(_("You do not take part in %s as a teacher.", self.name))
        return {'type': 'ir.actions.act_window', 'name': _("My bank account"), 'res_model': 'ems.erasmus.bank.wizard',
                'view_mode': 'form', 'target': 'new', 'context': {'default_group_participant_id': participant.id}}

    def _ems_sync_transfer_task(self):
        """One task for the Secretary per group with pocket money to pay, on the group's first
        payment still to pay (the Secretary does not open the group mobility): its summary says how
        many payments and how much, and it is done once nothing is left to pay."""
        activity_type = self.env.ref('ems.mail_activity_erasmus_transfer')
        Payment = self.env['ems.erasmus.payment'].sudo()
        for mobility in self.sudo():
            payments = Payment.search([('group_mobility_id', '=', mobility.id)])
            tasks = payments.activity_ids.filtered(lambda activity: activity.activity_type_id == activity_type)
            to_pay = payments.filtered(lambda payment: payment.state == 'to_pay')
            if not to_pay:
                tasks.action_feedback()
                continue
            anchor = to_pay.sorted('id')[:1]
            summary = _("Erasmus+: pay the pocket money of %(group)s (%(count)s payments, %(amount)s)",
                        group=mobility.name, count=len(to_pay),
                        amount=formatLang(self.env, sum(to_pay.mapped('amount')), currency_obj=mobility.currency_id))
            if tasks and set(tasks.mapped('res_id')) == {anchor.id}:
                tasks.write({'summary': summary})
                continue
            tasks.unlink()
            for user in _secretary_users(self.env):
                anchor.with_context(mail_activity_quick_update=True).activity_schedule(activity_type_id=activity_type.id, user_id=user.id, summary=summary)

    def action_close(self):
        """Also once every participant's pocket money and every collective invoice is paid."""
        self._ems_check_role('team')
        for mobility in self.sudo():
            participants = mobility.participant_ids.filtered(lambda participant: participant.state == 'active')
            if any(participant._ems_left_to_pay() for participant in participants) or \
                    mobility.invoice_ids.filtered(lambda invoice: invoice.state == 'to_pay'):
                raise UserError(_("Request and pay every participant's pocket money and every collective invoice of "
                                  "%s first.", mobility.name))
        return super().action_close()


class EmsErasmusInvoice(models.Model):
    _inherit = 'ems.erasmus.invoice'

    @api.constrains('group_mobility_id')
    def _check_no_direct_costs(self):
        for invoice in self:
            if invoice.group_mobility_id.no_direct_costs:
                raise ValidationError(_("The centre pays nothing directly in %s: it cannot have collective invoices.",
                                        invoice.group_mobility_id.name))


class EmsErasmusProject(models.Model):
    _inherit = 'ems.erasmus.project'

    def _ems_economy_warnings(self):
        """Also a group's collective invoices above a participant's grant, and a participant who
        withdrew after being paid."""
        warnings = super()._ems_economy_warnings()
        money = lambda amount: formatLang(self.env, amount, currency_obj=self.env.company.currency_id)
        for group in self.sudo().group_mobility_ids.filtered(lambda group: group.state != 'cancelled'):
            for participant in group.participant_ids:
                if participant.state == 'active' and participant.pocket_amount < 0:
                    warnings.append(_("The collective invoices of %(group)s are above the grant of %(name)s by "
                                      "%(over)s.", group=group.name, name=participant.partner_id.name,
                                      over=money(-participant.pocket_amount)))
                if participant.state == 'withdrawn' and participant.pocket_paid > 0:
                    warnings.append(_("%(name)s withdrew from %(group)s after being paid %(paid)s: record what they "
                                      "gave back in the group's \"Given back by the participant\".", name=participant.partner_id.name,
                                      group=group.name, paid=money(participant.pocket_paid)))
        return warnings


class EmsErasmusBankWizard(models.TransientModel):
    """A teacher of a group mobility gives the bank account for their own pocket money."""
    _name = 'ems.erasmus.bank.wizard'
    _description = 'Erasmus+ bank account for the pocket money'

    group_participant_id = fields.Many2one(string="Participant", comodel_name='ems.erasmus.group.participant',
                                           required=True, readonly=True)
    bank_account = fields.Char(string="IBAN", required=True)
    bank_holder = fields.Char(string="Account holder")

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        participant = self.env['ems.erasmus.group.participant'].sudo().browse(values.get('group_participant_id'))
        if participant and participant.partner_id == self.env.user.partner_id:
            values.update({name: participant[name] for name in BANK_FIELDS if name in fields_list and participant[name]})
        return values

    def action_confirm(self):
        self.ensure_one()
        participant = self.group_participant_id.sudo()
        if participant.partner_id != self.env.user.partner_id and participant.group_mobility_id._ems_role() != 'team':
            raise UserError(_("Only the participant gives their own bank account."))
        participant._ems_portal_set_bank(self.bank_account, self.bank_holder)
        return {'type': 'ir.actions.act_window_close'}
