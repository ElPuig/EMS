# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools import float_round

# What the centre may pay directly out of a participant's grant (issue #697).
CONCEPTS = [('travel', "Travel"), ('accommodation', "Accommodation"), ('course', "Course fees"), ('other', "Other")]
PAYMENT_KINDS = [('prefinancing', "Prefinancing"), ('final', "Final payment"), ('single', "Single payment")]
# Only action_mark_paid()/action_mark_unpaid() write them.
PAYMENT_STATE_FIELDS = {'state', 'paid_date', 'paid_by_id'}


class EmsErasmusProvision(models.Model):
    """Issue #697 - part of a participant's grant the centre pays directly (flights,
    accommodation, course fees...): deducted from what the participant receives. Usually one
    share of an invoice, split among the participants it covers."""
    _name = 'ems.erasmus.provision'
    _description = 'Erasmus+ provision of services'
    _order = 'mobility_id, id'

    mobility_id = fields.Many2one(string="Mobility", comodel_name='ems.erasmus.mobility', required=True,
                                  ondelete='cascade', index=True)
    partner_id = fields.Many2one(string="Participant", related='mobility_id.partner_id', store=True)
    invoice_id = fields.Many2one(string="Invoice", comodel_name='ems.erasmus.invoice', ondelete='cascade', index=True)
    concept = fields.Selection(string="Concept", selection=CONCEPTS, required=True, default='travel')
    description = fields.Char(string="Description")
    currency_id = fields.Many2one(string="Currency", related='mobility_id.currency_id')
    amount = fields.Monetary(string="Amount", required=True)


class EmsErasmusInvoice(models.Model):
    """Issue #697 - a supplier's invoice the centre paid for some participants (e.g. the group's
    flights and accommodation). Its amount is split equally among them as provisions of services,
    each share editable afterwards."""
    _name = 'ems.erasmus.invoice'
    _description = 'Erasmus+ invoice'
    _order = 'date desc, id desc'

    name = fields.Char(string="Invoice number", required=True)
    supplier_id = fields.Many2one(string="Supplier", comodel_name='res.partner')
    date = fields.Date(string="Date", default=lambda self: self.env['ems.datetime_utils'].get_local_today())
    concept = fields.Selection(string="Concept", selection=CONCEPTS, required=True, default='travel')
    description = fields.Char(string="Description")
    project_id = fields.Many2one(string="Project", comodel_name='ems.erasmus.project')
    currency_id = fields.Many2one(string="Currency", comodel_name='res.currency',
                                  default=lambda self: self.env.company.currency_id)
    amount = fields.Monetary(string="Amount", required=True)
    document = fields.Binary(string="Invoice file", attachment=True)
    document_filename = fields.Char(string="Invoice file name")
    mobility_ids = fields.Many2many(string="Participants", comodel_name='ems.erasmus.mobility',
                                    relation='ems_erasmus_invoice_mobility_rel',
                                    help="Who the invoice covers: its amount is split equally among them.")
    provision_ids = fields.One2many(string="Shares", comodel_name='ems.erasmus.provision', inverse_name='invoice_id')
    unassigned_amount = fields.Monetary(string="Not assigned", compute='_compute_unassigned_amount',
                                        help="The invoice's amount minus its shares: zero once fully assigned.")

    @api.depends('amount', 'provision_ids.amount')
    def _compute_unassigned_amount(self):
        for invoice in self:
            invoice.unassigned_amount = invoice.amount - sum(invoice.provision_ids.mapped('amount'))

    @api.model_create_multi
    def create(self, vals_list):
        invoices = super().create(vals_list)
        invoices._ems_split()
        return invoices

    def write(self, vals):
        result = super().write(vals)
        if {'amount', 'mobility_ids'} & set(vals):
            self._ems_split()
        elif {'concept', 'description'} & set(vals):
            for invoice in self:
                invoice.provision_ids.write({'concept': invoice.concept, 'description': invoice._ems_share_description()})
        return result

    def _ems_split(self):
        """One equal share per participant, the cents left over on the first one: a change of
        the amount or the participants splits it again from scratch."""
        for invoice in self:
            invoice.provision_ids.unlink()
            mobilities = invoice.mobility_ids
            if not mobilities:
                continue
            share = float_round(invoice.amount / len(mobilities), precision_rounding=invoice.currency_id.rounding,
                                rounding_method='DOWN')
            remainder = invoice.amount - share * len(mobilities)
            self.env['ems.erasmus.provision'].create([{
                'invoice_id': invoice.id, 'mobility_id': mobility.id, 'concept': invoice.concept,
                'description': invoice._ems_share_description(), 'amount': share + (remainder if index == 0 else 0),
            } for index, mobility in enumerate(mobilities)])

    def _ems_share_description(self):
        self.ensure_one()
        return self.description or _("Invoice %s", self.name)


