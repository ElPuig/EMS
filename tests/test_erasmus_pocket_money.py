import io

import openpyxl

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import HttpCase, tagged

from odoo.addons.ems.models.erasmus.grant import _secretary_users

from .common import create_role_user
from .test_erasmus_economy import ErasmusEconomyMixin
from .test_erasmus_grant import ErasmusGrantCase
from .test_erasmus_group_mobility import ErasmusGroupMobilityCase

# Valid Spanish IBANs (mod-97), fictitious accounts.
IBAN = 'ES9121000418450200051332'
TEACHER_IBAN = 'ES7921000813610123456789'


class ErasmusPocketMoneyCase(ErasmusEconomyMixin, ErasmusGroupMobilityCase):
    """Issue #764 - an approved group mobility (8 students, the leader and the accompanying teacher)
    in preparation: students' grants 1,200 €, teachers' 1,500 €, every student with the bank account
    of their enrolment and every teacher with the one they gave."""

    _undo = ErasmusGrantCase._undo

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.secretary_user = create_role_user(cls, 'secretary', 'test_pocket_secretary', name='Pocket Secretary')
        cls.director_user = create_role_user(cls, 'director', 'test_pocket_director')

    def _ready(self, iban=True):
        self._approved()
        self.assertEqual(self.mobility.state, 'preparation')
        participants = self.mobility.participant_ids
        self.students = participants.filtered(lambda participant: participant.role == 'student')
        self.teachers = participants - self.students
        self.students.write({'grant_amount': 1200})
        self.teachers.write({'grant_amount': 1500})
        if iban:
            self.env['res.partner.bank'].create([{'partner_id': partner.id, 'acc_number': IBAN}
                                                 for partner in self.students.partner_id])
            self.teachers.write({'bank_account': TEACHER_IBAN, 'bank_holder': 'Teacher Holder'})
        return participants

    def _collective(self, amount, name='F-POCKET-1'):
        return self.env['ems.erasmus.invoice'].create({
            'name': name, 'amount': amount, 'project_id': self.project.id, 'group_mobility_id': self.mobility.id})

    def _request(self, final=False, user=None):
        mobility = self.mobility.with_user(user or self.technician_user)
        (mobility.action_request_final_pocket_money if final else mobility.action_request_pocket_money)()
        return self.mobility.participant_ids.payment_ids

    def _secretary_tasks(self):
        """The Secretary's pocket money tasks of the group: one per person holding the role."""
        payments = self.env['ems.erasmus.payment'].search([('group_mobility_id', '=', self.mobility.id)])
        tasks = self.env['mail.activity'].search([
            ('res_model', '=', 'ems.erasmus.payment'), ('res_id', 'in', payments.ids),
            ('activity_type_id', '=', self.env.ref('ems.mail_activity_erasmus_transfer').id)])
        if tasks:
            self.assertEqual(tasks.user_id, _secretary_users(self.env))
            self.assertEqual(len(set(tasks.mapped('res_id'))), 1, "One task per group, not one per payment.")
            self.assertEqual(len(set(tasks.mapped('summary'))), 1)
        return tasks[:1]


