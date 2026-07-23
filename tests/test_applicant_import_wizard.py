import base64
import csv
import io
from datetime import date

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


# Subset of the real GEDAC "ASSIGNATS" export header, limited to the columns the
# wizard reads. Order is irrelevant (the wizard maps by name).
HEADERS = [
    'Núm. sol·licitud', 'Nom', 'Primer cognom', 'Segon cognom', 'Telèfon',
    'Correu electrònic', 'Ident. RALC', 'Tipus alumne',
    'Codi ensenyament', 'Nom ensenyament', 'Curs', "Esportista d'alt nivell",
    'Codi centre procedència', 'Nom centre procedència',
    'Codi ensenyament procedència', 'Nom ensenyament procedència', 'Curs procedència',
    'Centre assignat', 'Codi ensenyament assignat', 'Nom ensenyament assignat',
    'Torn assignat', 'Petició atesa',
]


class TestApplicantImportWizard(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.admin_user = cls.env.ref('base.user_admin')
        cls.admin_user.groups_id = [(4, cls.env.ref('ems.group_academic_admin').id)]

        cls.env.company.center_code = '8028047'

        cls.level = cls.env['ems.level'].create({'acronym': 'AIWL', 'name': 'AIW Level'})
        # Unique code whose tail token (ZZ99) is what the GEDAC "Codi ensenyament
        # assignat" (e.g. 'CFPM    ZZ99') resolves against.
        cls.study = cls.env['ems.study'].create({
            'code': 'CFGM_ZZ99', 'acronym': 'ZZT', 'name': 'AIW Test Study',
            'date': date.today(), 'deprecated': False, 'level_id': cls.level.id,
        })
        cls.group = cls.env['ems.group'].create({
            'course': 1, 'acronym': 'A', 'level_id': cls.level.id, 'study_id': cls.study.id,
        })

    # --- helpers ---

    def _xlsx(self, rows):
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(HEADERS)
        for row in rows:
            ws.append([row.get(h) for h in HEADERS])
        buf = io.BytesIO()
        wb.save(buf)
        return base64.b64encode(buf.getvalue())

    def _run(self, rows):
        wizard = self.env['ems.applicant_import_wizard'].create({
            'file': self._xlsx(rows), 'file_name': 'gedac.xlsx',
        })
        wizard.action_import()
        return wizard

    def _csv(self, rows):
        # Mimic the GEDAC csv export: ';' delimiter, cp1252 (Latin-1) encoding.
        buf = io.StringIO()
        writer = csv.writer(buf, delimiter=';')
        writer.writerow(HEADERS)
        for row in rows:
            writer.writerow(['' if row.get(h) is None else row.get(h) for h in HEADERS])
        return base64.b64encode(buf.getvalue().encode('cp1252'))

    def _run_csv(self, rows):
        wizard = self.env['ems.applicant_import_wizard'].create({
            'file': self._csv(rows), 'file_name': 'gedac.csv',
        })
        wizard.action_import()
        return wizard

    def _base_row(self, **kw):
        row = {
            'Nom': 'Laia', 'Primer cognom': 'Puig', 'Segon cognom': 'Roca',
            'Ident. RALC': 1234567890, 'Telèfon': 600111222,
            'Correu electrònic': 'laia@example.com',
            'Centre assignat': 8028047, 'Codi ensenyament assignat': 'CFPM    ZZ99',
            'Nom ensenyament assignat': 'AIW Test Study', 'Torn assignat': 'Matí',
        }
        row.update(kw)
        return row

    def _applicant(self, ralc):
        return self.env['res.partner'].search([('student_id', '=', str(ralc))], limit=1)

    # --- tests ---

    def test_create_applicant(self):
        self._run([self._base_row(**{
            'Codi centre procedència': 8037176, 'Nom centre procedència': 'Institut La Bastida',
            'Codi ensenyament procedència': 7, 'Nom ensenyament procedència': 'ESO',
            'Curs procedència': 4, 'Núm. sol·licitud': 'PRE25-123', 'Petició atesa': 1,
            'Curs': 2, 'Nom ensenyament': 'Comerç', "Esportista d'alt nivell": 'Sí sense valor',
        })])
        applicant = self._applicant(1234567890)
        self.assertTrue(applicant)
        self.assertEqual(applicant.contact_type, 'applicant')
        self.assertEqual(applicant.name, 'Laia Puig Roca')
        self.assertEqual(applicant.firstname, 'Laia')
        self.assertEqual(applicant.lastname, 'Puig Roca')
        self.assertEqual(applicant.study_id, self.study)
        self.assertEqual(applicant.preinscription_shift, 'morning')
        self.assertFalse(applicant.main_group_id)
        # Provenance and preinscription metadata end up in the notes (no dedicated field yet).
        self.assertIn('Institut La Bastida', applicant.comment)
        self.assertIn('8037176', applicant.comment)
        self.assertIn('Comerç', applicant.comment)          # 1st-choice study
        self.assertIn('High-level athlete', applicant.comment)

    def test_multiword_firstname_split(self):
        # "Nom" can be multi-word: it must all land in firstname, and the two
        # surnames in lastname — not re-split on the first space by partner_firstname.
        self._run([self._base_row(**{
            'Ident. RALC': 581, 'Nom': 'Aaron Leonel',
            'Primer cognom': 'Macodicomex', 'Segon cognom': 'M59',
        })])
        p = self._applicant(581)
        self.assertEqual(p.firstname, 'Aaron Leonel')
        self.assertEqual(p.lastname, 'Macodicomex M59')
        self.assertEqual(p.name, 'Aaron Leonel Macodicomex M59')

    def test_csv_import(self):
        # GEDAC csv variant: ';' + cp1252 + codes with a leading zero + accents.
        self._run_csv([self._base_row(**{
            'Ident. RALC': 651, 'Nom': 'Núria Àngels',
            'Centre assignat': '08028047', 'Torn assignat': 'Tarda',
        })])
        p = self._applicant(651)
        self.assertTrue(p)
        self.assertEqual(p.study_id, self.study)          # leading-zero center matched
        self.assertEqual(p.firstname, 'Núria Àngels')     # accents survive cp1252
        self.assertEqual(p.preinscription_shift, 'afternoon')

    def test_skip_other_center(self):
        self._run([self._base_row(**{'Ident. RALC': 555, 'Centre assignat': 9999999})])
        self.assertFalse(self._applicant(555))

    def test_skip_no_assignment(self):
        self._run([self._base_row(**{
            'Ident. RALC': 556, 'Centre assignat': None,
            'Codi ensenyament assignat': None,
        })])
        self.assertFalse(self._applicant(556))

    def test_skip_unknown_study(self):
        wizard = self._run([self._base_row(**{
            'Ident. RALC': 557, 'Codi ensenyament assignat': 'CFPM    XX00',
            'Nom ensenyament assignat': 'Unknown study',
        })])
        self.assertFalse(self._applicant(557))
        log = base64.b64decode(wizard.log_file).decode('utf-8-sig')
        self.assertIn('Study not found', log)

    def test_study_name_fallback(self):
        # Token 'NADA' matches no code; the exact name still resolves the study.
        self._run([self._base_row(**{
            'Ident. RALC': 558, 'Codi ensenyament assignat': 'CFPM    NADA',
            'Nom ensenyament assignat': 'AIW Test Study',
        })])
        self.assertEqual(self._applicant(558).study_id, self.study)

    def test_shift_mapping(self):
        self._run([
            self._base_row(**{'Ident. RALC': 561, 'Torn assignat': 'Tarda'}),
            # "Matí i tarda" (ESO split shift) -> morning: ESO is morning-only here.
            self._base_row(**{'Ident. RALC': 562, 'Torn assignat': 'Matí i tarda'}),
        ])
        self.assertEqual(self._applicant(561).preinscription_shift, 'afternoon')
        self.assertEqual(self._applicant(562).preinscription_shift, 'morning')

    def test_entry_course_mapping(self):
        self._run([
            self._base_row(**{'Ident. RALC': 601, 'Curs': 1}),
            self._base_row(**{'Ident. RALC': 602, 'Curs': 2}),
            self._base_row(**{'Ident. RALC': 603, 'Curs': None}),
        ])
        self.assertEqual(self._applicant(601).preinscription_course, '1')
        self.assertEqual(self._applicant(602).preinscription_course, '2')
        self.assertFalse(self._applicant(603).preinscription_course)

    def test_special_needs_mapping(self):
        self._run([
            self._base_row(**{'Ident. RALC': 591, 'Tipus alumne': 'NEE-A'}),
            self._base_row(**{'Ident. RALC': 592, 'Tipus alumne': 'NEE-B'}),
            self._base_row(**{'Ident. RALC': 593, 'Tipus alumne': 'Ordinari'}),
        ])
        self.assertEqual(self._applicant(591).special_needs, 'nee_a')
        self.assertEqual(self._applicant(592).special_needs, 'nee_b')
        self.assertFalse(self._applicant(593).special_needs)
        # A later "Ordinari" row must not clear an already-set NEE mark.
        self._run([self._base_row(**{'Ident. RALC': 591, 'Tipus alumne': 'Ordinari'})])
        self.assertEqual(self._applicant(591).special_needs, 'nee_a')

    def test_reimport_is_idempotent(self):
        self._run([self._base_row()])
        wizard = self._run([self._base_row(**{'Correu electrònic': 'laia2@example.com'})])
        applicants = self.env['res.partner'].search([('student_id', '=', '1234567890')])
        self.assertEqual(len(applicants), 1)
        self.assertEqual(applicants.email, 'laia2@example.com')
        self.assertIn('Applicants updated', wizard.result_html)

    def test_active_student_keeps_its_identity_but_records_the_destination(self):
        student = self.env['res.partner'].create({
            'name': 'Old Name', 'contact_type': 'student', 'student_id': '7000001',
            'main_group_id': self.group.id, 'email': 'old@example.com',
        })
        wizard = self._run([self._base_row(**{
            'Ident. RALC': 7000001, 'Nom': 'New', 'Primer cognom': 'Name',
            'Segon cognom': None, 'Correu electrònic': 'new@example.com',
            'Torn assignat': 'Tarda', 'Curs': 1,
        })])
        student.invalidate_recordset()
        # Own data untouched: GEDAC never overwrites the active student's identity,
        # group or contact details.
        self.assertEqual(student.contact_type, 'student')
        self.assertEqual(student.main_group_id, self.group)
        self.assertEqual(student.name, 'Old Name')
        self.assertEqual(student.email, 'old@example.com')
        # ...but the granted destination is captured now: it used to die with the
        # wizard, leaving the enrollment proposal blind to where the student is going.
        self.assertEqual(student.preinscription_study_id, self.study)
        self.assertEqual(student.preinscription_shift, 'afternoon')
        self.assertEqual(student.preinscription_course, '1')
        # Reported apart and offered as its own CSV, with the granted study captured.
        self.assertIn('active students', wizard.result_html.lower())
        self.assertTrue(wizard.students_file)
        csv_text = base64.b64decode(wizard.students_file).decode('utf-8-sig')
        self.assertIn('7000001', csv_text)
        self.assertIn(self.study.display_name, csv_text)

    def test_alumni_becomes_applicant(self):
        alumni = self.env['res.partner'].create({
            'name': 'Return Student', 'contact_type': 'alumni', 'student_id': '7000002',
            'has_graduated': True,
        })
        self._run([self._base_row(**{'Ident. RALC': 7000002})])
        alumni.invalidate_recordset()
        self.assertEqual(alumni.contact_type, 'applicant')
        self.assertEqual(alumni.study_id, self.study)

    def test_archived_withdrawal_becomes_applicant_and_is_reactivated(self):
        # A withdrawal is archived (active=False) as part of the exit, mirroring
        # hr.employee. A re-import must find and reactivate that same record
        # instead of silently creating a duplicate partner (orphaning the
        # original's year_record_ids/documents/benefits).
        withdrawal = self.env['res.partner'].create({
            'name': 'Return Student', 'contact_type': 'withdrawal', 'student_id': '7000003',
        })
        withdrawal.write({'active': False})
        self._run([self._base_row(**{'Ident. RALC': 7000003})])
        withdrawal.invalidate_recordset()
        self.assertEqual(withdrawal.contact_type, 'applicant')
        self.assertTrue(withdrawal.active)
        self.assertEqual(withdrawal.study_id, self.study)
        # No duplicate created.
        matches = self.env['res.partner'].with_context(active_test=False).search(
            [('student_id', '=', '7000003')])
        self.assertEqual(len(matches), 1)

    def test_phone_normalization(self):
        # Mobile with country code -> stripped to 9-digit national, stored as mobile.
        self._run([self._base_row(**{'Ident. RALC': 571, 'Telèfon': 34631078723})])
        p = self._applicant(571)
        self.assertEqual(p.mobile, '631078723')
        self.assertFalse(p.phone)

        # Plain 9-digit mobile -> unchanged, stored as mobile.
        self._run([self._base_row(**{'Ident. RALC': 572, 'Telèfon': 631078723})])
        self.assertEqual(self._applicant(572).mobile, '631078723')

        # Landline with country code -> stripped, stored as phone (not mobile).
        self._run([self._base_row(**{'Ident. RALC': 573, 'Telèfon': 34931234567})])
        p = self._applicant(573)
        self.assertEqual(p.phone, '931234567')
        self.assertFalse(p.mobile)

        # Unrecognized number (8 digits) -> kept verbatim under phone, no data loss.
        self._run([self._base_row(**{'Ident. RALC': 574, 'Telèfon': 63107872})])
        p = self._applicant(574)
        self.assertEqual(p.phone, '63107872')
        self.assertFalse(p.mobile)

    def test_center_code_leading_zero(self):
        # The official code carries a leading zero (08028047) that the numeric Excel
        # column drops (8028047). The comparison must ignore it on both sides.
        self.env.company.center_code = '08028047'
        self._run([self._base_row(**{'Ident. RALC': 563, 'Centre assignat': 8028047})])
        self.assertTrue(self._applicant(563))

    def test_missing_center_code_raises(self):
        self.env.company.center_code = False
        with self.assertRaises(UserError):
            self._run([self._base_row()])