class EmsErasmusPayment(models.Model):
    """Issue #697 - an amount of a participant's grant the Secretary transfers to their bank
    account: a prefinancing before leaving and the rest on return, or a single payment when the
    prefinancing is 100 %. Requested by the Erasmus team from the mobility; the Secretary marks it
    paid."""
    _name = 'ems.erasmus.payment'
    _description = 'Erasmus+ grant payment'
    _order = 'state desc, request_date, id'

    mobility_id = fields.Many2one(string="Mobility", comodel_name='ems.erasmus.mobility', required=True,
                                  ondelete='restrict', index=True)
    partner_id = fields.Many2one(string="Participant", related='mobility_id.partner_id', store=True, index=True)
    call_id = fields.Many2one(string="Call", related='mobility_id.call_id', store=True)
    project_id = fields.Many2one(string="Project", related='mobility_id.project_id', store=True)
    kind = fields.Selection(string="Payment", selection=PAYMENT_KINDS, required=True)
    currency_id = fields.Many2one(string="Currency", related='mobility_id.currency_id')
    amount = fields.Monetary(string="Amount", required=True)
    request_date = fields.Date(string="Requested on", readonly=True,
                               default=lambda self: self.env['ems.datetime_utils'].get_local_today())
    state = fields.Selection(string="State", required=True, default='to_pay', readonly=True,
                             selection=[('to_pay', "To pay"), ('paid', "Paid")])
    paid_date = fields.Date(string="Paid on", readonly=True)
    paid_by_id = fields.Many2one(string="Marked paid by", comodel_name='res.users', readonly=True)
    bank_account = fields.Char(string="IBAN", compute='_compute_bank_account')
    bank_holder = fields.Char(string="Account holder", compute='_compute_bank_account')

    def _compute_bank_account(self):
        """The participant's first bank account, the one EMS keeps from enrolment (a family's,
        for a minor, may be in the guardian's name)."""
        for payment in self:
            bank = payment.partner_id.sudo().bank_ids[:1]
            payment.bank_account = bank.acc_number
            payment.bank_holder = bank.acc_holder_name or (payment.partner_id.name if bank else False)

    def write(self, vals):
        if not self.env.su and not self.env.context.get('ems_erasmus_payment_state'):
            if PAYMENT_STATE_FIELDS & set(vals):
                raise AccessError(_("A payment is marked as paid from its own button."))
            if self.filtered(lambda payment: payment.state == 'paid'):
                raise UserError(_("A paid payment cannot change."))
        return super().write(vals)

    def unlink(self):
        if self.filtered(lambda payment: payment.state == 'paid'):
            raise UserError(_("A paid payment cannot be deleted."))
        return super().unlink()

    def action_mark_paid(self):
        self._ems_check_payer()
        self.filtered(lambda payment: payment.state == 'to_pay').with_context(ems_erasmus_payment_state=True).sudo().write({
            'state': 'paid', 'paid_by_id': self.env.uid,
            'paid_date': self.env['ems.datetime_utils'].get_local_today()})

    def action_mark_unpaid(self):
        self._ems_check_payer()
        self.filtered(lambda payment: payment.state == 'paid').with_context(ems_erasmus_payment_state=True).sudo().write({
            'state': 'to_pay', 'paid_by_id': False, 'paid_date': False})

    def _ems_check_payer(self):
        """The Secretary pays; the administrator is above every role."""
        user = self.env.user
        if not (user.has_group('ems.group_secretary') or user.has_group('ems.group_academic_admin')):
            raise AccessError(_("Only the Secretary marks a grant payment as paid."))
