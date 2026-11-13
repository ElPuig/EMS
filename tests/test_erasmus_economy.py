import base64
import io
from datetime import date

import openpyxl

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import Form
from odoo.tests.common import HttpCase, tagged

from .common import create_role_user
from .test_erasmus import PDF
from .test_erasmus_grant import ErasmusGrantCase
from .test_erasmus_group_mobility import ErasmusGroupMobilityCase


class ErasmusEconomyMixin:
    """Issue #762 - shared steps: a project's rates, its expenses and their payment."""

    def _rates(self, project, *bands, mobility_type='student_short', year=None, **vals):
        """One rate per (band_from, band_to, amount) of the project's call year."""
        return self.env['ems.erasmus.support.rate'].create([{
            'call_year': year or project.call_year, 'kind': project.kind, 'mobility_type': mobility_type,
            'band_from': band_from, 'band_to': band_to, 'amount': amount, **vals,
        } for band_from, band_to, amount in bands])

    def _expense(self, project, amount, user=None, **vals):
        Expense = self.env['ems.erasmus.expense'].with_user(user) if user else self.env['ems.erasmus.expense']
        return Expense.create({'project_id': project.id, 'concept': 'Working meal', 'amount': amount, **vals})

    def _pay(self, records, user):
        action = records.with_user(user).action_register_transfer()
        self.env['ems.erasmus.transfer.wizard'].with_user(user).with_context(action['context']).create({
            'receipt': base64.b64encode(PDF), 'receipt_filename': 'receipt.pdf'}).action_confirm()


