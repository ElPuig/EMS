import base64

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import Form
from odoo.tests.common import HttpCase, tagged

from .test_erasmus import PDF
from .test_erasmus_mobility import ErasmusMobilityCase


class ErasmusGrantCase(ErasmusMobilityCase):
    """Both students accepted their place and are preparing their mobility."""

    def _preparing(self):
        first, second = self._accepted()
        (first | second)._ems_set_state('preparing')
        return first, second

    def _transfer(self, records, user, receipt=True):
        """The Secretary's transfer wizard, as `user`, for payments or invoices."""
        field = 'payment_ids' if records._name == 'ems.erasmus.payment' else 'invoice_ids'
        action = records.with_user(user).action_register_transfer()
        wizard = self.env['ems.erasmus.transfer.wizard'].with_user(user).with_context(action['context']).create({
            'receipt': receipt and base64.b64encode(PDF), 'receipt_filename': receipt and 'receipt.pdf'})
        self.assertEqual(wizard[field], records)
        wizard.action_confirm()

    def _undo(self, records, user=None, reason='Registered by mistake'):
        """Undo a transfer through its wizard, with a reason (audit D-18)."""
        records = records.with_user(user) if user else records
        action = records.action_mark_unpaid()
        self.env[action['res_model']].with_user(user or self.env.user).with_context(action['context']).create(
            {'reason': reason}).action_confirm()

    def _invoice(self, mobilities, amount, **vals):
        return self.env['ems.erasmus.invoice'].create({
            'name': 'F-TEST-1', 'amount': amount, 'concept': 'travel', 'mobility_ids': [(6, 0, mobilities.ids)], **vals})


