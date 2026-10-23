from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import Form
from odoo.tests.common import HttpCase, tagged

from .test_erasmus_mobility import ErasmusMobilityCase


class ErasmusGrantCase(ErasmusMobilityCase):
    """Both students accepted their place and are preparing their mobility."""

    def _preparing(self):
        first, second = self._accepted()
        (first | second)._ems_set_state('preparing')
        return first, second

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
            first.payment_ids.with_user(self.erasmus_user).action_mark_paid()
        with self.assertRaises(AccessError):
            first.payment_ids.with_user(self.erasmus_user).write({'state': 'paid'})
        payment.action_mark_paid()
        self.assertEqual(first.payment_ids.state, 'paid')
        self.assertEqual(first.payment_ids.paid_by_id, self.secretary_user)
        team_payment = first.payment_ids.with_user(self.erasmus_user)
        with self.assertRaises(UserError):
            team_payment.amount = 1
        with self.assertRaises(UserError):
            team_payment.unlink()
        payment.action_mark_unpaid()
        self.assertEqual(first.payment_ids.state, 'to_pay')
        team_payment.unlink()
        self.assertFalse(first.payment_ids)

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