@tagged('post_install', '-at_install')
class TestErasmusPocketMoney(ErasmusPocketMoneyCase):
    """Issue #764 - pocket money payments to every participant of a group mobility."""

    def test_collective_invoices_are_split_equally_and_the_pocket_money_is_the_rest(self):
        participants = self._ready()
        self.assertEqual(len(participants), 10)
        self._collective(2000)
        self._collective(5000, name='F-POCKET-2')
        self.assertEqual(set(participants.mapped('invoice_share')), {700})
        self.assertEqual(set(self.students.mapped('pocket_amount')), {500})
        self.assertEqual(set(self.teachers.mapped('pocket_amount')), {800})
        self._collective(100.05, name='F-POCKET-3')
        shares = participants.mapped('invoice_share')
        self.assertAlmostEqual(sum(shares), 7100.05, msg="The cents left over go to one participant, none is lost.")
        self.assertEqual(sorted(set(shares)), [710, 710.05])
        self.teachers[:1].sudo().state = 'withdrawn'
        self.assertEqual(self.teachers[:1].invoice_share, 0, "A withdrawn participant shares no invoice.")
        self.assertAlmostEqual(sum((participants - self.teachers[:1]).mapped('invoice_share')), 7100.05)

    def test_requesting_makes_one_payment_each_and_one_task_for_the_secretary(self):
        participants = self._ready()
        invoice = self._collective(7000)
        payments = self._request()
        self.assertEqual(len(payments), 10)
        self.assertEqual(set(payments.mapped('kind')), {'single'}, "100 % by default: one single payment.")
        self.assertEqual(sum(payments.mapped('amount')), 12600 - 7000)
        self.assertEqual(payments.mapped('project_id'), self.project)
        self.assertEqual(payments.mapped('group_mobility_id'), self.mobility)
        accounts = {account.replace(' ', '') for account in payments.with_user(self.secretary_user).mapped('bank_account')}
        self.assertEqual(accounts, {IBAN, TEACHER_IBAN})
        self.assertEqual(participants.with_user(self.technician_user).mapped('pocket_state'), ['to_pay'] * 10)
        tasks = self._secretary_tasks()
        self.assertTrue(tasks)
        self.assertIn(self.mobility.name, tasks.summary)
        self.assertIn('10', tasks.summary)
        with self.assertRaises(UserError):
            self._request()
        self.assertEqual((self.mobility.econ_committed, self.mobility.econ_paid), (12600, 0))
        self._pay(payments[:4], self.secretary_user)
        self.assertEqual(len(self._secretary_tasks()), 1, "Still something to pay.")
        self.assertIn('6', self._secretary_tasks().summary)
        self._pay(payments[4:], self.secretary_user)
        self._pay(invoice, self.secretary_user)
        self.assertFalse(self._secretary_tasks(), "Everything paid: the task is done.")
        self.assertEqual((self.mobility.econ_paid, self.mobility.econ_state), (12600, 'paid'))
        self.assertEqual(self.project.paid_amount, 12600, "Nothing counted twice.")
        self.assertEqual(set(participants.mapped('pocket_state')), {'paid'})
        self._undo(payments[:1], self.secretary_user)
        self.assertEqual(len(self._secretary_tasks()), 1, "An undone transfer asks again.")

    def test_without_a_bank_account_the_request_names_who_is_missing(self):
        self._ready(iban=False)
        self.teachers.write({'bank_account': TEACHER_IBAN})
        with self.assertRaisesRegex(UserError, self.students[:1].partner_id.name):
            self._request()
        self.assertFalse(self.mobility.participant_ids.payment_ids)
        with self.assertRaises(ValidationError):
            self.teachers[:1].bank_account = 'ES0000000000000000000000'

    def test_a_prefinancing_below_100_leaves_the_rest_for_the_return(self):
        self._ready()
        self.mobility.prefinancing_percent = 80
        payments = self._request()
        self.assertEqual(set(payments.mapped('kind')), {'prefinancing'})
        self.assertEqual(sum(payments.mapped('amount')), 12600 * 0.8)
        with self.assertRaises(UserError):
            self._request(final=True)
        self.mobility.sudo()._ems_set_state('return')
        finals = self._request(final=True) - payments
        self.assertEqual(set(finals.mapped('kind')), {'final'})
        self.assertAlmostEqual(sum(finals.mapped('amount')), 12600 * 0.2)

    def test_nothing_is_requested_before_the_selection_is_approved(self):
        self._ranked()
        with self.assertRaises(UserError):
            self._request()

    def test_when_the_centre_pays_nothing_each_one_receives_the_whole_grant(self):
        participants = self._ready()
        self.mobility.no_direct_costs = True
        with self.assertRaises(ValidationError):
            self._collective(1000)
        self.assertEqual(set(self.students.mapped('pocket_amount')), {1200})
        self.assertEqual(sum(self._request().mapped('amount')), 12600)
        self.mobility.no_direct_costs = False
        self._collective(1000)
        with self.assertRaises(ValidationError):
            self.mobility.no_direct_costs = True
        self.assertEqual(len(participants), 10)

    def test_closing_waits_until_the_pocket_money_is_paid(self):
        self._ready()
        self.mobility.sudo().write({'state': 'return', 'eu_survey_state': 'validated',
                                    'programme_execution': 'as_planned'})
        with self.assertRaisesRegex(UserError, 'pocket money'):
            self.mobility.with_user(self.technician_user).action_close()

    def test_the_leader_reads_the_invoices_and_states_but_never_the_bank_accounts(self):
        self._ready()
        invoice = self._collective(7000)
        self._request()
        leader_participants = self.mobility.with_user(self.leader_user).participant_ids
        self.assertEqual(sum(leader_participants.mapped('pocket_amount')), 5600)
        self.assertEqual(set(leader_participants.mapped('pocket_state')), {'to_pay'})
        self.assertEqual(self.mobility.with_user(self.leader_user).invoice_ids, invoice)
        with self.assertRaises(AccessError):
            leader_participants[:1].read(['bank_account'])
        with self.assertRaises(AccessError):
            invoice.with_user(self.leader_user).amount = 1
        with self.assertRaises(AccessError):
            invoice.with_user(self.other_teacher_user).read(['amount'])
        self.assertTrue(invoice.with_user(self.secretary_user).read(['amount']),
                        "The rule for the group's teachers never narrows the Secretary's.")
        payment = self.mobility.participant_ids.payment_ids[:1]
        self.assertTrue(payment.with_user(self.director_user).read(['amount']))
        with self.assertRaises(AccessError):
            payment.with_user(self.director_user).read(['bank_account'])

    def test_a_teacher_gives_their_own_bank_account_and_nobody_else(self):
        self._ready(iban=False)
        leader = self.teachers.filtered(lambda participant: participant.role == 'leader')
        action = self.mobility.with_user(self.leader_user).action_my_bank_account()
        wizard = self.env[action['res_model']].with_user(self.leader_user).with_context(action['context']).create(
            {'bank_account': 'es79 2100 0813 6101 2345 6789', 'bank_holder': 'Group Leader Teacher'})
        wizard.action_confirm()
        self.assertEqual((leader.bank_account, leader.bank_holder), (TEACHER_IBAN, 'Group Leader Teacher'))
        with self.assertRaises(UserError):
            self.mobility.with_user(self.other_teacher_user).action_my_bank_account()

    def test_a_participant_paid_and_withdrawn_is_warned(self):
        self._ready()
        payment = self._request()[:1]
        self._pay(payment, self.secretary_user)
        payment.group_participant_id.sudo().state = 'withdrawn'
        self.assertTrue(any(payment.partner_id.name in warning for warning in self.project._ems_economy_warnings()))

    def test_the_excel_lists_the_pocket_money_payments(self):
        self._ready()
        self._request()
        workbook = openpyxl.load_workbook(io.BytesIO(self.project._ems_economy_xlsx()))
        rows = list(workbook['Payments'].iter_rows(values_only=True))
        self.assertEqual(len([row for row in rows if row[1] == 'Pocket money']), 10)

    def test_the_portal_shows_the_student_their_pocket_money(self):
        self._ready()
        self._collective(7000)
        student = self.students[:1].sudo()
        grant = student._ems_portal_grant()
        self.assertEqual(grant[0][0][1], 700, "Their share of the collective expenses.")
        self.assertEqual(student.pocket_amount, 500)
        student._ems_portal_set_bank(TEACHER_IBAN, 'Family Holder')
        self.assertEqual(student.bank_account, TEACHER_IBAN)


@tagged('post_install', '-at_install')
class TestErasmusPocketMoneyTour(HttpCase, ErasmusPocketMoneyCase):
    """Issue #764 - the mobility technician requests the pocket money from the group and the
    Secretary pays it from the grant payments (the least privileged roles that do each part)."""

    def test_pocket_money_tour(self):
        self._ready()
        self._collective(7000)
        self.technician_user.lang = 'en_US'
        self.start_tour(f'/odoo/action-ems.action_erasmus_group_mobility/{self.mobility.id}',
                        'ems_erasmus_pocket_money_team', login=self.technician_user.login)
        payments = self.mobility.participant_ids.payment_ids
        self.assertEqual(len(payments), 10)
        self.secretary_user.lang = 'en_US'
        self.start_tour('/odoo/action-ems.action_erasmus_payment', 'ems_erasmus_pocket_money_secretary',
                        login=self.secretary_user.login)
        self.assertEqual(set(payments.mapped('state')), {'paid'})