@tagged('post_install', '-at_install')
class TestErasmusGrant(ErasmusGrantCase):
    """Issue #697 - grants, provision of services, invoices and payments."""

    def test_invoice_is_split_equally_with_the_cents_left_on_the_first_share(self):
        first, second = self._preparing()
        third = self.env['ems.erasmus.mobility']
        invoice = self._invoice(first | second, 1000.01)
        shares = {provision.mobility_id: provision.amount for provision in invoice.provision_ids}
        self.assertEqual(shares, {first: 500.01, second: 500.0})
        self.assertEqual(invoice.unassigned_amount, 0)
        invoice.provision_ids.filtered(lambda provision: provision.mobility_id == second).amount = 400
        self.assertAlmostEqual(invoice.unassigned_amount, 100.0)
        invoice.mobility_ids = first | third
        self.assertEqual(invoice.provision_ids.mobility_id, first, "A change of participants splits it again.")
        self.assertEqual(invoice.provision_ids.amount, 1000.01)

    def test_grant_net_is_the_grant_minus_what_the_centre_pays(self):
        first, second = self._preparing()
        first.grant_amount = 1250
        self._invoice(first | second, 600)
        first.provision_ids = [(0, 0, {'concept': 'other', 'description': 'Equipment', 'amount': 50})]
        self.assertEqual(first.provision_amount, 350)
        self.assertEqual(first.grant_net, 900)

    def test_prefinancing_then_final_payment_absorbs_later_changes(self):
        first, _second = self._preparing()
        first.write({'grant_amount': 2000, 'prefinancing_percent': 80})
        first.action_request_prefinancing()
        self.assertEqual(first.payment_ids.mapped('kind'), ['prefinancing'])
        self.assertEqual(first.payment_ids.amount, 1600)
        with self.assertRaises(UserError):
            first.action_request_prefinancing()
        self._invoice(first, 300)
        first.action_request_final_payment()
        final = first.payment_ids.filtered(lambda payment: payment.kind == 'final')
        self.assertEqual(final.amount, 100, "2000 - 300 paid by the centre - 1600 already requested.")
        with self.assertRaises(UserError):
            first.action_request_final_payment()

    def test_full_prefinancing_is_a_single_payment(self):
        first, _second = self._preparing()
        first.write({'grant_amount': 1300, 'prefinancing_percent': 100})
        first.action_request_prefinancing()
        self.assertEqual(first.payment_ids.kind, 'single')
        self.assertEqual(first.payment_ids.amount, 1300)
        with self.assertRaises(UserError):
            first.action_request_final_payment()

    def test_nothing_to_pay_when_the_centre_pays_everything(self):
        first, _second = self._preparing()
        first.grant_amount = 500
        self._invoice(first, 500)
        with self.assertRaises(UserError):
            first.action_request_prefinancing()

    def test_prefinancing_is_a_percentage(self):
        first, _second = self._preparing()
        with self.assertRaises(ValidationError):
            first.prefinancing_percent = 0
        with self.assertRaises(ValidationError):
            first.prefinancing_percent = 120

    def test_only_the_erasmus_team_requests_payments(self):
        first, _second = self._preparing()
        first.grant_amount = 1000
        with self.assertRaises(AccessError):
            first.with_user(self.secretary_user).action_request_prefinancing()
        first.with_user(self.erasmus_user).action_request_prefinancing()
        self.assertTrue(first.payment_ids)

    def test_secretary_pays_and_a_paid_payment_is_frozen(self):
        first, _second = self._preparing()
        self.student.bank_ids = [(0, 0, {'acc_number': 'ES9121000418450200051332'})]
        first.grant_amount = 1000
        first.action_request_prefinancing()
        payment = first.payment_ids.with_user(self.secretary_user)
        self.assertEqual(payment.bank_account, 'ES91 2100 0418 4502 0005 1332')
        self.assertEqual(payment.partner_id, self.student)
        with self.assertRaises(AccessError):
            first.payment_ids.with_user(self.erasmus_user).action_register_transfer()
        with self.assertRaises(AccessError):
            first.payment_ids.with_user(self.erasmus_user).write({'state': 'paid'})
        self._transfer(first.payment_ids, self.secretary_user)
        self.assertEqual(first.payment_ids.state, 'paid')
        self.assertEqual(first.payment_ids.paid_by_id, self.secretary_user)
        self.assertEqual(first.payment_ids.receipt_ids.mapped('name'), ['receipt.pdf'])
        team_payment = first.payment_ids.with_user(self.erasmus_user)
        with self.assertRaises(UserError):
            team_payment.amount = 1
        with self.assertRaises(UserError):
            team_payment.unlink()
        self._undo(payment)
        self.assertEqual(first.payment_ids.state, 'to_pay')
        team_payment.unlink()
        self.assertFalse(first.payment_ids)

    def test_every_payment_or_invoice_to_pay_is_a_task_for_the_secretary(self):
        """The Secretary (role) gets one task per amount to transfer, in their daily summary of
        pending tasks, until the transfer is registered; undoing it brings the task back."""
        # The Secretary role comes from managing the top-level Secretary department (one per centre).
        secretary = self.env['hr.employee'].create({'name': 'Test Secretary', 'user_id': self.secretary_user.id,
                                                    'employee_type': 'teacher'})
        department = self.env['hr.department'].search([('top_level_role', '=', 'secretary')], limit=1)
        if department:
            department.manager_id = secretary
        else:
            self.env['hr.department'].create({'name': 'Test Secretary Department', 'is_top_level': True,
                                              'top_level_area': 'asp', 'top_level_role': 'secretary',
                                              'manager_id': secretary.id})
        self.assertIn(self.env.ref('ems.role_secretary'), secretary.role_ids)
        first, second = self._preparing()
        first.grant_amount = 1000
        first.action_request_prefinancing()
        payment = first.payment_ids
        invoice = self._invoice(first | second, 300)
        for record in (payment, invoice):
            self.assertEqual(record.activity_ids.user_id, self.secretary_user)
        self.assertIn(first.partner_id.name, payment.activity_ids.summary)
        self._transfer(payment, self.secretary_user)
        self._transfer(invoice, self.secretary_user)
        self.assertFalse(payment.activity_ids | invoice.activity_ids)
        self._undo(payment, self.secretary_user)
        self.assertEqual(payment.activity_ids.user_id, self.secretary_user)

    def test_one_transfer_pays_several_payments_with_one_receipt(self):
        first, second = self._preparing()
        (first | second).write({'grant_amount': 1000, 'prefinancing_percent': 100})
        (first | second).action_request_prefinancing()
        payments = (first | second).payment_ids
        self._transfer(payments, self.secretary_user)
        self.assertEqual(set(payments.mapped('state')), {'paid'})
        self.assertEqual(len(payments.receipt_ids), 1, "The receipt is shared, not copied.")
        self.assertEqual(payments.with_user(self.erasmus_user).receipt_ids.raw, PDF,
                         "The Erasmus team reads the receipt too.")

    def test_secretary_pays_an_invoice_and_then_it_cannot_be_deleted(self):
        first, second = self._preparing()
        invoice = self._invoice(first | second, 900)
        with self.assertRaises(AccessError):
            invoice.with_user(self.erasmus_user).write({'state': 'paid'})
        self._transfer(invoice, self.secretary_user)
        self.assertEqual(invoice.state, 'paid')
        self.assertTrue(invoice.receipt_ids)
        with self.assertRaises(UserError):
            invoice.with_user(self.erasmus_user).unlink()

    def test_secretary_reads_the_invoices_and_their_shares(self):
        first, second = self._preparing()
        invoice = self._invoice(first | second, 300).with_user(self.secretary_user)
        self.assertEqual(invoice.provision_ids.partner_id, self.student | self.second)
        with self.assertRaises(AccessError):
            invoice.amount = 1

    def test_team_creates_host_entities_and_their_tutors_but_no_other_contact(self):
        Partner = self.env['res.partner'].with_user(self.erasmus_user)
        host = Partner.create({'name': 'Test Host GmbH', 'is_company': True, 'is_erasmus_host': True})
        tutor = Partner.create({'name': 'Test Tutor', 'parent_id': host.id, 'email': 'tutor@example.com'})
        host.city = 'Reutlingen'
        with self.assertRaises(AccessError):
            Partner.create({'name': 'Not a host', 'is_company': True})
        with self.assertRaises(AccessError):
            self.student.with_user(self.erasmus_user).city = 'Elsewhere'
        first, _second = self._preparing()
        with Form(first.with_user(self.erasmus_user)) as form:
            form.host_partner_id = host
            self.assertEqual(form.host_contact_id, tutor, "The host entity's only contact is the tutor.")
        self.assertEqual(first.host_contact_email, 'tutor@example.com')


@tagged('post_install', '-at_install')
class TestPortalErasmusGrant(HttpCase, ErasmusGrantCase):
    """Issue #697 - the participant reads their grant on the portal."""

    def test_portal_shows_the_grant_what_the_centre_pays_and_the_payments(self):
        first, second = self._preparing()
        first.grant_amount = 1250
        self._invoice(first | second, 800, description='Flights to Larnaca')
        first.action_request_prefinancing()
        self.env['res.users'].with_context(no_reset_password=True).create({
            'name': self.student.name, 'login': 'test_erasmus_grant_student', 'password': 'test_erasmus_grant_student',
            'partner_id': self.student.id, 'lang': 'en_US',
            'groups_id': [(6, 0, [self.env.ref('base.group_portal').id])]})
        self.authenticate('test_erasmus_grant_student', 'test_erasmus_grant_student')
        page = self.url_open(f'/my/erasmus/call/{self.call.id}').text
        self.assertIn('o_ems_erasmus_grant', page)
        self.assertIn('Flights to Larnaca', page)
        self.assertIn('850.00', page, "1250 minus a 400 share of the flights.")
        self.assertIn('Prefinancing', page)
