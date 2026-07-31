import base64
import io
from datetime import date

from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase


class TestGradeImportWizard(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.admin_user = cls.env.ref('base.user_admin')
        cls.admin_user.groups_id = [(4, cls.env.ref('ems.group_academic_admin').id)]

        cls.teacher_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'GI Teacher',
            'login': 'gi_teacher',
            'groups_id': [(4, cls.env.ref('base.group_user').id), (4, cls.env.ref('ems.group_teacher').id)],
        })
        cls.teacher_employee = cls.env['hr.employee'].create({
            'name': 'GI Teacher Employee', 'user_id': cls.teacher_user.id, 'employee_type': 'teacher',
        })

        cls.level = cls.env['ems.level'].create({'acronym': 'GIL', 'name': 'GI Level'})
        cls.study = cls.env['ems.study'].create({
            'code': 'GISTD', 'acronym': 'GIS', 'name': 'GI Study',
            'date': date.today(), 'deprecated': False, 'level_id': cls.level.id,
        })
        # Subject without work placement (external ponderation 0).
        cls.subj_no_em = cls.env['ems.subject'].create({
            'code': 'GI01', 'acronym': 'GI01', 'name': 'GI Subject No EM',
            'study_ids': [(4, cls.study.id)],
        })
        cls.o1 = cls.env['ems.outcome'].create({'code': 'GI01_01RA', 'acronym': 'RA1', 'name': 'O1', 'subject_id': cls.subj_no_em.id})
        cls.o2 = cls.env['ems.outcome'].create({'code': 'GI01_02RA', 'acronym': 'RA2', 'name': 'O2', 'subject_id': cls.subj_no_em.id})
        cls.env['ems.planning'].create({
            'study_id': cls.study.id, 'subject_id': cls.subj_no_em.id,
            'internal_ponderation': 100.0, 'external_ponderation': 0.0,
            'planning_outcome_ids': [
                (0, 0, {'outcome_id': cls.o1.id, 'ponderation': 50.0}),
                (0, 0, {'outcome_id': cls.o2.id, 'ponderation': 50.0}),
            ],
        })
        # Subject with work placement (external ponderation 10) + an EM outcome.
        cls.subj_em = cls.env['ems.subject'].create({
            'code': 'GI02', 'acronym': 'GI02', 'name': 'GI Subject With EM',
            'study_ids': [(4, cls.study.id)],
        })
        cls.e1 = cls.env['ems.outcome'].create({'code': 'GI02_01RA', 'acronym': 'RA1', 'name': 'E1', 'subject_id': cls.subj_em.id})
        cls.env['ems.planning'].create({
            'study_id': cls.study.id, 'subject_id': cls.subj_em.id,
            'internal_ponderation': 90.0, 'external_ponderation': 10.0,
            'planning_outcome_ids': [(0, 0, {'outcome_id': cls.e1.id, 'ponderation': 100.0})],
        })
        # Optional subject: its EMS code (OPT9) deliberately differs from Esfera's (OPT2).
        cls.subj_opt = cls.env['ems.subject'].create({
            'code': 'OPT9', 'acronym': 'OPT9', 'name': 'GI Optional Subject',
            'study_ids': [(4, cls.study.id)],
        })
        cls.opt1 = cls.env['ems.outcome'].create({'code': 'OPT9_01RA', 'acronym': 'RA1', 'name': 'OPT O1', 'subject_id': cls.subj_opt.id})
        cls.env['ems.planning'].create({
            'study_id': cls.study.id, 'subject_id': cls.subj_opt.id,
            'internal_ponderation': 100.0, 'external_ponderation': 0.0,
            'planning_outcome_ids': [(0, 0, {'outcome_id': cls.opt1.id, 'ponderation': 100.0})],
        })

        cls.group = cls.env['ems.group'].create({
            'course': 1, 'acronym': 'A', 'level_id': cls.level.id, 'study_id': cls.study.id,
        })
        cls.student = cls.env['res.partner'].create({
            'name': 'GI Student', 'contact_type': 'student', 'student_id': '9990001', 'main_group_id': cls.group.id,
        })
        for subject in (cls.subj_no_em, cls.subj_em, cls.subj_opt):
            cls.env['ems.enrollment'].create({
                'student_id': cls.student.id, 'group_id': cls.group.id, 'subject_id': subject.id,
            })

    def _session(self, subject, round="1"):
        session = self.env['ems.grade_session'].create({
            'group_id': self.group.id, 'subject_id': subject.id, 'round': round,
            'teacher_id': self.teacher_employee.id,
        })
        session.fill_students()
        return session

    def _flat_xlsx(self, rows, sheet_name="Notes Flat"):
        # rows: list of (idAlumne, CodiMod, Codi, Tipus, Subtipus, Nota)
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = sheet_name
        ws.append(["idAlumne", "nom Alumne", "Codi Mòdul", "Nom Mòdul", "Codi", "Nom", "Tipus", "Subtipus", "Nota"])
        for idalu, mod, codi, tipus, sub, nota in rows:
            ws.append([idalu, "Student", mod, mod, codi, codi, tipus, sub, nota])
        buf = io.BytesIO()
        wb.save(buf)
        return base64.b64encode(buf.getvalue())

    def _pivot_xlsx(self, headers, data_rows):
        # headers: list of column labels; data_rows: list of full row value lists.
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Notes"
        ws.append([None] * len(headers))  # merged title row (ignored)
        ws.append(headers)
        for row in data_rows:
            ws.append(row)
        buf = io.BytesIO()
        wb.save(buf)
        return base64.b64encode(buf.getvalue())

    def _run(self, file_b64, round="1", **extra):
        vals = {'round': round, 'file': file_b64, 'file_name': 'x.xlsx'}
        vals.update(extra)
        wizard = self.env['ems.grade_import_wizard'].create(vals)
        wizard.action_import()
        return wizard

    def _unenrolled_student(self, student_id='9990002'):
        # A student of the group with no enrollment at all: the sessions have no lines for them.
        return self.env['res.partner'].create({
            'name': 'GI Unenrolled', 'contact_type': 'student',
            'student_id': student_id, 'main_group_id': self.group.id,
        })

    def _enrollment_count(self, student, subject):
        return self.env['ems.enrollment'].search_count([
            ('student_id', '=', student.id), ('subject_id', '=', subject.id),
        ])

    # --- Tests ---

    def test_flat_ra_and_em(self):
        s_no = self._session(self.subj_no_em)
        s_em = self._session(self.subj_em)
        # Excel codes carry the cycle token "_CYC" that EMS does not store.
        file = self._flat_xlsx([
            ('9990001', 'GI01_CYC', 'GI01_CYC_01RA', 'RA', '01', 8),
            ('9990001', 'GI01_CYC', 'GI01_CYC_02RA', 'RA', '02', 6),
            ('9990001', 'GI02_CYC', 'GI02_CYC_01RA', 'RA', '01', 7),
            ('9990001', 'GI02_CYC', 'GI02_CYC_01EM', 'EM', '01', 9),
        ])
        self._run(file)
        l1 = s_no.grade_outcome_line_ids.filtered(lambda l: l.outcome_id == self.o1)
        l2 = s_no.grade_outcome_line_ids.filtered(lambda l: l.outcome_id == self.o2)
        self.assertEqual((l1.score, l1.is_scored), (8, True))
        self.assertEqual((l2.score, l2.is_scored), (6, True))
        subj_line = s_em.grade_subject_line_ids
        self.assertEqual((subj_line.external_score, subj_line.external_is_scored), (9, True))
        self.assertEqual(s_em.grade_outcome_line_ids.score, 7)

    def test_pivot_sheet(self):
        s_no = self._session(self.subj_no_em)
        headers = ['idAlumne', 'nom', 'n. convocatoria', 'GI01_CYC', 'provisional', 'GI01_CYC_01RA', 'GI01_CYC_02RA']
        file = self._pivot_xlsx(headers, [['9990001', 'Student', '1', 5, '', 5, 9]])
        self._run(file)
        l1 = s_no.grade_outcome_line_ids.filtered(lambda l: l.outcome_id == self.o1)
        l2 = s_no.grade_outcome_line_ids.filtered(lambda l: l.outcome_id == self.o2)
        self.assertEqual((l1.score, l2.score), (5, 9))
        # MP column (bare code, value 5) stored as an override on the subject line.
        self.assertTrue(s_no.grade_subject_line_ids.is_overridden)
        self.assertEqual(s_no.grade_subject_line_ids.internal_score, 5)

    def test_student_not_found(self):
        s_no = self._session(self.subj_no_em)
        file = self._flat_xlsx([
            ('0000000', 'GI01', 'GI01_01RA', 'RA', '01', 8),
            ('9990001', 'GI01', 'GI01_01RA', 'RA', '01', 7),
        ])
        wizard = self._run(file)
        self.assertIn('Student not found', wizard.result_html)
        # The valid row is still applied.
        self.assertEqual(s_no.grade_outcome_line_ids.filtered(lambda l: l.outcome_id == self.o1).score, 7)

    def test_missing_session(self):
        # No session created at all: the module cannot be resolved.
        file = self._flat_xlsx([('9990001', 'GI01', 'GI01_01RA', 'RA', '01', 8)])
        wizard = self._run(file)
        self.assertIn('No evaluation session', wizard.result_html)

    def test_aggregate_columns_skipped(self):
        # QFINAL / QUNIVERSITAT are export-only aggregates, not subjects: skipped, not reported as errors.
        s_no = self._session(self.subj_no_em)
        file = self._flat_xlsx([
            ('9990001', 'QFINAL', 'QFINAL', 'MP', 'MP', 8),
            ('9990001', 'QUNIVERSITAT', 'QUNIVERSITAT', 'MP', 'MP', 7),
            ('9990001', 'GI01', 'GI01_01RA', 'RA', '01', 6),
        ])
        wizard = self._run(file)
        self.assertNotIn('QFINAL', wizard.result_html)
        self.assertNotIn('QUNIVERSITAT', wizard.result_html)
        self.assertNotIn('Errors', wizard.result_html)
        # The real grade is still applied.
        self.assertEqual(s_no.grade_outcome_line_ids.filtered(lambda l: l.outcome_id == self.o1).score, 6)

    def test_locked_outcome_overwritten_releases_lock_without_touching_past(self):
        # Pass o1 in round 1, then it is locked in round 2.
        s1 = self._session(self.subj_no_em, round="1")
        r1_line = s1.grade_outcome_line_ids.filtered(lambda l: l.outcome_id == self.o1)
        r1_line.write({'score': 8, 'is_scored': True})
        s2 = self._session(self.subj_no_em, round="2")
        locked = s2.grade_outcome_line_ids.filtered(lambda l: l.outcome_id == self.o1)
        self.assertTrue(locked.is_locked)
        # Manual edit is still blocked.
        with self.assertRaises(UserError):
            locked.write({'score': 3, 'is_scored': True})
        # The import overwrites the round-2 line and releases its lock, WITHOUT altering round 1.
        file = self._flat_xlsx([('9990001', 'GI01', 'GI01_01RA', 'RA', '01', 4)])
        self._run(file, round="2")
        self.assertEqual(locked.score, 4)
        self.assertTrue(locked.is_lock_released)
        # Round 1 is untouched: its history is preserved.
        self.assertEqual(r1_line.score, 8)
        self.assertTrue(r1_line.is_scored)
        # is_locked is a search-based compute; force a fresh read (as the UI does on each load).
        locked.invalidate_recordset(['is_locked'])
        self.assertFalse(locked.is_locked)

    def test_mp_override_no_em(self):
        s_no = self._session(self.subj_no_em)
        file = self._flat_xlsx([
            ('9990001', 'GI01', 'GI01_01RA', 'RA', '01', 8),
            ('9990001', 'GI01', 'GI01_02RA', 'RA', '02', 8),
            ('9990001', 'GI01', 'GI01', 'MP', 'MP', 6),
        ])
        self._run(file)
        line = s_no.grade_subject_line_ids
        self.assertTrue(line.is_overridden)
        self.assertEqual(line.internal_score, 6)
        self.assertEqual(line.final_score, 6)

    def test_mp_with_em_warns_on_divergence(self):
        s_em = self._session(self.subj_em)
        # RA 7 (internal), EM 7 (external) => final 7; but the file claims MP 9.
        file = self._flat_xlsx([
            ('9990001', 'GI02', 'GI02_01RA', 'RA', '01', 7),
            ('9990001', 'GI02', 'GI02_01EM', 'EM', '01', 7),
            ('9990001', 'GI02', 'GI02', 'MP', 'MP', 9),
        ])
        wizard = self._run(file)
        line = s_em.grade_subject_line_ids
        self.assertFalse(line.is_overridden)
        self.assertEqual(line.final_score, 7)
        self.assertIn('mismatch', wizard.result_html)

    def test_textual_note_not_scored(self):
        s_no = self._session(self.subj_no_em)
        line = s_no.grade_outcome_line_ids.filtered(lambda l: l.outcome_id == self.o1)
        file = self._flat_xlsx([('9990001', 'GI01', 'GI01_01RA', 'RA', '01', 'NP')])
        self._run(file)
        self.assertFalse(line.is_scored)

    def test_optional_module_mapped_by_enrollment(self):
        # Esfera exports the optional as "OPT2", but this study's optional is EMS code "OPT9".
        s_opt = self._session(self.subj_opt)
        file = self._flat_xlsx([
            ('9990001', 'OPT2_CYC', 'OPT2_CYC_01RA', 'RA', '01', 8),
            ('9990001', 'OPT2', 'OPT2', 'MP', 'MP', 8),
        ])
        wizard = self._run(file)
        self.assertNotIn('No evaluation session', wizard.result_html)
        line = s_opt.grade_outcome_line_ids.filtered(lambda l: l.outcome_id == self.opt1)
        self.assertEqual((line.score, line.is_scored), (8, True))
        self.assertTrue(s_opt.grade_subject_line_ids.is_overridden)
        self.assertEqual(s_opt.grade_subject_line_ids.internal_score, 8)

    def test_missing_enrollment_created_for_numeric_grade(self):
        # The session exists (another student is enrolled) but this one is not: with the option on,
        # the enrollment is created and the grade lands instead of being discarded.
        student = self._unenrolled_student()
        s_no = self._session(self.subj_no_em)
        file = self._flat_xlsx([
            ('9990002', 'GI01_CYC', 'GI01_CYC_01RA', 'RA', '01', 8),
            ('9990002', 'GI01_CYC', 'GI01_CYC_02RA', 'RA', '02', 6),
        ])
        wizard = self._run(file, create_missing_enrollments=True)
        self.assertEqual(self._enrollment_count(student, self.subj_no_em), 1)
        self.assertIn('Missing enrollments created', wizard.result_html)
        self.assertNotIn('No grade line', wizard.result_html)
        line = s_no.grade_outcome_line_ids.filtered(
            lambda l: l.student_id == student and l.outcome_id == self.o1)
        self.assertEqual((line.score, line.is_scored), (8, True))

    def test_missing_enrollment_created_for_textual_grades(self):
        # A textual grade is a grade too: PDT/NP say the module is not passed and CV says it is,
        # but all of them state the module belongs to the student's record.
        student = self._unenrolled_student()
        s_no = self._session(self.subj_no_em)
        file = self._flat_xlsx([
            ('9990002', 'GI01', 'GI01_01RA', 'RA', '01', 'CV'),
            ('9990002', 'GI01', 'GI01_02RA', 'RA', '02', 'PDT'),
        ])
        wizard = self._run(file, create_missing_enrollments=True)
        self.assertEqual(self._enrollment_count(student, self.subj_no_em), 1)
        self.assertIn('Missing enrollments created', wizard.result_html)
        # The line exists and is left unscored, as any textual grade is.
        line = s_no.grade_outcome_line_ids.filtered(
            lambda l: l.student_id == student and l.outcome_id == self.o1)
        self.assertTrue(line)
        self.assertFalse(line.is_scored)

    def test_missing_enrollment_not_created_for_blank_module(self):
        # A module left entirely blank is how Esfera lists what a student does not take.
        student = self._unenrolled_student()
        self._session(self.subj_no_em)
        file = self._flat_xlsx([
            ('9990002', 'GI01', 'GI01_01RA', 'RA', '01', ''),
            ('9990002', 'GI01', 'GI01_02RA', 'RA', '02', None),
        ])
        wizard = self._run(file, create_missing_enrollments=True)
        self.assertEqual(self._enrollment_count(student, self.subj_no_em), 0)
        self.assertIn('No grade line', wizard.result_html)

    def test_missing_enrollment_left_alone_when_option_disabled(self):
        # Default behaviour: the grade is reported as having nowhere to go.
        student = self._unenrolled_student()
        self._session(self.subj_no_em)
        file = self._flat_xlsx([('9990002', 'GI01', 'GI01_01RA', 'RA', '01', 8)])
        wizard = self._run(file)
        self.assertEqual(self._enrollment_count(student, self.subj_no_em), 0)
        self.assertIn('No grade line', wizard.result_html)
        self.assertNotIn('Missing enrollments created', wizard.result_html)

    def test_existing_enrollment_not_duplicated(self):
        s_no = self._session(self.subj_no_em)
        file = self._flat_xlsx([('9990001', 'GI01', 'GI01_01RA', 'RA', '01', 8)])
        wizard = self._run(file, create_missing_enrollments=True)
        self.assertEqual(self._enrollment_count(self.student, self.subj_no_em), 1)
        self.assertNotIn('Missing enrollments created', wizard.result_html)
        self.assertEqual(s_no.grade_outcome_line_ids.filtered(
            lambda l: l.outcome_id == self.o1).score, 8)

    def test_enrollment_in_another_group_warns_instead_of_enrolling(self):
        # Enrolled for this module in a different group: an anomaly to review by hand, not one to
        # fix by adding a second enrollment.
        student = self._unenrolled_student()
        other_group = self.env['ems.group'].create({
            'course': 1, 'acronym': 'B', 'level_id': self.level.id, 'study_id': self.study.id,
        })
        self.env['ems.enrollment'].create({
            'student_id': student.id, 'group_id': other_group.id, 'subject_id': self.subj_no_em.id,
        })
        self._session(self.subj_no_em)
        file = self._flat_xlsx([('9990002', 'GI01', 'GI01_01RA', 'RA', '01', 8)])
        wizard = self._run(file, create_missing_enrollments=True)
        self.assertEqual(self._enrollment_count(student, self.subj_no_em), 1)
        self.assertIn('enrollment left untouched', wizard.result_html)

    def test_missing_enrollment_created_for_the_single_optional(self):
        # Esfera's optional code (OPT2) never matches the EMS one (OPT9), and the enrollment that
        # normally resolves it is the one missing — but with a single optional in the group there
        # is nothing to be ambiguous about.
        student = self._unenrolled_student()
        s_opt = self._session(self.subj_opt)
        file = self._flat_xlsx([('9990002', 'OPT2_CYC', 'OPT2_CYC_01RA', 'RA', '01', 8)])
        wizard = self._run(file, create_missing_enrollments=True)
        self.assertEqual(self._enrollment_count(student, self.subj_opt), 1)
        line = s_opt.grade_outcome_line_ids.filtered(
            lambda l: l.student_id == student and l.outcome_id == self.opt1)
        self.assertEqual((line.score, line.is_scored), (8, True))

    def test_ambiguous_optional_warns_instead_of_enrolling(self):
        # Two optionals graded in the group: the file cannot say which one, so nothing is created.
        student = self._unenrolled_student()
        subj_opt2 = self.env['ems.subject'].create({
            'code': 'OPT8', 'acronym': 'OPT8', 'name': 'GI Second Optional',
            'study_ids': [(4, self.study.id)],
        })
        opt2_outcome = self.env['ems.outcome'].create({
            'code': 'OPT8_01RA', 'acronym': 'RA1', 'name': 'OPT2 O1', 'subject_id': subj_opt2.id,
        })
        self.env['ems.planning'].create({
            'study_id': self.study.id, 'subject_id': subj_opt2.id,
            'internal_ponderation': 100.0, 'external_ponderation': 0.0,
            'planning_outcome_ids': [(0, 0, {'outcome_id': opt2_outcome.id, 'ponderation': 100.0})],
        })
        self.env['ems.enrollment'].create({
            'student_id': self.student.id, 'group_id': self.group.id, 'subject_id': subj_opt2.id,
        })
        self._session(self.subj_opt)
        self._session(subj_opt2)
        file = self._flat_xlsx([('9990002', 'OPT2_CYC', 'OPT2_CYC_01RA', 'RA', '01', 8)])
        wizard = self._run(file, create_missing_enrollments=True)
        self.assertEqual(self._enrollment_count(student, self.subj_opt), 0)
        self.assertEqual(self._enrollment_count(student, subj_opt2), 0)
        self.assertIn('optional subjects', wizard.result_html)

    def test_access_restricted_to_admin(self):
        s_no = self._session(self.subj_no_em)
        file = self._flat_xlsx([('9990001', 'GI01', 'GI01_01RA', 'RA', '01', 8)])
        with self.assertRaises(AccessError):
            self.env['ems.grade_import_wizard'].with_user(self.teacher_user).create({
                'round': '1', 'file': file, 'file_name': 'x.xlsx',
            })
