# -*- coding: utf-8 -*-
from odoo import models
from odoo.tools import format_amount, format_date


class AccountMove(models.Model):
    """Portal-visible payment notifications for an enrollment invoice (issue #491)."""
    _inherit = 'account.move'

    def _ems_enrollment_order(self):
        """The EMS enrollment this invoice bills, if any."""
        self.ensure_one()
        orders = self.invoice_line_ids.sale_line_ids.order_id
        return orders.filtered(lambda order: order.ems_course_id)[:1]

    def _ems_installment_lines(self):
        """The invoice's installments, oldest due date first."""
        self.ensure_one()
        return self.line_ids.filtered(
            lambda line: line.display_type == 'payment_term'
        ).sorted(lambda line: (line.date_maturity or self.invoice_date_due, line.id))

    def _ems_notify_enrollment_payment(self, settled_lines):
        """Post one message per just-settled installment on the enrollment's own chatter.

        Posting on the `sale.order` rather than widening any portal domain to `account.move`
        is what makes a payment visible on both portal pages that list communications, without
        exposing anything else of the invoice. The message carries `ems.mt_enrollment_payment`,
        a subtype nobody is subscribed to (`default=False`), so it is stored and readable in the
        portal without emailing the enrollment's followers.
        """
        for move in self:
            order = move._ems_enrollment_order()
            if not order:
                continue
            lines = move._ems_installment_lines()
            # The family reads this, not the person who registered the payment.
            move_lang = move.with_context(lang=order.partner_id.lang or self.env.lang)
            for number, line in enumerate(lines, start=1):
                if line not in settled_lines:
                    continue
                amount = format_amount(move_lang.env, abs(line.amount_currency), move.currency_id)
                if len(lines) > 1:
                    body = move_lang.env._(
                        "Payment received for installment %(number)s of %(count)s of enrollment "
                        "%(enrollment)s: %(amount)s (due %(due_date)s).",
                        number=number, count=len(lines), enrollment=order.name, amount=amount,
                        due_date=format_date(move_lang.env, line.date_maturity),
                    )
                else:
                    body = move_lang.env._(
                        "Payment received for enrollment %(enrollment)s: %(amount)s.",
                        enrollment=order.name, amount=amount,
                    )
                order.sudo().message_post(
                    body=body,
                    message_type='comment',
                    subtype_xmlid='ems.mt_enrollment_payment',
                )


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    def _reconcile_pre_hook(self):
        # Snapshot of the installments still open before this reconciliation: comparing against
        # it afterwards is what keeps _ems_notify_enrollment_payment() from ever announcing a
        # payment registered before this feature existed - no stored flag, no backfill.
        data = super()._reconcile_pre_hook()
        invoices = data['not_paid_invoices'] | data['in_payment_invoices']
        data['ems_open_installments'] = invoices.line_ids.filtered(
            lambda line: line.display_type == 'payment_term' and not line.reconciled)
        return data

    def _reconcile_post_hook(self, data):
        super()._reconcile_post_hook(data)
        settled = data.get(
            'ems_open_installments', self.env['account.move.line']
        ).filtered(lambda line: line.reconciled)
        settled.move_id._ems_notify_enrollment_payment(settled)
