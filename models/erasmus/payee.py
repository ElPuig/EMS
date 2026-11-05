# -*- coding: utf-8 -*-
"""Who the Secretary transfers part of an Erasmus+ grant to: an individual mobility (issue #697)
or a participant of a group mobility (issue #764). See docs/en/developers/erasmus/economy.md."""

import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_round

FIRST_PAYMENT_KINDS = ('prefinancing', 'single')


def split_amount(amount, count, currency):
    """`amount` in `count` equal shares, rounded down, the cents left over on the first one (an
    invoice's shares among its participants)."""
    if not count:
        return []
    share = float_round(amount / count, precision_rounding=currency.rounding, rounding_method='DOWN')
    return [share + (amount - share * count if index == 0 else 0) for index in range(count)]


def normalize_iban(value):
    """`value` without spaces and in capitals, once its check digits are right (ISO 13616, mod 97);
    empty stays empty."""
    iban = re.sub(r'\s', '', value or '').upper()
    if not iban:
        return False
    if not re.fullmatch(r'[A-Z]{2}\d{2}[A-Z0-9]{10,30}', iban) or \
            int(''.join(str(int(char, 36)) for char in iban[4:] + iban[:4])) % 97 != 1:
        raise ValidationError(_("%s is not a valid IBAN: check it.", value))
    return iban


class EmsErasmusPayee(models.AbstractModel):
    """Who the Secretary transfers part of a grant to: an individual mobility's participant (issue
    #697) or a group mobility's (issue #764, their pocket money). A first payment, the prefinancing
    percentage of what they receive (a single payment at 100 %), and the rest in a final one.
    Each payee says what it transfers in all, its percentage, when a payment can be asked for and
    how a payment points at it."""
    _name = 'ems.erasmus.payee'
    _description = 'Erasmus+ grant payee'

    can_request_prefinancing = fields.Boolean(string="Can request the first payment",
                                              compute='_compute_can_request_payment')
    can_request_final = fields.Boolean(string="Can request the final payment", compute='_compute_can_request_payment')

    def _ems_payee_granted(self):
        """Whether there is a grant to pay at all."""
        raise NotImplementedError()

    def _ems_payee_amount(self):
        """What the participant receives in all."""
        raise NotImplementedError()

    def _ems_payee_percent(self):
        raise NotImplementedError()

    def _ems_payee_link(self):
        """The payment's field pointing at this payee."""
        raise NotImplementedError()

    def _ems_payee_check_state(self):
        """Raise when no payment can be requested now."""
        raise NotImplementedError()

    def _ems_payee_deductions(self):
        """What the centre pays directly out of the grant, as (label, amount), for the portal."""
        return []

    def _ems_payee_bank(self):
        """(IBAN, holder) of the account to transfer to: the participant's first bank account, the
        one EMS keeps from enrolment (a family's, for a minor, may be in the guardian's name)."""
        self.ensure_one()
        bank = self.partner_id.sudo().bank_ids[:1]
        return bank.acc_number, bank.acc_holder_name or (self.partner_id.name if bank else False)

    def _ems_payee_depends(self):
        """What the request buttons depend on; the payee's `payment_ids` is its own field."""
        return []

    @api.depends(lambda self: self._ems_payee_depends())
    def _compute_can_request_payment(self):
        for payee in self:
            payments = payee.sudo().payment_ids
            first = payments.filtered(lambda payment: payment.kind in FIRST_PAYMENT_KINDS)
            payee.can_request_prefinancing = bool(payee._ems_payee_granted()) and not first
            payee.can_request_final = bool(first) and not payments.filtered(lambda payment: payment.kind == 'final')

    def _ems_first_payment_vals(self):
        """The first payment of each payee, ready to create."""
        vals_list = []
        for payee in self:
            if not payee.can_request_prefinancing:
                raise UserError(_("The first payment of %s is already requested, or the grant is not set.",
                                  payee.partner_id.name))
            percent = payee._ems_payee_percent()
            vals_list.append(payee._ems_payment_vals('single' if percent >= 100 else 'prefinancing',
                                                     payee._ems_payee_amount() * percent / 100))
        return vals_list

    def _ems_final_payment_vals(self):
        """The rest, on return: what the participant receives minus what was already requested, so
        a change of the grant or of what the centre pays after the first payment lands here."""
        vals_list = []
        for payee in self:
            if not payee.can_request_final:
                raise UserError(_("Request the first payment of %s before the final one, and only once.",
                                  payee.partner_id.name))
            vals_list.append(payee._ems_payment_vals(
                'final', payee._ems_payee_amount() - sum(payee.sudo().payment_ids.mapped('amount'))))
        return vals_list

    def _ems_payment_vals(self, kind, amount):
        self.ensure_one()
        self._ems_payee_check_state()
        amount = self.currency_id.round(amount)
        if self.currency_id.compare_amounts(amount, 0) <= 0:
            raise UserError(_("There is nothing to pay to %s: check the grant and the services the centre pays.",
                              self.partner_id.name))
        return {**self._ems_payee_link(), 'kind': kind, 'amount': amount}

    def _ems_left_to_pay(self):
        """A payment still to pay, or part of what the participant receives not requested yet."""
        self.ensure_one()
        payments = self.sudo().payment_ids
        return bool(payments.filtered(lambda payment: payment.state == 'to_pay')) or \
            self.currency_id.compare_amounts(self._ems_payee_amount() - sum(payments.mapped('amount')), 0) > 0

    def _ems_portal_grant(self):
        """The grant as the participant reads it on the portal (art. 5 of the calls: what the centre
        pays directly and what they receive): the deductions as (label, amount), the payments as
        (label, state label, amount, paid date)."""
        self.ensure_one()
        Payment = self.env['ems.erasmus.payment']
        kinds = dict(Payment._fields['kind']._description_selection(self.env))
        states = dict(Payment._fields['state']._description_selection(self.env))
        payments = [(kinds[payment.kind], states[payment.state], payment.amount, payment.paid_date)
                    for payment in self.sudo().payment_ids]
        return self._ems_payee_deductions(), payments
