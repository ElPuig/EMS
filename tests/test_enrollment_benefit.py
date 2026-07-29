import base64
from datetime import date
from unittest.mock import patch

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase

from .common import create_level_study


class TestEnrollmentBenefit(TransactionCase):
    """Issue 352: benefits (bonification/exemption) vs confirmed enrollments.

    - A benefit approved while the enrollment is still a draft applies
      immediately to the fee lines.
    - Once the enrollment is confirmed, the order is frozen: a benefit
      approved afterwards must NOT alter its lines (order and posted invoice
      must always match).
    - The secretary re-apply action lifts the freeze explicitly: it cancels
      the unpaid invoice, recomputes the fee lines and regenerates the
      invoice.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Never let a test reach a real SMTP server (see CLAUDE.md).
        mail_server_patcher = patch(
            'odoo.addons.base.models.ir_mail_server.IrMailServer.send_email',
        )
        mail_server_patcher.start()
        cls.addClassCleanup(mail_server_patcher.stop)

        Course = cls.env['ems.course']
        cls.course = Course.search([('is_enrollment_default', '=', True)], limit=1) \
            or Course.create({'start': 2099, 'end': 2100, 'is_enrollment_default': True})
        cls.level, cls.study = create_level_study(cls, 'BNL', level={'name': 'Benefit Level'}, study={
            'code': 'BNF001', 'acronym': 'BNST', 'name': 'Benefit Study',
        })
        cls.subject1 = cls.env['ems.subject'].create({
            'code': 'BNSUB1', 'acronym': 'BN1', 'name': 'Benefit Subject 1',
            'study_ids': [(6, 0, [cls.study.id])]})
        cls.subject2 = cls.env['ems.subject'].create({
            'code': 'BNSUB2', 'acronym': 'BN2', 'name': 'Benefit Subject 2',
            'study_ids': [(6, 0, [cls.study.id])]})
        cls.fee_product = cls.env['product.template'].create({
            'name': 'Benefit Enrollment Fee',
            'type': 'service',
            'invoice_policy': 'order',
            'is_generic': True,
            'ems_is_enrollment_fee': True,
            'list_price': 400.0,
            'ems_subject_unit_cost': 25.0,
        })
        cls.student = cls.env['res.partner'].create({
            'name': 'Benefit Student', 'contact_type': 'student'})

    def _order(self, partner=None):
        order = self.env['sale.order'].create({
            'partner_id': (partner or self.student).id,
            'ems_study_id': self.study.id,
            'ems_course_id': self.course.id,
            'shift': 'morning',
        })
        order.order_line = [
            (0, 0, {'product_id': self.subject1.product_id.id}),
            (0, 0, {'product_id': self.subject2.product_id.id}),
            (0, 0, {'product_id': self.fee_product.product_variant_id.id}),
        ]
        return order

    def _fee_line(self, order):
        return order.order_line.filtered(
            lambda l: l.product_template_id.ems_is_enrollment_fee)

    def _add_benefit(self, benefit_type):
        return self.env['ems.student.benefit'].create({
            'student_id': self.student.id,
            'benefit_type': benefit_type,
            'document': base64.b64encode(b'doc'),
        })

    # --- benefit approved before confirmation (draft order) ------------------

    def test_bonification_applies_on_draft_order(self):
        order = self._order()
        fee = self._fee_line(order)
        self.assertEqual(fee.price_unit, 50.0)  # 2 subjects x 25 < 400 cap
        self.assertEqual(fee.discount, 0.0)
        self._add_benefit('large_family_gen')
        self.assertEqual(self.student.benefit_status, 'bonification')
        self.assertEqual(fee.discount, 50.0)
        self.assertEqual(fee.price_subtotal, 25.0)

    def test_exemption_applies_on_draft_order(self):
        order = self._order()
        fee = self._fee_line(order)
        self._add_benefit('disability')
        self.assertEqual(self.student.benefit_status, 'exemption')
        self.assertEqual(fee.discount, 100.0)
        self.assertEqual(fee.price_subtotal, 0.0)

    # --- freeze after confirmation --------------------------------------------

    def test_confirmed_order_is_frozen(self):
        order = self._order()
        fee = self._fee_line(order)
        self.assertEqual(fee.price_subtotal, 50.0)
        total_before = order.amount_total
        order.write({'state': 'sale'})
        self.env.flush_all()

        self._add_benefit('large_family_gen')
        self.assertEqual(self.student.benefit_status, 'bonification')
        # The confirmed order keeps the amounts it was invoiced with.
        self.assertEqual(fee.discount, 0.0)
        self.assertEqual(fee.price_subtotal, 50.0)
        self.assertEqual(order.amount_total, total_before)

    def test_draft_order_still_recomputes_while_other_confirmed(self):
        # A student may only hold one enrollment per course, so the freeze on
        # a confirmed enrollment is cross-checked against a second student's
        # draft one: the same kind of benefit only recomputes the draft.
        student2 = self.env['res.partner'].create({
            'name': 'Benefit Student 2', 'contact_type': 'student'})
        confirmed = self._order()
        confirmed.write({'state': 'sale'})
        self.env.flush_all()
        draft = self._order(partner=student2)

        self._add_benefit('large_family_gen')
        self.env['ems.student.benefit'].create({
            'student_id': student2.id,
            'benefit_type': 'large_family_gen',
            'document': base64.b64encode(b'doc'),
        })
        self.assertEqual(self._fee_line(confirmed).discount, 0.0)
        self.assertEqual(self._fee_line(draft).discount, 50.0)

    # --- secretary re-apply action --------------------------------------------

    def test_reapply_benefits_regenerates_invoice(self):
        order = self._order()
        order.write({'state': 'sale'})
        self.env.flush_all()
        invoice = order._ems_generate_enrollment_invoice()
        self.assertEqual(invoice.state, 'posted')
        self.assertEqual(invoice.amount_total, order.amount_total)
        total_before = order.amount_total

        self._add_benefit('large_family_gen')
        self.assertEqual(order.amount_total, total_before)  # still frozen

        order.action_ems_reapply_benefits()
        fee = self._fee_line(order)
        self.assertEqual(fee.discount, 50.0)
        self.assertEqual(fee.price_subtotal, 25.0)
        self.assertEqual(invoice.state, 'cancel')
        new_invoice = order.invoice_ids.filtered(
            lambda m: m.move_type == 'out_invoice' and m.state != 'cancel')
        self.assertEqual(len(new_invoice), 1)
        self.assertEqual(new_invoice.state, 'posted')
        self.assertEqual(new_invoice.amount_total, order.amount_total)

    def test_reapply_exemption_zeroes_invoice(self):
        order = self._order()
        order.write({'state': 'sale'})
        self.env.flush_all()
        order._ems_generate_enrollment_invoice()

        self._add_benefit('disability')
        order.action_ems_reapply_benefits()
        fee = self._fee_line(order)
        self.assertEqual(fee.discount, 100.0)
        self.assertEqual(fee.price_subtotal, 0.0)

    def test_direct_debit_invoice_trusts_bank_account(self):
        # An untrusted debtor account must not block posting (regular user)
        # nor be silently dropped from the invoice (superuser).
        bank = self.env['res.partner.bank'].create({
            'acc_number': 'ES9121000418450200051332',
            'partner_id': self.student.id,
        })
        self.assertFalse(bank.allow_out_payment)
        order = self._order()
        order.write({'state': 'sale', 'ems_payment_method': 'direct_debit'})
        self.env.flush_all()

        invoice = order._ems_generate_enrollment_invoice()
        self.assertEqual(invoice.partner_bank_id, bank)
        self.assertTrue(bank.allow_out_payment)

    def test_reapply_requires_confirmed_order(self):
        order = self._order()
        with self.assertRaises(ValidationError):
            order.action_ems_reapply_benefits()