@tagged('post_install', '-at_install')
class TestErasmusEconomy(ErasmusEconomyMixin, ErasmusGrantCase):
    """Issue #762 - the economy of a project with individual mobilities (acceptance tests 1-10, 12-15)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.director_user = create_role_user(cls, 'director', 'test_economy_director')
        # A call year with no seeded rates: each test sets its own (the seeded ones are tested apart).
        cls.project = cls.env['ems.erasmus.project'].create({
            'name': '2019-1-ES01-KA121-VET-000000762', 'kind': 'ka121_vet', 'budget': 10000})

    def _committed_mobility(self, grant=1500):
        first, second = self._preparing()
        first.write({'project_id': self.project.id, 'grant_amount': grant})
        return first, second

    def test_call_year_comes_from_the_agreement_number_and_the_grant_is_available(self):
        self.assertEqual(self.project.call_year, 2019)
        self.assertEqual((self.project.grant_current, self.project.available_amount), (10000, 10000))
        self.env['ems.erasmus.project.amendment'].create({'project_id': self.project.id, 'amount': 500,
                                                          'name': 'Amendment 1'})
        self.assertEqual((self.project.grant_current, self.project.available_amount), (10500, 10500))
        self.assertIn('Amendment 1', self.project.message_ids[0].body + self.project.message_ids[0].preview,
                      "Every economic change stays in the project's history.")

    def test_lines_are_added_from_the_project_form_of_a_project_with_mobilities(self):
        """Review 2026-11-05 (B2): adding an amendment or a SEPIE transfer in the Economy tab of a
        project with mobilities recomputed their records while unsaved and crashed."""
        self._committed_mobility()
        self.assertTrue(self.project.mobility_ids._ems_record_lines(), "The mobility has documents to sort.")
        expense = self._expense(self.project, 40)
        self.assertIn(expense.name, self.project.economy_warnings, "An expense without a receipt is warned about.")
        with Form(self.project.with_user(self.erasmus_user)) as form:
            with form.amendment_ids.new() as amendment:
                amendment.amount = 300
                amendment.name = 'Amendment from the form'
            with form.income_ids.new() as income:
                income.amount = 1000
            form.support_adjustment = 25
            form.support_adjustment_reason = 'Agreement annex'
        self.assertEqual((self.project.grant_current, self.project.received_amount), (10300, 1000))

    def test_files_uploaded_with_a_new_record_follow_its_access(self):
        """Review 2026-11-05 (B1): a file uploaded in a form before saving has no res_id, and Odoo
        only lets its uploader read it: the team and the Director could not open the expense nor
        the project. Saved, every economic record owns its files."""
        def upload(user, model):
            return self.env['ir.attachment'].with_user(user).create(
                {'name': 'invoice.pdf', 'raw': PDF, 'res_model': model, 'res_id': 0})
        expense = self._expense(self.project, 90, user=self.secretary_user, attachment_ids=[
            (6, 0, upload(self.secretary_user, 'ems.erasmus.expense').ids)])
        amendment = self.env['ems.erasmus.project.amendment'].with_user(self.erasmus_user).create({
            'project_id': self.project.id, 'amount': 100,
            'attachment_ids': [(6, 0, upload(self.erasmus_user, 'ems.erasmus.project.amendment').ids)]})
        diffusion = self.env['ems.erasmus.diffusion'].with_user(self.erasmus_user).create({
            'name': 'Information session',
            'attachment_ids': [(6, 0, upload(self.erasmus_user, 'ems.erasmus.diffusion').ids)]})
        for record, reader in ((expense, self.director_user), (expense, self.erasmus_user),
                               (amendment, self.director_user), (diffusion, self.erasmus_user)):
            self.assertEqual(record.attachment_ids.res_id, record.id)
            self.assertEqual(record.with_user(reader).attachment_ids.with_user(reader).raw, PDF)
        self.env.invalidate_all()
        self.project.with_user(self.director_user).read(['expense_ids', 'economy_warnings'])

    def test_sepie_transfers_are_received_money_not_budget(self):
        self.env['ems.erasmus.project.income'].create([
            {'project_id': self.project.id, 'kind': 'prefinancing', 'amount': 8000, 'date': date(2025, 9, 1)},
            {'project_id': self.project.id, 'kind': 'balance', 'amount': 1000, 'date': date(2027, 3, 1)}])
        self.assertEqual((self.project.received_amount, self.project.to_receive_amount), (9000, 1000))
        self.assertEqual(self.project.available_amount, 10000, "Received money is not the available budget.")
        self.assertEqual(self.project.final_payment_date, date(2027, 3, 1), "The balance is the final payment.")
        with self.assertRaises(ValidationError):
            self.env['ems.erasmus.project.income'].create({'project_id': self.project.id, 'amount': 0})

    def test_grant_agreement_is_an_economic_document_of_the_project(self):
        document = self.env['ems.erasmus.project.document'].with_context(default_category='03_Economia').create({
            'project_id': self.project.id, 'name': 'Grant agreement',
            'attachment_ids': [(0, 0, {'name': 'agreement.pdf', 'raw': PDF})]})
        economic = self.project.with_user(self.director_user).document_ids.filtered(
            lambda line: line.category == '03_Economia')
        self.assertEqual(economic, document, "Issue #784: in the Documentation tab, not repeated in Economy.")
        self.assertEqual(economic.attachment_ids.raw, PDF)

    def test_a_mobility_is_a_forecast_until_confirmed_and_then_committed(self):
        first, _second = self._accepted()
        first.write({'project_id': self.project.id, 'grant_amount': 1500})
        self.assertEqual((first.econ_state, first.econ_forecast, first.econ_committed), ('forecast', 1500, 0))
        self.assertEqual((self.project.forecast_amount, self.project.available_amount), (1500, 10000))
        first._ems_set_state('preparing')
        self.assertEqual((first.econ_state, first.econ_committed, first.econ_pending), ('committed', 1500, 1500))
        self.assertEqual((self.project.committed_amount, self.project.available_amount), (1500, 8500))

    def test_paying_moves_from_pending_to_paid_without_a_second_deduction(self):
        first, _second = self._committed_mobility()
        first.action_request_prefinancing()
        self._pay(first.payment_ids, self.secretary_user)
        self.assertEqual((first.econ_state, first.econ_paid, first.econ_pending), ('partial', 1200, 300))
        self.assertEqual((self.project.paid_amount, self.project.pending_amount, self.project.available_amount),
                         (1200, 300, 8500))
        first.action_request_final_payment()
        self._pay(first.payment_ids.filtered(lambda payment: payment.state == 'to_pay'), self.secretary_user)
        self.assertEqual((first.econ_state, first.econ_paid, first.econ_pending), ('paid', 1500, 0))
        self.assertEqual(self.project.available_amount, 8500)

    def test_an_invoice_paid_out_of_a_grant_is_not_an_extra_expense(self):
        first, _second = self._committed_mobility()
        invoice = self._invoice(first, 400, project_id=self.project.id)
        self._transfer(invoice, self.secretary_user)
        self.assertEqual((first.econ_committed, first.econ_paid), (1500, 400))
        self.assertEqual((self.project.committed_amount, self.project.other_expense_amount), (1500, 0))
        loose = self._invoice(self.env['ems.erasmus.mobility'], 250, name='F-TEST-2', project_id=self.project.id)
        self.assertEqual((self.project.committed_amount, self.project.other_expense_amount), (1750, 250),
                         "An invoice of no mobility is one of the project's other expenses.")
        self.assertTrue(loose)

    def test_a_grant_change_updates_the_commitment_by_the_difference(self):
        first, _second = self._committed_mobility()
        first.grant_amount = 1800
        self.assertEqual((self.project.committed_amount, self.project.available_amount), (1800, 8200))

    def test_a_cancelled_mobility_releases_what_was_not_paid(self):
        first, _second = self._committed_mobility()
        first.action_request_prefinancing()
        self._pay(first.payment_ids, self.secretary_user)
        first.cancel_reason = 'Travel documents not handed in'
        first.action_cancel()
        self.assertEqual((first.econ_state, first.econ_committed), ('adjusted', 1200))
        self.assertEqual(self.project.available_amount, 8800)
        self.assertIn('is cancelled with', self.project.economy_warnings)
        first.recovered_amount = 1200
        self.assertEqual((first.econ_state, first.econ_committed, self.project.available_amount),
                         ('cancelled', 0, 10000))

    def test_part_of_a_cancelled_mobility_given_back_still_counts_the_rest(self):
        first, _second = self._committed_mobility()
        first.action_request_prefinancing()
        self._pay(first.payment_ids, self.secretary_user)
        first.cancel_reason = 'Illness'
        first.action_cancel()
        first.recovered_amount = 500
        self.assertEqual((first.econ_state, first.econ_committed, first.econ_paid), ('adjusted', 700, 700))
        self.assertEqual((self.project.committed_amount, self.project.paid_amount), (700, 700))

    def test_each_warning_names_what_to_check(self):
        """Review 2026-11-05: only one warning was tested."""
        first, second = self._committed_mobility()
        second.write({'project_id': self.project.id, 'grant_amount': 300})
        self._transfer(self._invoice(second, 500, project_id=self.project.id), self.secretary_user)
        first.action_request_prefinancing()
        expense = self._expense(self.project, 40)
        warnings = self.project.economy_warnings
        self.assertIn(f'{expense.name}', warnings, "An expense without an invoice or receipt.")
        self.assertIn('requested payments still to make', warnings, "The prefinancing and the expense still to transfer.")
        self.assertIn(second.partner_id.name, warnings, "Paid above their grant.")
        self.assertIn('organisational support', warnings, "No rate for the call year.")
        self._pay(first.payment_ids, self.secretary_user)
        first.cancel_reason = 'Illness'
        first.action_cancel()
        self.assertIn('is cancelled with', self.project.economy_warnings)
        self.assertEqual(self.project.economy_warning_count, len(self.project._ems_economy_warnings()))

    def test_moving_a_mobility_to_another_project_moves_its_figures(self):
        first, _second = self._committed_mobility()
        other = self.env['ems.erasmus.project'].create({'name': '2026-1-ES01-KA121-VET-000000763',
                                                        'kind': 'ka121_vet', 'budget': 5000})
        first.project_id = other
        self.assertEqual((self.project.committed_amount, other.committed_amount), (0, 1500))

    def test_expenses_count_once_registered_and_paying_them_deducts_nothing_more(self):
        expense = self._expense(self.project, 300, user=self.secretary_user, category='organisational_support')
        self.assertTrue(expense.name.startswith('DESP-'))
        self.assertEqual((self.project.available_amount, self.project.support_expense_amount), (9700, 300))
        self.assertIn(expense.name, self.project.economy_warnings, "No receipt yet.")
        self._pay(expense, self.secretary_user)
        self.assertEqual((expense.state, self.project.available_amount, self.project.paid_amount), ('paid', 9700, 300))
        self.assertTrue(expense.receipt_ids)
        with self.assertRaises(UserError):
            expense.with_user(self.erasmus_user).amount = 200

    def test_a_paid_expense_is_corrected_with_a_reason_that_stays(self):
        expense = self._expense(self.project, 300)
        self._pay(expense, self.secretary_user)
        action = expense.with_user(self.erasmus_user).action_correct()
        wizard = self.env[action['res_model']].with_user(self.erasmus_user).with_context(action['context']).create(
            {'reason': 'Corrected invoice'})
        wizard.amount = 280
        wizard.action_confirm()
        self.assertEqual((expense.amount, expense.corrected), (280, True))
        self.assertIn('Corrected invoice', expense.message_ids[0].body)
        self.assertIn('changed after being paid', self.project.economy_warnings)
        with self.assertRaises(AccessError):
            expense.with_user(self.secretary_user).action_correct()

    def _correct(self, expense, amount, reason='Corrected invoice'):
        action = expense.with_user(self.erasmus_user).action_correct()
        wizard = self.env[action['res_model']].with_user(self.erasmus_user).with_context(action['context']).create(
            {'reason': reason})
        wizard.amount = amount
        wizard.action_confirm()

    def test_a_paid_expense_corrected_upwards_leaves_the_difference_to_pay(self):
        """Review 2026-11-05, adriamt's decision: what was transferred stays paid and the difference
        is a new expense for the Secretary to pay; corrected downwards, what was paid above it is
        still paid and the project warns about it."""
        expense = self._expense(self.project, 75, concept='Working meal')
        self._pay(expense, self.secretary_user)
        self._correct(expense, 80)
        difference = self.project.expense_ids - expense
        self.assertEqual((expense.amount, expense.state), (75, 'paid'))
        self.assertEqual((difference.amount, difference.state, difference.corrected_from_id), (5, 'to_pay', expense))
        self.assertTrue(difference.activity_ids, "A task for the Secretary to pay the difference.")
        self.assertIn(difference.name, expense.message_ids[0].body)
        self.assertEqual((self.project.committed_amount, self.project.paid_amount, self.project.pending_amount),
                         (80, 75, 5))
        other = self._expense(self.project, 100)
        self._pay(other, self.secretary_user)
        self._correct(other, 90)
        self.assertEqual((other.amount, other.transferred_amount), (90, 100))
        self.assertEqual((self.project.committed_amount, self.project.paid_amount), (180, 175),
                         "What was really transferred counts until it is given back.")
        self.assertIn(f'{other.name} was paid', self.project.economy_warnings)
        self.assertIn('above its corrected amount', self.project.economy_warnings)

    def test_an_expense_transfer_is_undone_with_its_reason_and_a_cancelled_one_restored(self):
        expense = self._expense(self.project, 300)
        self._pay(expense, self.secretary_user)
        self._undo(expense, self.secretary_user, reason='Wrong expense')
        self.assertEqual((expense.state, self.project.paid_amount, self.project.available_amount), ('to_pay', 0, 9700))
        self.assertIn('Wrong expense', expense.message_ids[0].body)
        expense.with_user(self.erasmus_user).action_cancel()
        expense.with_user(self.erasmus_user).action_restore()
        self.assertEqual((expense.state, self.project.available_amount), ('to_pay', 9700))
        self.assertTrue(expense.activity_ids, "Restored, it is a task for the Secretary again.")

    def test_a_cancelled_expense_counts_nothing(self):
        expense = self._expense(self.project, 300)
        expense.with_user(self.erasmus_user).action_cancel()
        self.assertEqual(self.project.available_amount, 10000)
        with self.assertRaises(UserError):
            expense.with_user(self.secretary_user).action_register_transfer()

    def test_organisational_support_follows_its_call_year_bands_and_minimum(self):
        first, second = self._committed_mobility()
        second.project_id = self.project
        first.write({'date_start': date(2027, 6, 1), 'date_end': date(2027, 6, 30)})
        second.write({'date_start': date(2027, 7, 1), 'date_end': date(2027, 7, 5)})
        self._rates(self.project, (1, 1, 500), (2, 0, 300))
        self._rates(self.project, (1, 0, 999), year=2018)
        self.assertEqual((self.project.support_forecast, self.project.support_generated), (800, 0))
        (first | second)._ems_set_state('done')
        self.assertEqual(self.project.support_generated, 800, "The second participant is in the second band.")
        self.env['ems.erasmus.support.rate'].search([('call_year', '=', 2019)]).min_days = 10
        self.assertEqual(self.project.support_generated, 500, "A stay shorter than the minimum generates none.")
        self.project.write({'support_adjustment': 50, 'support_adjustment_reason': 'Agreement annex'})
        self._expense(self.project, 120, category='organisational_support')
        self.assertEqual((self.project.support_generated, self.project.support_balance), (550, 430))
        self.assertEqual(self.project.grant_current, 10000, "The support is never added to the grant.")
        with self.assertRaises(ValidationError):
            self.project.support_adjustment_reason = False

    def test_a_whole_project_band_counts_every_kind_of_mobility_and_shows_that_position(self):
        """Review 2026-11-05 (D5): with band_scope 'project' (KA131-HED) the rate was right but the
        position shown (Excel) was the one among the same kind of mobility."""
        first, second = self._committed_mobility()
        second.project_id = self.project
        first.write({'date_start': date(2027, 6, 1), 'date_end': date(2027, 6, 30)})
        second.write({'date_start': date(2027, 7, 1), 'date_end': date(2027, 10, 30)})
        self.assertEqual((first.support_type, second.support_type), ('student_short', 'student_long'))
        self._rates(self.project, (1, 1, 400), (2, 0, 230), band_scope='project')
        self._rates(self.project, (1, 1, 400), (2, 0, 230), mobility_type='student_long', band_scope='project')
        lines = self.project._ems_support_lines()
        self.assertEqual([(line['forecast_position'], line['forecast']) for line in lines], [(1, 400), (2, 230)])

    def test_an_old_project_keeps_its_call_year_rates(self):
        first, _second = self._committed_mobility()
        first._ems_set_state('done')
        self._rates(self.project, (1, 0, 350))
        self.assertEqual(self.project.support_generated, 350)
        self._rates(self.project, (1, 0, 999), year=2027)
        self.assertEqual(self.project.support_generated, 350)

    def test_seeded_rates_follow_the_funding_rules_of_each_action(self):
        Rate = self.env['ems.erasmus.support.rate']
        vet = Rate.search([('call_year', '=', 2025), ('kind', '=', 'ka121_vet')])
        hed = Rate.search([('call_year', '=', 2026), ('kind', '=', 'ka131_hed')])
        amount = lambda rates, kind, same, project: rates._ems_rate_for(
            kind, {'same': same, 'project': project}, 30)[0].amount
        self.assertEqual(amount(vet, 'student_short', 100, 250), 350, "VET counts the same kind of mobility.")
        self.assertEqual(amount(vet, 'student_short', 101, 101), 200)
        self.assertEqual((amount(vet, 'student_long', 500, 500), amount(vet, 'student_group', 1, 1),
                          amount(vet, 'staff_course', 1, 1), amount(vet, 'non_associated', 1, 1)), (500, 100, 100, 500))
        self.assertEqual(amount(hed, 'staff_job', 3, 100), 400, "HED counts students and staff together.")
        self.assertEqual(amount(hed, 'student_short', 3, 101), 230)

    def test_the_kind_of_mobility_comes_from_its_dates_and_activity_unless_set_by_hand(self):
        first, _second = self._committed_mobility()
        project = self.env['ems.erasmus.project'].create({'name': '2025-1-ES01-KA121-VET-000000765',
                                                          'kind': 'ka121_vet', 'budget': 1})
        first.write({'project_id': project.id, 'date_start': date(2027, 6, 1), 'date_end': date(2027, 6, 30)})
        self.assertEqual((first.support_type, project.support_forecast), ('student_short', 350))
        first.date_end = date(2027, 9, 30)
        self.assertEqual((first.support_type, project.support_forecast), ('student_long', 500))
        first.support_type = 'non_associated'
        first.date_end = date(2027, 6, 30)
        self.assertEqual(first.support_type, 'non_associated', "A type chosen by hand is kept.")

    def test_missing_rates_and_overspending_are_warned(self):
        first, _second = self._committed_mobility(grant=12000)
        self.assertIn('above the current grant', self.project.economy_warnings)
        self.assertIn('organisational support', self.project.economy_warnings)
        self.assertTrue(first)
        with self.assertRaises(ValidationError):
            self._rates(self.project, (1, 10, 100), (5, 0, 50))

    def test_permissions_of_coordination_secretary_and_director(self):
        project = self.project
        self.assertEqual(project.with_user(self.director_user).available_amount, 10000)
        with self.assertRaises(AccessError):
            project.with_user(self.director_user).budget = 1
        with self.assertRaises(AccessError):
            self._expense(project, 10, user=self.director_user)
        with self.assertRaises(AccessError):
            self.env['ems.erasmus.project.amendment'].with_user(self.secretary_user).create(
                {'project_id': project.id, 'amount': 1})
        with self.assertRaises(AccessError):
            project.with_user(self.hos_user).read(['available_amount'])
        with self.assertRaises(AccessError):
            self.env['ems.erasmus.payment'].with_user(self.director_user).search([]).read(['bank_account'])
        with self.assertRaises(AccessError):
            self.env['ems.erasmus.support.rate'].with_user(self.secretary_user).create(
                {'call_year': 2025, 'kind': 'ka121_vet', 'amount': 1})
        expense = self._expense(project, 10, user=self.secretary_user)
        self._pay(expense, self.secretary_user)
        with self.assertRaises(AccessError):
            self._pay(self._expense(project, 10), self.erasmus_user)

    def test_excel_totals_match_the_panel(self):
        first, _second = self._committed_mobility()
        first.action_request_prefinancing()
        self._pay(first.payment_ids, self.secretary_user)
        self._expense(self.project, 300, category='organisational_support')
        content = self.project.with_user(self.director_user)._ems_economy_xlsx()
        workbook = openpyxl.load_workbook(io.BytesIO(content))
        summary = {row[0]: row[1] for row in workbook.worksheets[0].iter_rows(values_only=True)}
        self.assertEqual(summary['Committed'], self.project.committed_amount)
        self.assertEqual(summary['Paid'], self.project.paid_amount)
        self.assertEqual(summary['Available'], self.project.available_amount)
        self.assertEqual(summary['Forecast'], 0)
        self.assertEqual(len(workbook.worksheets), 6)
        with self.assertRaises(AccessError):
            self.project.with_user(self.teacher_user)._ems_economy_xlsx()


@tagged('post_install', '-at_install')
class TestErasmusGroupEconomy(ErasmusEconomyMixin, ErasmusGroupMobilityCase):
    """Issue #762 - a group mobility counts its grant once and only its students generate
    organisational support (acceptance test 11)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.secretary_user = create_role_user(cls, 'secretary', 'test_economy_group_secretary')

    def test_each_participant_has_a_grant_counted_once_and_only_students_generate_support(self):
        """The seeded 2025 KA121-VET rates: 100 € per student of a group mobility, none for its
        accompanying teachers (8 students and 2 teachers: 800 €)."""
        self.project.write({'name': '2025-1-ES01-KA121-VET-000000764', 'budget': 20000})
        self.assertEqual(self.project.support_forecast, 100 * self.mobility.student_places)
        self._approved()
        participants = self.mobility.grant_participant_ids
        students = participants.filtered(lambda participant: participant.role == 'student')
        teachers = participants - students
        self.assertTrue(teachers, "The accompanying teachers take part too.")
        students.write({'grant_amount': 900})
        teachers.write({'grant_amount': 1200})
        total = 900 * len(students) + 1200 * len(teachers)
        self.assertEqual((self.mobility.grant_amount, self.mobility.econ_state), (total, 'committed'))
        self.assertEqual(self.project.committed_amount, total, "Each participant's grant counts once.")
        self.mobility.sudo()._ems_set_state('return')
        self.assertEqual(self.project.support_generated, 100 * len(students))
        if len(students) == 8 and len(teachers) == 2:
            self.assertEqual(self.project.support_generated, 800)
        invoice = self.env['ems.erasmus.invoice'].create({
            'name': 'F-GROUP-1', 'amount': 4000, 'project_id': self.project.id,
            'group_mobility_id': self.mobility.id})
        self.assertEqual(self.project.committed_amount, total, "A collective invoice is part of the grants.")
        self._pay(invoice, self.secretary_user)
        self.assertEqual((self.mobility.econ_paid, self.mobility.econ_state), (4000, 'partial'))
        with self.assertRaises(AccessError):
            students[:1].with_user(self.leader_user).grant_amount = 1
        students[:1].sudo().state = 'withdrawn'
        self.assertEqual(self.mobility.grant_amount, total - 900, "A withdrawn participant's grant never counts.")


@tagged('post_install', '-at_install')
class TestErasmusEconomyTour(ErasmusEconomyMixin, HttpCase, ErasmusGrantCase):
    """Issue #762 - the Secretary opens the economic panel (list and comparison), a project's Economy
    tab and registers an expense."""

    def test_economy_tour(self):
        project = self.env['ems.erasmus.project'].create({
            'name': '2019-1-ES01-KA131-HED-000000762', 'kind': 'ka131_hed', 'budget': 5000})
        self._expense(project, 75, concept='Merchandising')
        self.secretary_user.lang = 'en_US'
        self.start_tour('/odoo/action-ems.action_erasmus_project', 'ems_erasmus_economy_tour', login=self.secretary_user.login)
        expense = self.env['ems.erasmus.expense'].search([('concept', '=', 'Tour dissemination service')])
        self.assertEqual((expense.project_id, expense.amount), (project, 120))
