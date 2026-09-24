import base64
import io
from datetime import date, datetime

from odoo import fields as odoo_fields
from odoo.tests.common import TransactionCase

from .common import create_level_study_group, next_student_id


class TestStudentImportWizard(TransactionCase):
    """Focused coverage for _get_or_create_student: the dedup/reactivation
    logic touched by the archive-on-withdrawal change, not a full xlsx
    column-mapping suite (see action_import / _process_row for that)."""

    def _wizard(self, overwrite=False):
        return self.env['ems.student_import_wizard'].create({
            'file': base64.b64encode(b'placeholder'), 'file_name': 'esfera.xlsx',
            'overwrite': overwrite,
        })

    def _stats(self):
        return {'created': 0, 'updated': 0, 'errors': [], 'warnings': [], 'log': []}

    def test_creates_new_student(self):
        wizard = self._wizard()
        stats = self._stats()
        student = wizard._get_or_create_student('8000001', {
            'name': 'Brand New', 'contact_type': 'student',
            'student_id': '8000001', 'active': True,
        }, stats)
        self.assertEqual(student.name, 'Brand New')
        self.assertTrue(student.active)
        self.assertEqual(stats['created'], 1)

    def test_updates_existing_student_when_overwriting(self):
        existing = self.env['res.partner'].create({
            'name': 'Old Name', 'contact_type': 'student', 'student_id': '8000002'})
        wizard = self._wizard(overwrite=True)
        stats = self._stats()
        student = wizard._get_or_create_student('8000002', {
            'name': 'New Name', 'contact_type': 'student',
            'student_id': '8000002', 'active': True,
        }, stats)
        self.assertEqual(student, existing)
        self.assertEqual(student.name, 'New Name')
        self.assertEqual(stats['updated'], 1)

    def test_keeps_ems_value_when_not_overwriting(self):
        # Default mode: EMS's own data wins, so a field that already holds something
        # is left exactly as it was, even though the file carries a different value.
        existing = self.env['res.partner'].create({
            'name': 'Old Name', 'contact_type': 'student', 'student_id': '8000012',
            'email': 'kept@example.com'})
        wizard = self._wizard()
        stats = self._stats()
        student = wizard._get_or_create_student('8000012', {
            'name': 'New Name', 'contact_type': 'student', 'student_id': '8000012',
            'email': 'from.file@example.com', 'active': True,
        }, stats)
        self.assertEqual(student.name, 'Old Name')
        self.assertEqual(student.email, 'kept@example.com')
        self.assertEqual(stats['updated'], 1)

    def test_fills_only_empty_fields_when_not_overwriting(self):
        # The other half of the default mode: a field EMS has left empty still gets
        # filled in from the file.
        existing = self.env['res.partner'].create({
            'name': 'Has No Email', 'contact_type': 'student', 'student_id': '8000013'})
        wizard = self._wizard()
        stats = self._stats()
        wizard._get_or_create_student('8000013', {
            'name': 'Other Name', 'contact_type': 'student', 'student_id': '8000013',
            'email': 'filled.in@example.com', 'active': True,
        }, stats)
        self.assertEqual(existing.email, 'filled.in@example.com')
        self.assertEqual(existing.name, 'Has No Email')

    def test_empty_file_value_never_blanks_existing_data(self):
        # The rule that holds in BOTH modes: a column that came empty in the file must
        # never erase what EMS already holds. Checked under overwrite=True, the mode
        # where the file is otherwise allowed to win.
        existing = self.env['res.partner'].create({
            'name': 'Keep Me', 'contact_type': 'student', 'student_id': '8000014',
            'email': 'keep@example.com', 'phone': '900111222'})
        wizard = self._wizard(overwrite=True)
        stats = self._stats()
        wizard._get_or_create_student('8000014', {
            'name': 'Keep Me', 'contact_type': 'student', 'student_id': '8000014',
            'email': None, 'phone': '', 'mobile': False, 'active': True,
        }, stats)
        self.assertEqual(existing.email, 'keep@example.com')
        self.assertEqual(existing.phone, '900111222')

    def test_skips_new_student_without_name(self):
        wizard = self._wizard()
        stats = self._stats()
        student = wizard._get_or_create_student('8000015', {
            'name': '', 'contact_type': 'student', 'student_id': '8000015', 'active': True,
        }, stats)
        self.assertFalse(student)
        self.assertEqual(stats['created'], 0)
        self.assertTrue(stats['warnings'])

    def test_reactivates_archived_withdrawal_instead_of_duplicating(self):
        # A withdrawal is archived (active=False) as part of the exit, mirroring
        # hr.employee. Re-importing the same RALC must find and reactivate that
        # record, not silently create a duplicate partner.
        withdrawn = self.env['res.partner'].create({
            'name': 'Old Name', 'contact_type': 'withdrawal', 'student_id': '8000003'})
        withdrawn.write({'active': False})
        wizard = self._wizard()
        stats = self._stats()
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

    def test_find_headers_locates_student_id_row(self):
        wizard = self._wizard()
        ws = self._sheet([
            ['Some export title'],
            [],
            ["Identificador de l'alumne/a", 'Nom', 'Primer Cognom'],
            ['9000100', 'Test', 'Student'],
        ])
        idx, col_map = wizard._find_headers(ws)
        self.assertEqual(idx, 3)
        self.assertEqual(col_map["Identificador de l'alumne/a"], 0)
        self.assertEqual(col_map['Nom'], 1)

    def test_find_headers_ignores_a_grup_classe_only_header(self):
        # 'Grup Classe' used to be the marker; it is no longer enough on its own,
        # since the student identifier is the only column actually required.
        wizard = self._wizard()
        ws = self._sheet([['Grup Classe', 'Nom'], ['TSIW A', 'Test']])
        idx, col_map = wizard._find_headers(ws)
        self.assertIsNone(idx)
        self.assertEqual(col_map, {})

    def test_find_headers_returns_none_when_absent(self):
        wizard = self._wizard()
        ws = self._sheet([['Nom', 'Cognom'], ['Test', 'Student']])
        idx, col_map = wizard._find_headers(ws)
        self.assertIsNone(idx)
        self.assertEqual(col_map, {})

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

    def test_get_or_create_family_without_document_matches_by_mobile(self):
        # Issue #507: a tutor with no document number is recognised by mobile number, when a
        # single family contact holds it and the first name matches (res.partner._ems_find_family).
        wizard = self._wizard()
        first, accio1 = wizard._get_or_create_family(
            'Undocumented Tutor', None, None, '+34 711 000 101', None, {}, firstname='Undocumented')
        second, accio2 = wizard._get_or_create_family(
            'Undocumented Tutor Surname', None, None, '711000101', None, {}, firstname='Undocumented')
        self.assertEqual(accio1, 'Creat')
        self.assertEqual(accio2, 'Actualitzat')
        self.assertEqual(first, second)

    def test_get_or_create_family_shared_mobile_other_name_creates_new_with_warning(self):
        # Parents sharing one phone: the same mobile under another first name is never merged.
        student = self.env['res.partner'].create({
            'name': 'Shared Phone Student', 'contact_type': 'student', 'student_id': next_student_id()})
        wizard = self._wizard()
        stats = self._stats()
        mother, _accio = wizard._get_or_create_family(
            'Maria Shared', None, None, '711000102', None, {}, firstname='Maria')
        father, accio = wizard._get_or_create_family(
            'Joan Shared', None, None, '711000102', None, {}, firstname='Joan', stats=stats, student=student)
        self.assertEqual(accio, 'Creat')
        self.assertNotEqual(mother, father)
        self.assertEqual(len(stats['warnings']), 1)
        self.assertIn('Maria Shared', stats['warnings'][0])

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
        level, study, group = create_level_study_group(self, 'TSIW', level={'name': 'Test Import Level'}, study={
            'code': 'TSIW01', 'name': 'Test Import Study',
        }, group={'external_id': 'ESFERA-TSIW-A'})
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
        stats = self._stats()
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

    def test_process_row_tis_document_type_maps_to_medical_id(self):
        # 'TIS' (Targeta d'Identificació Sanitària) is a real document type Esfera exports
        # alongside DNI/NIE/PASS - confirmed handled (docs.get('TIS') -> medical_id), just
        # never had an explicit test locking it in. Also covers the multi-document case: a
        # student can have both a DNI and a TIS in the same row (' - '-joined).
        row, col_map = self._row_and_col_map({
            'Grup Classe': 'SOME-CODE', 'Nom': 'Tis', 'Primer Cognom': 'Student', 'Segon Cognom': '',
            'Identificador de l\'alumne/a': '9000006',
            'Número de document d\'identitat': '12345678A - AB1234567',
            'Tipus de document d\'identitat': 'DNI - TIS',
        })
        wizard = self._wizard()
        stats = self._stats()
        wizard._process_row(row, col_map, stats)

        student = self.env['res.partner'].search([('student_id', '=', '9000006')])
        self.assertTrue(student)
        self.assertEqual(student.document_id, '12345678A')
        self.assertEqual(student.medical_id, 'AB1234567')

    def test_process_row_missing_group_adds_note_and_warning(self):
        # Intentional behavior (import anyway, note for later manual placement) - but
        # now also surfaced in stats['warnings'], visible in the result summary a
        # secretary actually reviews, not just buried in the student's comment field.
        # See plans/student_import_wizard_data_quality_gaps.md (now resolved).
        row, col_map = self._row_and_col_map({
            'Grup Classe': 'NO-SUCH-GROUP-CODE',
            'Nom': 'Groupless',
            'Primer Cognom': 'Student',
            'Segon Cognom': '',
            'Identificador de l\'alumne/a': '9000002',
        })
        wizard = self._wizard()
        stats = self._stats()
        wizard._process_row(row, col_map, stats)

        student = self.env['res.partner'].search([('student_id', '=', '9000002')])
        self.assertTrue(student)
        self.assertFalse(student.main_group_id)
        self.assertIn('NO-SUCH-GROUP-CODE', student.comment)
        self.assertEqual(stats['errors'], [])
        self.assertEqual(len(stats['warnings']), 1)
        self.assertIn('Groupless Student', stats['warnings'][0])
        self.assertIn('NO-SUCH-GROUP-CODE', stats['warnings'][0])

    def test_process_row_matching_group_adds_no_warning(self):
        level, study, group = create_level_study_group(self, 'TSIWG', level={'name': 'Test Import Warn Level'}, study={
            'code': 'TSIWG01', 'name': 'Test Import Warn Study',
        }, group={'external_id': 'ESFERA-TSIWG-A'})
        row, col_map = self._row_and_col_map({
            'Grup Classe': 'ESFERA-TSIWG-A',
            'Nom': 'Grouped', 'Primer Cognom': 'Student', 'Segon Cognom': '',
            'Identificador de l\'alumne/a': '9000005',
        })
        wizard = self._wizard()
        stats = self._stats()
        wizard._process_row(row, col_map, stats)
        self.assertEqual(stats['warnings'], [])

    def test_process_row_without_name_is_noop(self):
        row, col_map = self._row_and_col_map({
            'Grup Classe': 'SOME-CODE', 'Nom': '', 'Primer Cognom': '', 'Segon Cognom': '',
            "Identificador de l'alumne/a": '9000020',
        })
        wizard = self._wizard()
        stats = self._stats()
        wizard._process_row(row, col_map, stats)
        self.assertEqual(stats['created'], 0)
        self.assertEqual(stats['updated'], 0)
        self.assertTrue(stats['warnings'])

    def test_process_row_without_student_id_is_skipped(self):
        # The identifier is the only mandatory column: without it the row cannot be
        # matched to a student, so it is skipped and reported instead of imported.
        row, col_map = self._row_and_col_map({
            'Grup Classe': 'SOME-CODE', 'Nom': 'No', 'Primer Cognom': 'Identifier',
        })
        wizard = self._wizard()
        stats = self._stats()
        wizard._process_row(row, col_map, stats)
        self.assertEqual(stats['created'], 0)
        self.assertEqual(stats['updated'], 0)
        self.assertTrue(stats['warnings'])

    def test_process_row_without_group_still_imports(self):
        # 'Grup Classe' is no longer mandatory, and an empty one must not silently
        # discard the row the way it used to.
        row, col_map = self._row_and_col_map({
            'Grup Classe': '', 'Nom': 'Groupless', 'Primer Cognom': 'ByDesign',
            "Identificador de l'alumne/a": '9000021',
        })
        wizard = self._wizard()
        stats = self._stats()
        wizard._process_row(row, col_map, stats)
        student = self.env['res.partner'].search([('student_id', '=', '9000021')])
        self.assertTrue(student)
        self.assertEqual(stats['created'], 1)
        # No group code was exported, so there is nothing to warn about either.
        self.assertEqual(stats['warnings'], [])

    def test_process_tutor_links_family_with_deduced_relation(self):
        student = self.env['res.partner'].create({'name': 'Tutor Link Student', 'contact_type': 'student', 'student_id': next_student_id()})
        row, col_map = self._row_and_col_map({
            'Tutor 1 - nom': 'Maria',
            'Tutor 1 - 1r cognom ': 'Garcia',
            'Tutor 1 - 2n cognom': 'Lopez',
            'Tutor 1 - doc. identitat': '87654321B',
            'Contacte 1er tutor alumne - Valor': '699887766 - mother@example.com',
            'Contacte 1er tutor alumne - Observacions': 'Mare',
        })
        wizard = self._wizard()
        stats = self._stats()
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
        student = self.env['res.partner'].create({'name': 'Fallback Note Student', 'contact_type': 'student', 'student_id': next_student_id()})
        row, col_map = self._row_and_col_map({
            'Tutor 2 - nom': 'Jordi',
            'Tutor 2 - 1r cognom': 'Puig',
            'Tutor 2 - doc. identitat': '55555555C',
            'Contacte 2on tutor alumne - Valor': '655555555',
            'Contacte 2on tutor alumne - Observacions': 'Cangur habitual',
        })
        wizard = self._wizard()
        stats = self._stats()
        wizard._process_tutor(row, col_map, 'Tutor 2', student, stats)
        self.assertIn('Cangur habitual', student.comment)
        self.assertIn('Tutor per defecte', student.comment)

    def test_process_tutor_without_name_is_noop(self):
        student = self.env['res.partner'].create({'name': 'No Tutor Student', 'contact_type': 'student', 'student_id': next_student_id()})
        row, col_map = self._row_and_col_map({'Tutor 1 - nom': ''})
        wizard = self._wizard()
        stats = self._stats()
        wizard._process_tutor(row, col_map, 'Tutor 1', student, stats)
        self.assertEqual(stats['log'], [])

    def test_process_tutor_without_document_adds_warning(self):
        # A tutor with neither a document number nor a phone cannot be recognised
        # (res.partner._ems_find_family): surfaced in stats['warnings'] so a possible
        # duplicate is reviewed by hand.
        student = self.env['res.partner'].create({'name': 'Undocumented Tutor Student', 'contact_type': 'student', 'student_id': next_student_id()})
        row, col_map = self._row_and_col_map({
            'Tutor 1 - nom': 'Sense', 'Tutor 1 - 1r cognom ': 'Document',
        })
        wizard = self._wizard()
        stats = self._stats()
        wizard._process_tutor(row, col_map, 'Tutor 1', student, stats)
        self.assertEqual(len(stats['warnings']), 1)
        self.assertIn('Sense Document', stats['warnings'][0])
        self.assertIn('Undocumented Tutor Student', stats['warnings'][0])

    def test_process_tutor_with_document_adds_no_warning(self):
        student = self.env['res.partner'].create({'name': 'Documented Tutor Student', 'contact_type': 'student', 'student_id': next_student_id()})
        row, col_map = self._row_and_col_map({
            'Tutor 1 - nom': 'Amb', 'Tutor 1 - 1r cognom ': 'Document',
            'Tutor 1 - doc. identitat': '99999999Z',
        })
        wizard = self._wizard()
        stats = self._stats()
        wizard._process_tutor(row, col_map, 'Tutor 1', student, stats)
        self.assertEqual(stats['warnings'], [])

    # --- _build_log_csv / _build_result_html --------------------------------------

    def test_build_log_csv_contains_logged_entries(self):
        student = self.env['res.partner'].create({'name': 'CSV Log Student', 'contact_type': 'student', 'student_id': next_student_id()})
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

    def test_build_result_html_escapes_warning_content(self):
        wizard = self._wizard()
        html = wizard._build_result_html({
            'created': 1, 'updated': 0, 'errors': [],
            'warnings': ['<script>alert(1)</script>'],
        })
        self.assertIn('&lt;script&gt;', html)
        self.assertNotIn('<script>alert(1)</script>', html)

    def test_build_result_html_no_warnings_omits_warning_block(self):
        wizard = self._wizard()
        html = wizard._build_result_html({'created': 0, 'updated': 0, 'errors': []})
        self.assertNotIn('Warnings', html)

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
        level, study, group = create_level_study_group(self, 'TSIWE', level={'name': 'Test Import E2E Level'}, study={
            'code': 'TSIWE01', 'name': 'Test Import E2E Study',
        }, group={'external_id': 'ESFERA-E2E-A'})
        wizard_model = self.env['ems.student_import_wizard']
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
        # Only the columns this row actually fills in: the file no longer has to carry
        # a fixed set of headers, so the test builds them from the values themselves.
        headers = list(values_by_header)
        data_row = [values_by_header[h] for h in headers]
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

    def test_action_import_invalid_email_fails_only_that_row(self):
        # Regression (issue #467): a malformed email (e.g. a phone number ending up in the
        # wrong column) must not silently import - res.partner's own _check_email_format
        # constraint now rejects it - but it also must not abort the rest of the file: the
        # existing per-row try/except in action_import() already isolates one row's failure.
        import openpyxl
        headers = ["Identificador de l'alumne/a", 'Nom', 'Correu electrònic']
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(headers)
        ws.append(['9100010', 'Good Email', 'good.email@example.com'])
        ws.append(['9100011', 'Bad Email', '612345678'])
        buf = io.BytesIO()
        wb.save(buf)

        wizard = self.env['ems.student_import_wizard'].create({
            'file': base64.b64encode(buf.getvalue()), 'file_name': 'mixed_emails.xlsx',
        })
        wizard.action_import()

        good_student = self.env['res.partner'].search([('student_id', '=', '9100010')])
        self.assertTrue(good_student)
        self.assertEqual(good_student.email, 'good.email@example.com')

        bad_student = self.env['res.partner'].search([('student_id', '=', '9100011')])
        self.assertFalse(bad_student)
        self.assertIn('Errors (1):', wizard.result_html)
        self.assertIn('is not a valid email address', wizard.result_html)

    def test_action_import_raises_when_student_id_column_is_absent(self):
        from odoo.exceptions import UserError
        wizard = self.env['ems.student_import_wizard'].create({
            'file': self._build_xlsx_b64(['Grup Classe', 'Nom'], ['CODE', 'Test']),
            'file_name': 'incomplete.xlsx',
        })
        with self.assertRaises(UserError):
            wizard.action_import()

    def test_action_import_accepts_a_file_with_only_the_student_id(self):
        # The identifier alone is a valid file: every other column is optional now.
        wizard = self.env['ems.student_import_wizard'].create({
            'file': self._build_xlsx_b64(
                ["Identificador de l'alumne/a", 'Nom'], ['9000030', 'Minimal File']),
            'file_name': 'minimal.xlsx',
        })
        wizard.action_import()
        self.assertTrue(self.env['res.partner'].search([('student_id', '=', '9000030')]))

    def test_action_import_tolerates_full_real_column_set(self):
        # The real Esfera/SAGA export has 86 columns, far more than the handful this
        # wizard actually reads (confirmed against a real, anonymized export - see
        # plans/student_import_wizard_esfera_gaps.md). Never verified before that the ~50
        # extra columns it doesn't use (address sub-fields, tutor legal/notification flags,
        # a second "Contacte propis alumne" block, etc.) don't break parsing.
        FULL_REAL_COLUMNS = [
            "Grup Classe", "Número de document d'identitat", "Tipus de document d'identitat",
            'Data naixement', 'Nacionalitat', 'País naixement', 'Província naixement',
            'Municipi naixement', 'Alumne tutelat legalment', 'Tipus de via',
            'Alumne emancipat legalment', "Identificador de l'alumne/a", 'Telèfon',
            'Localitat de residència', 'Municipi de residència', 'Província de residència',
            'País de residència', 'Codi postal', 'Correu electrònic', 'Número',
            'Alumne amb custòdia compartida en dos domicilis', 'Bloc', 'Escala', 'Planta',
            'Porta', "Resta de dades de l'adreça", 'Observacions',
            'Contacte alumne - Correu electrònic', 'Nom', 'Primer Cognom', 'Segon Cognom',
            'Nom via', 'Tutor 1 - nom', 'Tutor 2 - nom', 'Tutor 1 - doc. identitat',
            'Tutor 1 - nom via', 'Tutor 1 - localitat', 'Tutor 1 - municipi',
            'Tutor 1 - provincia', 'Tutor 1 - país', 'Tutor 1 - CP', 'Tutor 2 - doc. identitat',
            'Tutor 2 - nom via', 'Tutor 2 - localitat', 'Tutor 2 - municipi',
            'Tutor 2 - provincia', 'Tutor 2 - país', 'Tutor 2 - CP', 'Tutor 1 - 1r cognom',
            'Tutor 1 - 2n cognom', 'Tutor 1 - tipus via', 'Tutor 1 - número', 'Tutor 1 - bloc',
            'Tutor 1 - escala', 'Tutor 1 - planta', 'Tutor 1 - porta',
            "Tutor 1 - resta de dades de l'adreça", 'Tutor 1 - destinatari correspondència',
            'Tutor 2 - 1r cognom', 'Tutor 2 - 2n cognom', 'Tutor 2 - tipus via',
            'Tutor 2 - número', 'Tutor 2 - bloc', 'Tutor 2 - escala', 'Tutor 2 - planta',
            'Tutor 2 - porta', "Tutor 2 - resta de dades de l'adreça",
            'Tutor 2 - tipus doc. Identitat', 'Tutors comparteixen domicili',
            'Tutor 1 - tipus doc. Identitat', 'Tutor 1 - persona jurídica',
            'Tutor 1 - contactes: rebre notificacions',
            'Tutor 2 - contactes: rebre notificacions', 'Contacte alumne - Telèfon',
            'Contacte altres alumne - Tipus', 'Contacte altres alumne - Valor',
            'Contacte altres alumne - Observacions', 'Contacte 1er tutor alumne - Tipus',
            'Contacte 1er tutor alumne - Valor', 'Contacte 1er tutor alumne - Observacions',
            'Contacte 2on tutor alumne - Tipus', 'Contacte 2on tutor alumne - Valor',
            'Contacte 2on tutor alumne - Observacions', 'Contacte propis alumne - Tipus',
            'Contacte propis alumne - Valor', 'Contacte propis alumne - Observacions',
        ]
        level, study, group = create_level_study_group(self, 'TSIWF', level={'name': 'Test Import Full Level'}, study={
            'code': 'TSIWF01', 'name': 'Test Import Full Study',
        }, group={'external_id': 'ESFERA-FULL-A'})
        values_by_header = {
            'Grup Classe': 'ESFERA-FULL-A',
            'Nom': 'Full',
            'Primer Cognom': 'Column',
            'Segon Cognom': 'Set',
            "Identificador de l'alumne/a": '9300001',
            "Número de document d'identitat": '11111111X',
            "Tipus de document d'identitat": 'DNI',
            'Data naixement': '01/01/2010',
            'Telèfon': '600000001',
            'Correu electrònic': 'full.columns@example.com',
        }
        data_row = [values_by_header.get(h, '') for h in FULL_REAL_COLUMNS]
        wizard = self.env['ems.student_import_wizard'].create({
            'file': self._build_xlsx_b64(FULL_REAL_COLUMNS, data_row),
            'file_name': 'esfera_full.xlsx',
        })
        wizard.action_import()

        student = self.env['res.partner'].search([('student_id', '=', '9300001')])
        self.assertTrue(student)
        self.assertEqual(student.main_group_id, group)
        self.assertIn('Students created:', wizard.result_html)

    def test_action_import_raises_when_header_row_not_found(self):
        from odoo.exceptions import UserError
        wizard = self.env['ems.student_import_wizard'].create({
            'file': self._build_xlsx_b64(['Nom', 'Cognom'], ['Test', 'Student']),
            'file_name': 'no_header.xlsx',
        })
        with self.assertRaises(UserError):
            wizard.action_import()


    # --- every sheet is imported, not just the active one -------------------------

    def _build_multi_sheet_xlsx_b64(self, sheets):
        """Build a workbook from a list of (title, rows) pairs."""
        import openpyxl
        wb = openpyxl.Workbook()
        wb.remove(wb.active)
        for title, rows in sheets:
            ws = wb.create_sheet(title=title)
            for row in rows:
                ws.append(row)
        buf = io.BytesIO()
        wb.save(buf)
        return base64.b64encode(buf.getvalue())

    def test_action_import_reads_every_sheet(self):
        # A real Esfera export splits its students across several sheets; only the
        # active one used to be read, silently dropping all the others.
        headers = ["Identificador de l'alumne/a", 'Nom', 'Primer Cognom']
        wizard = self.env['ems.student_import_wizard'].create({
            'file': self._build_multi_sheet_xlsx_b64([
                ('First', [headers, ['9000050', 'Sheet', 'One']]),
                ('Second', [headers, ['9000051', 'Sheet', 'Two']]),
            ]),
            'file_name': 'two_sheets.xlsx',
        })
        wizard.action_import()
        self.assertTrue(self.env['res.partner'].search([('student_id', '=', '9000050')]))
        self.assertTrue(self.env['res.partner'].search([('student_id', '=', '9000051')]))

    def test_action_import_skips_sheets_without_a_header(self):
        # An auxiliary or empty tab must be ignored, not abort the file.
        headers = ["Identificador de l'alumne/a", 'Nom']
        wizard = self.env['ems.student_import_wizard'].create({
            'file': self._build_multi_sheet_xlsx_b64([
                ('Notes', [['just some text'], []]),
                ('Data', [headers, ['9000052', 'Valid Row']]),
            ]),
            'file_name': 'mixed_sheets.xlsx',
        })
        wizard.action_import()
        self.assertTrue(self.env['res.partner'].search([('student_id', '=', '9000052')]))

    # --- notes are stacked, never replaced ----------------------------------------

    def test_import_notes_are_stacked_on_top_never_replaced(self):
        student = self.env['res.partner'].create({
            'name': 'Noted Student', 'contact_type': 'student', 'student_id': '9000060',
            'comment': '<p>Hand-written note</p>'})
        wizard = self._wizard(overwrite=True)
        wizard._prepend_import_notes(student, 'Observacions: imported note')

        self.assertIn('Hand-written note', student.comment)
        self.assertIn('Observacions: imported note', student.comment)
        # Odoo's HTML sanitiser rewrites the void tag, so match either form.
        self.assertIn('<hr', student.comment)
        # The newest block comes first, so the latest import reads at the top.
        self.assertLess(
            student.comment.index('Observacions'), student.comment.index('Hand-written'))
        stamp = odoo_fields.Datetime.context_timestamp(
            student, odoo_fields.Datetime.now()).strftime('%d/%m/%Y')
        self.assertIn(stamp, student.comment)

    def test_import_notes_on_a_record_without_previous_ones(self):
        student = self.env['res.partner'].create({
            'name': 'Fresh Student', 'contact_type': 'student', 'student_id': '9000061'})
        wizard = self._wizard()
        wizard._prepend_import_notes(student, 'Observacions: first note')
        self.assertIn('Observacions: first note', student.comment)

    def test_import_without_notes_leaves_the_field_untouched(self):
        student = self.env['res.partner'].create({
            'name': 'Untouched Student', 'contact_type': 'student', 'student_id': '9000062',
            'comment': '<p>Only mine</p>'})
        wizard = self._wizard(overwrite=True)
        wizard._prepend_import_notes(student, False)
        self.assertEqual(student.comment, '<p>Only mine</p>')

    # --- family contacts follow the same write policy as students -----------------

    def test_family_keeps_ems_data_when_not_overwriting(self):
        family = self.env['res.partner'].create({
            'name': 'Existing Family', 'contact_type': 'family',
            'document_id': '77777777X', 'email': 'family.kept@example.com'})
        wizard = self._wizard()
        result, accio = wizard._get_or_create_family(
            'New Name', '77777777X', None, None, 'from.file@example.com', {'city': 'Barcelona'})
        self.assertEqual(result, family)
        self.assertEqual(accio, 'Actualitzat')
        self.assertEqual(family.email, 'family.kept@example.com')
        self.assertEqual(family.name, 'Existing Family')
        # ...while a field EMS had left empty is still filled in.
        self.assertEqual(family.city, 'Barcelona')

    def test_family_overwrites_when_flagged(self):
        family = self.env['res.partner'].create({
            'name': 'Old Family Name', 'contact_type': 'family',
            'document_id': '77777778Y', 'email': 'old@example.com'})
        wizard = self._wizard(overwrite=True)
        wizard._get_or_create_family(
            'New Family Name', '77777778Y', None, None, 'new@example.com', {})
        self.assertEqual(family.email, 'new@example.com')
        self.assertEqual(family.name, 'New Family Name')

    def test_family_empty_value_never_blanks_existing_data(self):
        family = self.env['res.partner'].create({
            'name': 'Kept Family', 'contact_type': 'family',
            'document_id': '77777779Z', 'email': 'kept@example.com', 'city': 'Girona'})
        wizard = self._wizard(overwrite=True)
        wizard._get_or_create_family(
            'Kept Family', '77777779Z', None, None, None, {'city': '', 'street': False})
        self.assertEqual(family.email, 'kept@example.com')
        self.assertEqual(family.city, 'Girona')
