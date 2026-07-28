import base64
import io
from datetime import date, datetime

from odoo.tests.common import TransactionCase


class TestStudentImportWizard(TransactionCase):
    """Focused coverage for _get_or_create_student: the dedup/reactivation
    logic touched by the archive-on-withdrawal change, not a full xlsx
    column-mapping suite (see action_import / _process_row for that)."""

    def _wizard(self):
        return self.env['ems.student_import_wizard'].create({
            'file': base64.b64encode(b'placeholder'), 'file_name': 'esfera.xlsx',
        })

    def test_creates_new_student(self):
        wizard = self._wizard()
        stats = {'created': 0, 'updated': 0, 'errors': [], 'log': []}
        student = wizard._get_or_create_student('8000001', {
            'name': 'Brand New', 'contact_type': 'student',
            'student_id': '8000001', 'active': True,
        }, stats)
        self.assertEqual(student.name, 'Brand New')
        self.assertTrue(student.active)
        self.assertEqual(stats['created'], 1)

    def test_updates_existing_student(self):
        existing = self.env['res.partner'].create({
            'name': 'Old Name', 'contact_type': 'student', 'student_id': '8000002'})
        wizard = self._wizard()
        stats = {'created': 0, 'updated': 0, 'errors': [], 'log': []}
        student = wizard._get_or_create_student('8000002', {
            'name': 'New Name', 'contact_type': 'student',
            'student_id': '8000002', 'active': True,
        }, stats)
        self.assertEqual(student, existing)
        self.assertEqual(student.name, 'New Name')
        self.assertEqual(stats['updated'], 1)

    def test_reactivates_archived_withdrawal_instead_of_duplicating(self):
        # A withdrawal is archived (active=False) as part of the exit, mirroring
        # hr.employee. Re-importing the same RALC must find and reactivate that
        # record, not silently create a duplicate partner.
        withdrawn = self.env['res.partner'].create({
            'name': 'Old Name', 'contact_type': 'withdrawal', 'student_id': '8000003'})
        withdrawn.write({'active': False})
        wizard = self._wizard()
        stats = {'created': 0, 'updated': 0, 'errors': [], 'log': []}
        student = wizard._get_or_create_student('8000003', {
            'name': 'New Name', 'contact_type': 'student',
            'student_id': '8000003', 'active': True,
        }, stats)
        self.assertEqual(student, withdrawn)
        self.assertTrue(student.active)
        self.assertEqual(student.contact_type, 'student')
        self.assertEqual(stats['updated'], 1)
        matches = self.env['res.partner'].with_context(active_test=False).search(
            [('student_id', '=', '8000003')])
        self.assertEqual(len(matches), 1)

    # --- _find_headers / _check_required_columns --------------------------------

    def test_find_headers_locates_grup_classe_row(self):
        wizard = self._wizard()
        ws = self._sheet([
            ['Some export title'],
            [],
            ['Grup Classe', 'Nom', 'Primer Cognom'],
            ['TSIW A', 'Test', 'Student'],
        ])
        idx, col_map = wizard._find_headers(ws)
        self.assertEqual(idx, 3)
        self.assertEqual(col_map['Grup Classe'], 0)
        self.assertEqual(col_map['Nom'], 1)

    def test_find_headers_returns_none_when_absent(self):
        wizard = self._wizard()
        ws = self._sheet([['Nom', 'Cognom'], ['Test', 'Student']])
        idx, col_map = wizard._find_headers(ws)
        self.assertIsNone(idx)
        self.assertEqual(col_map, {})

    def test_check_required_columns_reports_missing(self):
        wizard = self._wizard()
        missing = wizard._check_required_columns({'Grup Classe': 0, 'Nom': 1})
        self.assertIn('Primer Cognom', missing)
        self.assertNotIn('Grup Classe', missing)

    def test_check_required_columns_accepts_either_trailing_space_variant(self):
        wizard = self._wizard()
        full_map = {col: i for i, col in enumerate(wizard._REQUIRED_COLUMNS)}
        full_map['Tutor 1 - 1r cognom'] = len(full_map)
        full_map['Tutor 2 - 1r cognom '] = len(full_map)
        missing = wizard._check_required_columns(full_map)
        self.assertEqual(missing, [])

    # --- parsing helpers ---------------------------------------------------------

    def test_parse_documents_pairs_types_and_numbers(self):
        wizard = self._wizard()
        docs = wizard._parse_documents('12345678A - X1234567L', 'DNI - NIE')
        self.assertEqual(docs, {'DNI': '12345678A', 'NIE': 'X1234567L'})

    def test_parse_documents_empty_input(self):
        wizard = self._wizard()
        self.assertEqual(wizard._parse_documents('', 'DNI'), {})
        self.assertEqual(wizard._parse_documents(None, 'DNI'), {})

    def test_parse_date_accepts_known_formats(self):
        wizard = self._wizard()
        self.assertEqual(wizard._parse_date('15/03/2010'), date(2010, 3, 15))
        self.assertEqual(wizard._parse_date('2010-03-15'), date(2010, 3, 15))
        self.assertEqual(wizard._parse_date('15-03-2010'), date(2010, 3, 15))

    def test_parse_date_invalid_returns_false(self):
        wizard = self._wizard()
        self.assertFalse(wizard._parse_date('not a date'))
        self.assertFalse(wizard._parse_date(''))

    def test_build_street_joins_present_parts_only(self):
        wizard = self._wizard()
        street = wizard._build_street('Carrer', 'Major', '12', None, '', '2n', '3a', None)
        self.assertEqual(street, 'Carrer Major 12 2n 3a')

    def test_build_street_all_empty_returns_false(self):
        wizard = self._wizard()
        self.assertFalse(wizard._build_street(None, None, None, None, None, None, None, None))

    def test_parse_contact_value_splits_phone_and_email(self):
        wizard = self._wizard()
        phone, email = wizard._parse_contact_value('612345678 - test@example.com')
        self.assertEqual(phone, '612345678')
        self.assertEqual(email, 'test@example.com')

    def test_parse_contact_value_phone_only(self):
        wizard = self._wizard()
        phone, email = wizard._parse_contact_value('612345678')
        self.assertEqual(phone, '612345678')
        self.assertIsNone(email)

    def test_split_phone_mobile_recognizes_spanish_mobile(self):
        wizard = self._wizard()
        phone, mobile = wizard._split_phone_mobile('612345678')
        self.assertIsNone(phone)
        self.assertEqual(mobile, '612345678')

    def test_split_phone_mobile_recognizes_spanish_landline(self):
        wizard = self._wizard()
        phone, mobile = wizard._split_phone_mobile('912345678')
        self.assertEqual(phone, '912345678')
        self.assertIsNone(mobile)

    def test_split_phone_mobile_falls_back_gracefully_on_garbage(self):
        wizard = self._wizard()
        phone, mobile = wizard._split_phone_mobile('not-a-number')
        self.assertEqual(phone, 'not-a-number')
        self.assertIsNone(mobile)

    # --- _deduce_relation_type ----------------------------------------------------

    def test_deduce_relation_type_recognizes_mother(self):
        wizard = self._wizard()
        rel, is_fallback = wizard._deduce_relation_type('Mare biològica')
        self.assertEqual(rel, self.env.ref('ems.relation_type_mother'))
        self.assertFalse(is_fallback)

    def test_deduce_relation_type_recognizes_father(self):
        wizard = self._wizard()
        rel, is_fallback = wizard._deduce_relation_type('Padre')
        self.assertEqual(rel, self.env.ref('ems.relation_type_father'))
        self.assertFalse(is_fallback)

    def test_deduce_relation_type_falls_back_to_tutor(self):
        wizard = self._wizard()
        rel, is_fallback = wizard._deduce_relation_type('Cangur habitual')
        self.assertEqual(rel, self.env.ref('ems.relation_type_tutor'))
        self.assertTrue(is_fallback)

    def test_deduce_relation_type_empty_text_falls_back_to_tutor(self):
        wizard = self._wizard()
        rel, is_fallback = wizard._deduce_relation_type(None)
        self.assertEqual(rel, self.env.ref('ems.relation_type_tutor'))
        self.assertTrue(is_fallback)

    # --- _get_or_create_family ----------------------------------------------------

    def test_get_or_create_family_matches_existing_by_document(self):
        existing = self.env['res.partner'].create({
            'name': 'Old Family Name', 'contact_type': 'family', 'document_id': '11111111A'})
        wizard = self._wizard()
        family, accio = wizard._get_or_create_family(
            'New Family Name', '11111111A', '612345678', None, 'family@example.com', {})
        self.assertEqual(family, existing)
        self.assertEqual(accio, 'Actualitzat')
        self.assertEqual(family.phone, '612345678')
        self.assertEqual(family.email, 'family@example.com')

    def test_get_or_create_family_without_document_always_creates_new(self):
        # KNOWN LIMITATION (documented in the model + student_import_wizard.md):
        # a tutor with no document number can never be matched on re-import —
        # this test locks in that current behavior so a future fix is a
        # deliberate decision, not an accidental change caught by surprise.
        wizard = self._wizard()
        first, accio1 = wizard._get_or_create_family(
            'Undocumented Tutor', None, '612345678', None, None, {})
        second, accio2 = wizard._get_or_create_family(
            'Undocumented Tutor', None, '612345678', None, None, {})
        self.assertEqual(accio1, 'Creat')
        self.assertEqual(accio2, 'Creat')
        self.assertNotEqual(first, second)

    def test_get_or_create_family_no_name_returns_false(self):
        wizard = self._wizard()
        family, accio = wizard._get_or_create_family('', '11111111A', None, None, None, {})
        self.assertFalse(family)
        self.assertIsNone(accio)

    # --- _process_row / _process_tutor (column-mapping, no real xlsx needed) ----

    def _row_and_col_map(self, values):
        """values: dict of {header: value}. Returns (row_tuple, col_map) covering
        exactly the headers passed in, mimicking what _find_headers would build."""
        headers = list(values.keys())
        col_map = {h: i for i, h in enumerate(headers)}
        row = tuple(values.values())
        return row, col_map

    def test_process_row_creates_student_with_group_and_documents(self):
        level = self.env['ems.level'].create({'acronym': 'TSIW', 'name': 'Test Import Level'})
        study = self.env['ems.study'].create({
            'code': 'TSIW01', 'acronym': 'TSIW', 'name': 'Test Import Study',
            'date': date.today(), 'deprecated': False, 'level_id': level.id,
        })
        group = self.env['ems.group'].create({
            'course': 1, 'acronym': 'A', 'level_id': level.id, 'study_id': study.id,
            'external_id': 'ESFERA-TSIW-A',
        })
        row, col_map = self._row_and_col_map({
            'Grup Classe': 'ESFERA-TSIW-A',
            'Nom': 'Imported',
            'Primer Cognom': 'Student',
            'Segon Cognom': 'Test',
            'Identificador de l\'alumne/a': '9000001',
            'Número de document d\'identitat': '12345678A',
            'Tipus de document d\'identitat': 'DNI',
            'Data naixement': '10/05/2008',
            'Nacionalitat': '',
            'País naixement': '',
            'Telèfon': '612345678',
            'Correu electrònic': 'student.import@example.com',
        })
        wizard = self._wizard()
        stats = {'created': 0, 'updated': 0, 'errors': [], 'log': []}
        wizard._process_row(row, col_map, stats)

        student = self.env['res.partner'].search([('student_id', '=', '9000001')])
        self.assertTrue(student)
        self.assertEqual(student.name, 'Imported Student Test')
        self.assertEqual(student.main_group_id, group)
        self.assertEqual(student.document_id, '12345678A')
        self.assertEqual(student.mobile, '612345678')
        self.assertEqual(student.email, 'student.import@example.com')
        self.assertEqual(student.birth_date, date(2008, 5, 10))
        self.assertEqual(stats['created'], 1)

    def test_process_row_missing_group_adds_note_without_erroring(self):
        row, col_map = self._row_and_col_map({
            'Grup Classe': 'NO-SUCH-GROUP-CODE',
            'Nom': 'Groupless',
            'Primer Cognom': 'Student',
            'Segon Cognom': '',
            'Identificador de l\'alumne/a': '9000002',
        })
        wizard = self._wizard()
        stats = {'created': 0, 'updated': 0, 'errors': [], 'log': []}
        wizard._process_row(row, col_map, stats)

        student = self.env['res.partner'].search([('student_id', '=', '9000002')])
        self.assertTrue(student)
        self.assertFalse(student.main_group_id)
        self.assertIn('NO-SUCH-GROUP-CODE', student.comment)
        self.assertEqual(stats['errors'], [])

    def test_process_row_without_name_is_noop(self):
        row, col_map = self._row_and_col_map({
            'Grup Classe': 'SOME-CODE', 'Nom': '', 'Primer Cognom': '', 'Segon Cognom': '',
        })
        wizard = self._wizard()
        stats = {'created': 0, 'updated': 0, 'errors': [], 'log': []}
        wizard._process_row(row, col_map, stats)
        self.assertEqual(stats['created'], 0)
        self.assertEqual(stats['updated'], 0)

    def test_process_tutor_links_family_with_deduced_relation(self):
        student = self.env['res.partner'].create({'name': 'Tutor Link Student', 'contact_type': 'student'})
        row, col_map = self._row_and_col_map({
            'Tutor 1 - nom': 'Maria',
            'Tutor 1 - 1r cognom ': 'Garcia',
            'Tutor 1 - 2n cognom': 'Lopez',
            'Tutor 1 - doc. identitat': '87654321B',
            'Contacte 1er tutor alumne - Valor': '699887766 - mother@example.com',
            'Contacte 1er tutor alumne - Observacions': 'Mare',
        })
        wizard = self._wizard()
        stats = {'created': 0, 'updated': 0, 'errors': [], 'log': []}
        wizard._process_tutor(row, col_map, 'Tutor 1', student, stats)

        family = self.env['res.partner'].search([('document_id', '=', '87654321B')])
        self.assertTrue(family)
        self.assertEqual(family.name, 'Maria Garcia Lopez')
        self.assertEqual(family.contact_type, 'family')
        self.assertEqual(family.mobile, '699887766')
        self.assertEqual(family.email, 'mother@example.com')

        relation = self.env['res.partner.relation'].search([
            ('left_partner_id', '=', family.id), ('right_partner_id', '=', student.id)])
        self.assertTrue(relation)
        self.assertEqual(relation.type_id, self.env.ref('ems.relation_type_mother'))

    def test_process_tutor_fallback_relation_adds_note_on_student(self):
        student = self.env['res.partner'].create({'name': 'Fallback Note Student', 'contact_type': 'student'})
        row, col_map = self._row_and_col_map({
            'Tutor 2 - nom': 'Jordi',
            'Tutor 2 - 1r cognom': 'Puig',
            'Tutor 2 - doc. identitat': '55555555C',
            'Contacte 2on tutor alumne - Valor': '655555555',
            'Contacte 2on tutor alumne - Observacions': 'Cangur habitual',
        })
        wizard = self._wizard()
        stats = {'created': 0, 'updated': 0, 'errors': [], 'log': []}
        wizard._process_tutor(row, col_map, 'Tutor 2', student, stats)
        self.assertIn('Cangur habitual', student.comment)
        self.assertIn('Tutor per defecte', student.comment)

    def test_process_tutor_without_name_is_noop(self):
        student = self.env['res.partner'].create({'name': 'No Tutor Student', 'contact_type': 'student'})
        row, col_map = self._row_and_col_map({'Tutor 1 - nom': ''})
        wizard = self._wizard()
        stats = {'created': 0, 'updated': 0, 'errors': [], 'log': []}
        wizard._process_tutor(row, col_map, 'Tutor 1', student, stats)
        self.assertEqual(stats['log'], [])

    # --- _build_log_csv / _build_result_html --------------------------------------

    def test_build_log_csv_contains_logged_entries(self):
        student = self.env['res.partner'].create({'name': 'CSV Log Student', 'contact_type': 'student'})
        wizard = self._wizard()
        csv_b64 = wizard._build_log_csv([
            {'tipus': 'Alumne', 'accio': 'Creat', 'partner_id': student.id, 'ts': datetime.now()},
        ])
        content = base64.b64decode(csv_b64).decode('utf-8-sig')
        self.assertIn('CSV Log Student', content)
        self.assertIn('Alumne', content)
        self.assertIn('Creat', content)

    def test_build_result_html_escapes_error_content(self):
        wizard = self._wizard()
        html = wizard._build_result_html({
            'created': 2, 'updated': 1,
            'errors': ['<script>alert(1)</script>'],
        })
        self.assertIn('&lt;script&gt;', html)
        self.assertNotIn('<script>alert(1)</script>', html)
        self.assertIn('2', html)
        self.assertIn('1', html)

    def test_build_result_html_no_errors_omits_error_block(self):
        wizard = self._wizard()
        html = wizard._build_result_html({'created': 0, 'updated': 0, 'errors': []})
        self.assertNotIn('Errors', html)

    # --- action_import end-to-end (real xlsx) --------------------------------------

    def _sheet(self, rows):
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        for row in rows:
            ws.append(row)
        return ws

    def _build_xlsx_b64(self, headers, data_row):
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(headers)
        ws.append(data_row)
        buf = io.BytesIO()
        wb.save(buf)
        return base64.b64encode(buf.getvalue())

    def test_action_import_end_to_end_creates_student(self):
        level = self.env['ems.level'].create({'acronym': 'TSIWE', 'name': 'Test Import E2E Level'})
        study = self.env['ems.study'].create({
            'code': 'TSIWE01', 'acronym': 'TSIWE', 'name': 'Test Import E2E Study',
            'date': date.today(), 'deprecated': False, 'level_id': level.id,
        })
        group = self.env['ems.group'].create({
            'course': 1, 'acronym': 'A', 'level_id': level.id, 'study_id': study.id,
            'external_id': 'ESFERA-E2E-A',
        })
        wizard_model = self.env['ems.student_import_wizard']
        headers = list(wizard_model._REQUIRED_COLUMNS)
        # Cover the trailing-space variant column too, and match all required headers.
        headers += ['Tutor 1 - 1r cognom ', 'Tutor 2 - 1r cognom ']
        values_by_header = {
            'Grup Classe': 'ESFERA-E2E-A',
            'Nom': 'E2E',
            'Primer Cognom': 'Import',
            'Segon Cognom': 'Test',
            'Identificador de l\'alumne/a': '9100001',
            'Número de document d\'identitat': '99999999Z',
            'Tipus de document d\'identitat': 'DNI',
            'Data naixement': '01/09/2009',
            'Telèfon': '912345678',
            'Correu electrònic': 'e2e.student@example.com',
            'Tutor 1 - nom': 'Anna',
            'Tutor 1 - 1r cognom ': 'Serra',
            'Tutor 1 - doc. identitat': '88888888D',
            'Contacte 1er tutor alumne - Valor': '611222333 - anna.serra@example.com',
            'Contacte 1er tutor alumne - Observacions': 'Mare',
        }
        data_row = [values_by_header.get(h, '') for h in headers]
        wizard = wizard_model.create({
            'file': self._build_xlsx_b64(headers, data_row),
            'file_name': 'esfera_e2e.xlsx',
        })
        wizard.action_import()

        student = self.env['res.partner'].search([('student_id', '=', '9100001')])
        self.assertTrue(student)
        self.assertEqual(student.name, 'E2E Import Test')
        self.assertEqual(student.main_group_id, group)

        family = self.env['res.partner'].search([('document_id', '=', '88888888D')])
        self.assertTrue(family)
        relation = self.env['res.partner.relation'].search([
            ('left_partner_id', '=', family.id), ('right_partner_id', '=', student.id)])
        self.assertEqual(relation.type_id, self.env.ref('ems.relation_type_mother'))

        self.assertIn('Students created:', wizard.result_html)
        self.assertTrue(wizard.log_file)

    def test_action_import_raises_on_missing_required_columns(self):
        from odoo.exceptions import UserError
        wizard = self.env['ems.student_import_wizard'].create({
            'file': self._build_xlsx_b64(['Grup Classe', 'Nom'], ['CODE', 'Test']),
            'file_name': 'incomplete.xlsx',
        })
        with self.assertRaises(UserError):
            wizard.action_import()

    def test_action_import_raises_when_header_row_not_found(self):
        from odoo.exceptions import UserError
        wizard = self.env['ems.student_import_wizard'].create({
            'file': self._build_xlsx_b64(['Nom', 'Cognom'], ['Test', 'Student']),
            'file_name': 'no_header.xlsx',
        })
        with self.assertRaises(UserError):
            wizard.action_import()
