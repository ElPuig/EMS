import base64
from datetime import date

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestStudentUpdateWizard(TransactionCase):
    """ems.student_update_wizard: generic CSV bulk-UPDATE for already-enrolled
    students, matched by IDALU. Distinct from ems.student_import_wizard (xlsx,
    Esfera/SAGA, can also create students) — see student_update_wizard.md."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.student = cls.env['res.partner'].create({
            'name': 'Update Wizard Student', 'contact_type': 'student', 'student_id': '7000001',
        })
        cls.other_student = cls.env['res.partner'].create({
            'name': 'Other Update Wizard Student', 'contact_type': 'student', 'student_id': '7000002',
        })

    def _wizard(self, content):
        return self.env['ems.student_update_wizard'].create({
            'file': base64.b64encode(content.encode('utf-8')),
            'file_name': 'update.csv',
        })

    def _load(self, wizard):
        wizard.action_load_columns()
        return {c.name: c for c in self.env['ems.csv_column'].search([('wizard_id', '=', wizard.id)])}

    # --- action_load_columns ---------------------------------------------------

    def test_action_load_columns_creates_ordered_columns(self):
        wizard = self._wizard('IDALU,Nom,Telefon\n7000001,Test,600000000\n')
        self._load(wizard)
        ordered = self.env['ems.csv_column'].search([('wizard_id', '=', wizard.id)])
        self.assertEqual(ordered.mapped('name'), ['IDALU', 'Nom', 'Telefon'])

    def test_action_load_columns_without_file_raises(self):
        wizard = self.env['ems.student_update_wizard'].new({})
        with self.assertRaises(UserError):
            wizard.action_load_columns()

    def test_action_load_columns_empty_file_raises(self):
        wizard = self._wizard('')
        with self.assertRaises(UserError):
            wizard.action_load_columns()

    def test_action_load_columns_blank_headers_raises(self):
        wizard = self._wizard(',,\ndata,data,data\n')
        with self.assertRaises(UserError):
            wizard.action_load_columns()

    def test_action_load_columns_replaces_previous_mapping(self):
        wizard = self._wizard('IDALU,Nom\n7000001,Test\n')
        self._load(wizard)
        first_run_ids = self.env['ems.csv_column'].search([('wizard_id', '=', wizard.id)]).ids
        wizard.write({'file': base64.b64encode(b'IDALU,Cognom\n7000001,Test\n')})
        self._load(wizard)
        second_run = self.env['ems.csv_column'].search([('wizard_id', '=', wizard.id)])
        self.assertEqual(second_run.mapped('name'), ['IDALU', 'Cognom'])
        self.assertFalse(self.env['ems.csv_column'].browse(first_run_ids).exists())

    # --- fields_get label borrowing ----------------------------------------------

    def test_fields_get_borrows_partner_field_labels(self):
        expected = self.env['res.partner'].fields_get(['street'], ['string'])['street']['string']
        res = self.env['ems.student_update_wizard'].fields_get(['col_street'], ['string'])
        self.assertEqual(res['col_street']['string'], expected)

    def test_fields_get_borrows_bank_field_label(self):
        expected = self.env['res.partner.bank'].fields_get(['acc_holder_name'], ['string'])['acc_holder_name']['string']
        res = self.env['ems.student_update_wizard'].fields_get(['col_acc_holder'], ['string'])
        self.assertEqual(res['col_acc_holder']['string'], expected)

    # --- _parse_date ---------------------------------------------------------------

    def test_parse_date_accepts_known_formats(self):
        wizard = self.env['ems.student_update_wizard'].new({})
        self.assertEqual(wizard._parse_date('15/03/2010'), date(2010, 3, 15))
        self.assertEqual(wizard._parse_date('2010-03-15'), date(2010, 3, 15))
        self.assertEqual(wizard._parse_date('15-03-2010'), date(2010, 3, 15))

    def test_parse_date_invalid_returns_none(self):
        wizard = self.env['ems.student_update_wizard'].new({})
        self.assertIsNone(wizard._parse_date('not a date'))

    # --- action_update: guard + basic field mapping ------------------------------

    def test_action_update_without_match_key_raises(self):
        wizard = self._wizard('IDALU,Nom\n7000001,Test\n')
        self._load(wizard)
        with self.assertRaises(UserError):
            wizard.action_update()

    def test_action_update_writes_mapped_fields(self):
        wizard = self._wizard('IDALU,Nom,Telefon\n7000001,Updated Name,611222333\n')
        cols = self._load(wizard)
        wizard.write({'col_student_id': cols['IDALU'].id, 'col_name': cols['Nom'].id, 'col_phone': cols['Telefon'].id})
        wizard.action_update()

        self.student.invalidate_recordset(['name', 'phone'])
        self.assertEqual(self.student.name, 'Updated Name')
        self.assertEqual(self.student.phone, '611222333')
        self.assertIn('1', wizard.result_html)

    def test_action_update_skips_blank_idalu_rows(self):
        wizard = self._wizard('IDALU,Nom\n,Should Be Skipped\n7000001,Real Row\n')
        cols = self._load(wizard)
        wizard.write({'col_student_id': cols['IDALU'].id, 'col_name': cols['Nom'].id})
        wizard.action_update()
        self.student.invalidate_recordset(['name'])
        self.assertEqual(self.student.name, 'Real Row')
        ghost = self.env['res.partner'].search([('name', '=', 'Should Be Skipped')])
        self.assertFalse(ghost)

    def test_action_update_idalu_not_found_is_counted_not_errored(self):
        wizard = self._wizard('IDALU,Nom\n9999999,Nobody\n')
        cols = self._load(wizard)
        wizard.write({'col_student_id': cols['IDALU'].id, 'col_name': cols['Nom'].id})
        wizard.action_update()
        self.assertIn('IDALU not found', base64.b64decode(wizard.result_csv).decode('utf-8'))
        self.assertNotIn('Errors', wizard.result_html)

    def test_action_update_unparseable_date_logs_error_but_keeps_other_fields(self):
        wizard = self._wizard('IDALU,Nom,Naixement\n7000001,Date Fail Name,not-a-date\n')
        cols = self._load(wizard)
        wizard.write({
            'col_student_id': cols['IDALU'].id, 'col_name': cols['Nom'].id,
            'col_birth_date': cols['Naixement'].id,
        })
        wizard.action_update()
        self.student.invalidate_recordset(['name', 'birth_date'])
        self.assertEqual(self.student.name, 'Date Fail Name')
        self.assertFalse(self.student.birth_date)
        self.assertIn('could not parse date', wizard.result_html)

    def test_action_update_write_error_is_captured_and_continues(self):
        # nuss must be exactly 12 digits (res.partner._check_nuss) — a real, easy way
        # to force student.write() to raise without mocking anything.
        original_name = self.student.name
        wizard = self._wizard(
            'IDALU,Nom,NUSS\n'
            '7000001,Bad Nuss Row,abc\n'
            '7000002,Good Row,123456789012\n'
        )
        cols = self._load(wizard)
        wizard.write({'col_student_id': cols['IDALU'].id, 'col_name': cols['Nom'].id, 'col_nuss': cols['NUSS'].id})
        wizard.action_update()

        self.student.invalidate_recordset(['name', 'nuss'])
        self.other_student.invalidate_recordset(['name', 'nuss'])
        # Regression test for the cr.savepoint() fix: @api.constrains (_check_nuss)
        # runs AFTER the SQL write already flushed — without the savepoint, this
        # "failed" row's name change would silently have stuck despite being
        # reported as an error. The whole row's vals must roll back together.
        self.assertEqual(self.student.name, original_name)
        self.assertFalse(self.student.nuss)
        self.assertEqual(self.other_student.name, 'Good Row')
        self.assertEqual(self.other_student.nuss, '123456789012')
        self.assertIn('Errors', wizard.result_html)
        self.assertIn('error:', base64.b64decode(wizard.result_csv).decode('utf-8'))

    def test_action_update_escapes_error_content_in_result_html(self):
        # The only CSV-controlled text that ends up embedded in result_html is via
        # an error message (here: the unparseable date value) — a plain field like
        # Nom is written straight to the DB and never echoed back into the HTML.
        wizard = self._wizard('IDALU,Naixement\n7000001,<script>alert(1)</script>\n')
        cols = self._load(wizard)
        wizard.write({'col_student_id': cols['IDALU'].id, 'col_birth_date': cols['Naixement'].id})
        wizard.action_update()
        self.assertIn('&lt;script&gt;', wizard.result_html)
        self.assertNotIn('<script>alert(1)</script>', wizard.result_html)

    # --- action_update: bank account branch --------------------------------------

    def test_action_update_creates_new_bank_account(self):
        wizard = self._wizard('IDALU,IBAN,Titular\n7000001,ES9121000418450200051332,John Doe\n')
        cols = self._load(wizard)
        wizard.write({'col_student_id': cols['IDALU'].id, 'col_iban': cols['IBAN'].id, 'col_acc_holder': cols['Titular'].id})
        wizard.action_update()
        bank = self.env['res.partner.bank'].search([('partner_id', '=', self.student.id)])
        self.assertEqual(len(bank), 1)
        self.assertEqual(bank.acc_number.replace(' ', ''), 'ES9121000418450200051332')
        self.assertEqual(bank.acc_holder_name, 'John Doe')

    def test_action_update_reactivates_existing_bank_account(self):
        existing = self.env['res.partner.bank'].create({
            'acc_number': 'ES9121000418450200051332', 'partner_id': self.student.id,
        })
        existing.active = False
        wizard = self._wizard('IDALU,IBAN,Titular\n7000001,ES9121000418450200051332,Jane Doe\n')
        cols = self._load(wizard)
        wizard.write({'col_student_id': cols['IDALU'].id, 'col_iban': cols['IBAN'].id, 'col_acc_holder': cols['Titular'].id})
        wizard.action_update()
        self.assertTrue(existing.active)
        self.assertEqual(existing.acc_holder_name, 'Jane Doe')

    def test_action_update_archives_other_bank_accounts(self):
        old = self.env['res.partner.bank'].create({
            'acc_number': 'ES8200000000000000000000', 'partner_id': self.student.id,
        })
        wizard = self._wizard('IDALU,IBAN\n7000001,ES9121000418450200051332\n')
        cols = self._load(wizard)
        wizard.write({'col_student_id': cols['IDALU'].id, 'col_iban': cols['IBAN'].id})
        wizard.action_update()
        self.assertFalse(old.active)

    def test_action_update_blank_iban_leaves_bank_untouched(self):
        wizard = self._wizard('IDALU,Nom,IBAN\n7000001,No Bank Change,\n')
        cols = self._load(wizard)
        wizard.write({'col_student_id': cols['IDALU'].id, 'col_name': cols['Nom'].id, 'col_iban': cols['IBAN'].id})
        wizard.action_update()
        self.assertFalse(self.env['res.partner.bank'].search([('partner_id', '=', self.student.id)]))

    # NOTE: the bank-account except Exception branch (a malformed/rejected IBAN
    # reported as "(bank)" in errors, without blocking the row's other student
    # fields) is real but not covered here — base_iban's own validation turned
    # out lenient enough in practice (garbage checksums did not reliably raise)
    # that a deterministic trigger wasn't found without deeper investigation.
    # Flagged in student_update_wizard.md rather than forcing a brittle test.
