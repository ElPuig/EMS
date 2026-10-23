# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools import float_round

# What the centre may pay directly out of a participant's grant (issue #697).
CONCEPTS = [('travel', "Travel"), ('accommodation', "Accommodation"), ('course', "Course fees"), ('other', "Other")]
PAYMENT_KINDS = [('prefinancing', "Prefinancing"), ('final', "Final payment"), ('single', "Single payment")]
# Only the transfer wizard and action_mark_unpaid() write them.
PAYMENT_STATE_FIELDS = {'state', 'paid_date', 'paid_by_id', 'receipt_ids'}


def _check_transfer_fields(records, vals):
    """A payment or an invoice is paid, with its receipt, only through the transfer wizard."""
    if not records.env.su and not records.env.context.get('ems_erasmus_payment_state') \
            and PAYMENT_STATE_FIELDS & set(vals):
        raise AccessError(_("A payment is marked as paid by registering its transfer."))


def _transfer_wizard_action(records):
    _check_payer(records.env)
    return {
        'type': 'ir.actions.act_window', 'name': _("Register transfer"), 'res_model': 'ems.erasmus.transfer.wizard',
        'view_mode': 'form', 'target': 'new',
        'context': {f'default_{"payment" if records._name == "ems.erasmus.payment" else "invoice"}_ids': records.ids},
    }


def _check_payer(env):
    """The Secretary pays; the administrator is above every role."""
    if not (env.user.has_group('ems.group_secretary') or env.user.has_group('ems.group_academic_admin')):
        raise AccessError(_("Only the Secretary registers the transfers of the Erasmus+ grants and invoices."))


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
    state = fields.Selection(string="State", required=True, default='to_pay', readonly=True,
                             selection=[('to_pay', "To pay"), ('paid', "Paid")])
    paid_date = fields.Date(string="Paid on", readonly=True)
    paid_by_id = fields.Many2one(string="Marked paid by", comodel_name='res.users', readonly=True)
    receipt_ids = fields.Many2many(string="Transfer receipts", comodel_name='ir.attachment',
                                   relation='ems_erasmus_invoice_receipt_rel', readonly=True,
                                   help="Added by the Secretary when registering the transfer.")
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
        _check_transfer_fields(self, vals)
        result = super().write(vals)
        if {'amount', 'mobility_ids'} & set(vals):
            self._ems_split()
        elif {'concept', 'description'} & set(vals):
            for invoice in self:
                invoice.provision_ids.write({'concept': invoice.concept, 'description': invoice._ems_share_description()})
        return result

    def unlink(self):
        if self.filtered(lambda invoice: invoice.state == 'paid'):
            raise UserError(_("A paid invoice cannot be deleted."))
        return super().unlink()

    def action_register_transfer(self):
        return _transfer_wizard_action(self)

    def action_mark_unpaid(self):
        """Undo a transfer registered by mistake."""
        _check_payer(self.env)
        _mark_paid(self.filtered(lambda invoice: invoice.state == 'paid'), False)

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
    receipt_ids = fields.Many2many(string="Transfer receipts", comodel_name='ir.attachment',
                                   relation='ems_erasmus_payment_receipt_rel', readonly=True,
                                   help="Added by the Secretary when registering the transfer; one receipt can cover "
                                        "several payments.")
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
        _check_transfer_fields(self, vals)
        if not self.env.su and not self.env.context.get('ems_erasmus_payment_state') \
                and self.filtered(lambda payment: payment.state == 'paid'):
            raise UserError(_("A paid payment cannot change."))
        return super().write(vals)

    def unlink(self):
        if self.filtered(lambda payment: payment.state == 'paid'):
            raise UserError(_("A paid payment cannot be deleted."))
        return super().unlink()

    def action_register_transfer(self):
        return _transfer_wizard_action(self)

    def action_mark_unpaid(self):
        """Undo a transfer registered by mistake: back to pay, its receipts kept apart from it."""
        _check_payer(self.env)
        _mark_paid(self.filtered(lambda record: record.state == 'paid'), False)


def _mark_paid(records, paid_date, receipts=None):
    """Paid on `paid_date` with `receipts` added, or (paid_date False) back to pay without them."""
    vals = {'state': 'paid', 'paid_by_id': records.env.uid, 'paid_date': paid_date} if paid_date else \
        {'state': 'to_pay', 'paid_by_id': False, 'paid_date': False, 'receipt_ids': [(5, 0, 0)]}
    if paid_date and receipts:
        vals['receipt_ids'] = [(4, receipt.id) for receipt in receipts]
    records.with_context(ems_erasmus_payment_state=True).sudo().write(vals)


class EmsErasmusTransferWizard(models.TransientModel):
    """Issue #697 - the Secretary registers a bank transfer: the grant payments or the invoices it
    pays (one transfer can cover several, e.g. a batch of grants or a travel agency's invoice), its
    date and its receipt, which is kept on each of them for the project's dossier."""
    _name = 'ems.erasmus.transfer.wizard'
    _description = 'Erasmus+ transfer'

    payment_ids = fields.Many2many(string="Grant payments", comodel_name='ems.erasmus.payment',
                                   relation='ems_erasmus_transfer_wizard_payment_rel')
    invoice_ids = fields.Many2many(string="Invoices", comodel_name='ems.erasmus.invoice',
                                   relation='ems_erasmus_transfer_wizard_invoice_rel')
    date = fields.Date(string="Transfer date", required=True,
                       default=lambda self: self.env['ems.datetime_utils'].get_local_today())
    currency_id = fields.Many2one(string="Currency", comodel_name='res.currency',
                                  default=lambda self: self.env.company.currency_id)
    total = fields.Monetary(string="Total", compute='_compute_total')
    receipt = fields.Binary(string="Receipt", help="The bank's receipt of the transfer (PDF).")
    receipt_filename = fields.Char(string="Receipt file name")

    @api.depends('payment_ids.amount', 'invoice_ids.amount')
    def _compute_total(self):
        for wizard in self:
            wizard.total = sum(wizard.payment_ids.mapped('amount')) + sum(wizard.invoice_ids.mapped('amount'))

    def action_confirm(self):
        self.ensure_one()
        _check_payer(self.env)
        records = [records.filtered(lambda record: record.state == 'to_pay')
                   for records in (self.payment_ids, self.invoice_ids)]
        if not any(records):
            raise UserError(_("Everything selected is already paid."))
        receipt = self.receipt and self.env['ir.attachment'].sudo().create({
            'name': self.receipt_filename or _("Transfer receipt %s.pdf", self.date), 'datas': self.receipt,
            'res_model': (records[0] or records[1])._name, 'res_id': (records[0] or records[1])[:1].id})
        for paid in records:
            _mark_paid(paid, self.date, receipt)
        return {'type': 'ir.actions.act_window_close'}
