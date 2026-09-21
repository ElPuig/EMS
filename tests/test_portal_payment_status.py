from datetime import date

from odoo.tests.common import TransactionCase

from .common import create_level_study, mock_outgoing_email, next_student_id


class TestPortalPaymentStatus(TransactionCase):
    """Issue #491: the portal must show whether the enrollment has actually been paid.

    Two pieces, both driven by the enrollment's own invoice: the per-installment status the
    payment block renders (_ems_portal_installments) and the message posted on the enrollment's
    chatter when an installment is settled, which is what reaches both communications lists.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.mail_transport = mock_outgoing_email(cls)
        Course = cls.env['ems.course']
        cls.course = Course.search([('is_enrollment_default', '=', True)], limit=1) \
            or Course.create({'start': 2099, 'end': 2100, 'is_enrollment_default': True})
        cls.level, cls.study = create_level_study(cls, 'PPS', level={'name': 'Payment Status Level'}, study={
            'code': 'PPS001', 'acronym': 'PPST', 'name': 'Payment Status Study',
        })
        cls.subject = cls.env['ems.subject'].create({
            'code': 'PPSSUB', 'acronym': 'PP1', 'name': 'Payment Status Subject',
            'study_ids': [(6, 0, [cls.study.id])]})
        cls.fee_product = cls.env['product.template'].create({
            'name': 'Payment Status Fee', 'type': 'service', 'invoice_policy': 'order',
            'is_generic': True, 'ems_is_enrollment_fee': True,
            'list_price': 400.0, 'ems_subject_unit_cost': 100.0,
        })
        cls.student = cls.env['res.partner'].create({
            'name': 'Payment Status Student', 'contact_type': 'student',
            'student_id': next_student_id()})
        cls.deferred_term = cls.env['account.payment.term'].create({
            'name': 'PPS two installments', 'ems_portal_visible': True, 'ems_requires_fees': True,
            'line_ids': [
                (0, 0, {'value': 'percent', 'value_amount': 50.0, 'nb_days': 0}),
                (0, 0, {'value': 'percent', 'value_amount': 50.0, 'nb_days': 60}),
            ],
        })

    def _order(self, payment_term=None):
        order = self.env['sale.order'].create({
            'partner_id': self.student.id,
            'ems_study_id': self.study.id,
            'ems_course_id': self.course.id,
            'shift': 'morning',
            'payment_term_id': payment_term.id if payment_term else False,
        })
        order.order_line = [
            (0, 0, {'product_id': self.subject.product_id.id}),
            (0, 0, {'product_id': self.fee_product.product_variant_id.id}),
        ]
        # The fee line has to price BEFORE the order is confirmed: a confirmed order freezes
        # its lines (sale.order.line._ems_benefit_frozen_lines), so a price still uncomputed
        # at that point would stay at zero and the invoice would have nothing to pay.
        self.assertTrue(order.amount_total)
        order.write({'state': 'sale'})
        self.env.flush_all()
        return order

    def _invoice(self, order):
        return order._ems_generate_enrollment_invoice()

    def _pay(self, invoice, amount=None):
        """Register a payment against the invoice, the way the secretary's office does."""
        wizard = self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=invoice.ids,
        ).create({'payment_date': date.today()})
        if amount is not None:
            wizard.amount = amount
        return wizard._create_payments()

    def _installment_lines(self, invoice):
        return invoice.line_ids.filtered(lambda line: line.display_type == 'payment_term')

    def _payment_messages(self, order):
        subtype = self.env.ref('ems.mt_enrollment_payment')
        return order.message_ids.filtered(lambda message: message.subtype_id == subtype)

    # --- _ems_portal_installments -------------------------------------------------

    def test_single_payment_installment_is_pending_until_paid(self):
        order = self._order()
        invoice = self._invoice(order)
        installments = order._ems_portal_installments()
        self.assertEqual(len(installments), 1)
        self.assertEqual(installments[0]['number'], 1)
        self.assertEqual(installments[0]['count'], 1)
        self.assertFalse(installments[0]['paid'])
        self.assertEqual(installments[0]['amount'], invoice.amount_total)
        self.assertTrue(installments[0]['due_date'])
        # The label is assembled server-side so it can be translated as whole sentences.
        self.assertIn('Single payment', installments[0]['label'])

        self._pay(invoice)
        self.assertTrue(order._ems_portal_installments()[0]['paid'])

    def test_deferred_plan_reports_each_installment_separately(self):
        order = self._order(payment_term=self.deferred_term)
        invoice = self._invoice(order)
        installments = order._ems_portal_installments()
        self.assertEqual(len(installments), 2)
        self.assertEqual([i['number'] for i in installments], [1, 2])
        self.assertTrue(all(i['count'] == 2 for i in installments))
        self.assertLess(installments[0]['due_date'], installments[1]['due_date'])
        self.assertFalse(any(i['paid'] for i in installments))
        self.assertIn('1', installments[0]['label'])
        self.assertIn('2', installments[1]['label'])

        first = self._installment_lines(invoice).sorted('date_maturity')[0]
        self._pay(invoice, amount=abs(first.amount_currency))

        installments = order._ems_portal_installments()
        self.assertTrue(installments[0]['paid'], "the first installment is settled")
        self.assertFalse(installments[1]['paid'], "the second one is still pending")
        self.assertEqual(invoice.payment_state, 'partial')

    def test_an_enrollment_without_payment_plan_still_reports_its_installments(self):
        # An enrollment confirmed from the backend carries no payment_term_id and no payment
        # method, but its invoice is just as real: 149 of the 544 confirmed enrollments of this
        # box's database are in that state, and they showed no payment information at all.
        order = self._order()
        self.assertFalse(order.payment_term_id)
        self.assertFalse(order.ems_payment_method)
        invoice = self._invoice(order)

        installments = order._ems_portal_installments()
        self.assertEqual(len(installments), 1)
        self.assertEqual(installments[0]['amount'], invoice.amount_total)

        self._pay(invoice)
        self.assertTrue(order._ems_portal_installments()[0]['paid'])

    def test_no_invoice_yet_reports_no_installments(self):
        self.assertEqual(self._order()._ems_portal_installments(), [])

    # --- payment message on the enrollment chatter ---------------------------------

    def test_paying_posts_a_message_on_the_enrollment(self):
        order = self._order()
        invoice = self._invoice(order)
        self.assertFalse(self._payment_messages(order))

        self._pay(invoice)

        messages = self._payment_messages(order)
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages.model, 'sale.order')
        self.assertEqual(messages.res_id, order.id)
        self.assertIn(order.name, messages.body)

    def test_each_installment_is_announced_once(self):
        order = self._order(payment_term=self.deferred_term)
        invoice = self._invoice(order)
        lines = self._installment_lines(invoice).sorted('date_maturity')

        self._pay(invoice, amount=abs(lines[0].amount_currency))
        self.assertEqual(len(self._payment_messages(order)), 1)

        self._pay(invoice, amount=abs(lines[1].amount_currency))
        messages = self._payment_messages(order)
        self.assertEqual(len(messages), 2, "one message per installment, never a repeat")

    def test_partial_payment_of_an_installment_is_not_announced(self):
        order = self._order(payment_term=self.deferred_term)
        invoice = self._invoice(order)
        lines = self._installment_lines(invoice).sorted('date_maturity')

        self._pay(invoice, amount=abs(lines[0].amount_currency) / 2)

        self.assertFalse(self._payment_messages(order))
        self.assertFalse(any(i['paid'] for i in order._ems_portal_installments()))

    def test_the_message_never_sends_an_email(self):
        # ems.mt_enrollment_payment is default=False on purpose: nobody is subscribed to it,
        # so the message is visible in the portal without mailing the enrollment's followers.
        order = self._order()
        self.mail_transport.reset_mock()
        self._pay(self._invoice(order))
        self.assertTrue(self._payment_messages(order))
        self.mail_transport.assert_not_called()

    def test_the_message_is_written_in_the_family_language(self):
        # The family reads it in the portal, so it is built in the student's language, not in
        # the language of whoever registered the payment.
        self.student.lang = 'ca_ES'
        order = self._order()
        self._pay(self._invoice(order))
        self.assertIn('Pagament rebut', self._payment_messages(order).body)

    def test_a_non_enrollment_invoice_is_left_alone(self):
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.student.id,
            'invoice_line_ids': [(0, 0, {'name': 'Something else', 'quantity': 1, 'price_unit': 10.0})],
        })
        invoice.action_post()
        self._pay(invoice)
        self.assertEqual(invoice.payment_state, 'paid')
        self.assertFalse(self.env['mail.message'].search([
            ('model', '=', 'sale.order'),
            ('subtype_id', '=', self.env.ref('ems.mt_enrollment_payment').id),
            ('res_id', 'in', self.env['sale.order'].search([('partner_id', '=', self.student.id)]).ids),
        ]))

    # --- what the portal pages actually filter on ----------------------------------

    def test_the_message_reaches_both_portal_communication_filters(self):
        order = self._order()
        self._pay(self._invoice(order))
        message = self._payment_messages(order)

        # /my/comunicaciones: any non-note message on the student's own enrollments.
        note = self.env.ref('mail.mt_note')
        self.assertIn(message, self.env['mail.message'].search([
            ('model', '=', 'sale.order'), ('res_id', 'in', order.ids),
            ('message_type', 'in', ['email', 'comment', 'notification']),
            ('subtype_id', '!=', note.id),
        ]))
        # /my/gestion-matriculas: the enrollment page's own, narrower filter.
        self.assertIn(message, self.env['mail.message'].search(
            order._ems_portal_message_domain()))
