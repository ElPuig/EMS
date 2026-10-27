# -*- coding: utf-8 -*-

import base64

from odoo.exceptions import UserError
from odoo.tests import Form
from odoo.tests.common import TransactionCase

from ..models.grades.previous_curriculum_pdf import grade_passes, parse_previous_curriculum_record
from .common import build_previous_curriculum_pdf, create_level_study, create_role_user, next_student_id


class TestPreviousCurriculumRecord(TransactionCase):
    """The academic history of a previous curriculum (issue #672), imported from its document and
    kept as printed: modules and units (UF) with their hours, grade and sitting."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.center_code = '08000777'
        # The current study that took over the invented cycle ICX0.
        cls.level, cls.study = create_level_study(cls, 'PCR', study={'code': 'CFGS_ICX0'})
        cls.secretary = create_role_user(cls, 'secretary', 'test_secretary_previous_curriculum')
        cls.head_of_studies = create_role_user(cls, 'head_of_studies', 'test_hos_previous_curriculum')

    def setUp(self):
        super().setUp()
        self.student = self.env['res.partner'].create({
            'name': 'Previous Curriculum Student', 'contact_type': 'student',
            'student_id': next_student_id()})

    def _document(self, identifier=None, failed=True, **kwargs):
        """Module 001 passed, with a unit name wrapped at a hyphen; module 002 not graded yet (a
        unit pending) or passed; the work placement apte."""
        return build_previous_curriculum_pdf(identifier or self.student.student_id, [
            ('001', 'MP1. Primer mòdul|inventat', 99, '6', 'Ext.', [
                ('00101', 'UF1. Unitat objecte-|relacional', 66, '7', '1'),
                ('00102', 'UF2. Segona unitat', 33, '5', '2'),
            ]),
            ('002', 'MP2. Segon mòdul', 0 if failed else 66, '' if failed else '8', '' if failed else 'Ord.', [
                ('00201', 'UF1. Unitat pendent', 66, 'NP' if failed else '8', '' if failed else '1'),
            ]),
            ('014', 'MP14. Formació en centres de|treball', 317, 'Ap', 'Ord.', [
                ('01401', 'Formació en centres de treball', 317, 'Ap', '1'),
            ]),
        ], **kwargs)

    def _read(self, pdf, user=None):
        Wizard = self.env['ems.previous_curriculum_wizard'].with_user(user or self.secretary)
        form = Form(Wizard.with_context(default_student_id=self.student.id))
        form.certificate_file = base64.b64encode(pdf)
        return form

    def test_the_document_is_read_as_printed(self):
        document = parse_previous_curriculum_record(self._document())
        self.assertEqual(document['student_identifier'], self.student.student_id)
        self.assertEqual((document['centre_code'], document['centre_name']), ('08000777', 'Institut Inventat'))
        self.assertEqual(document['curriculum_code'], 'CFPS ICX0')
        self.assertEqual(document['curriculum_name'], 'CFPS Cicle Inventat (LOE)')
        self.assertEqual((document['start_year'], document['end_year']), (2080, 2082))
        first, second, placement = document['modules']
        self.assertEqual((first['code'], first['name'], first['hours'], first['grade'], first['sitting']),
                         ('001', 'MP1. Primer mòdul inventat', 99, '6', 'Ext.'))
        # The first unit shares its line with the module, and a word cut at its hyphen is rejoined.
        self.assertEqual([(unit['code'], unit['name'], unit['grade'], unit['sitting']) for unit in first['units']],
                         [('00101', 'UF1. Unitat objecte-relacional', '7', '1'),
                          ('00102', 'UF2. Segona unitat', '5', '2')])
        # A module with a unit pending has no hours, grade or sitting yet.
        self.assertEqual((second['hours'], second['grade'], second['sitting']), (0, '', ''))
        self.assertEqual(second['units'][0]['grade'], 'NP')
        self.assertEqual(placement['name'], 'MP14. Formació en centres de treball')

    def test_passing_grades(self):
        for grade in ('5', '10', 'Ap', 'CV', 'EX'):
            self.assertTrue(grade_passes(grade), grade)
        for grade in ('4', 'NP', 'NA', '', False):
            self.assertFalse(grade_passes(grade), grade)

    def test_import_creates_the_record(self):
        form = self._read(self._document())
        self.assertEqual(form.study_id, self.study)
        # A module not passed: the title is not proposed.
        self.assertFalse(form.title_obtained)
        form.save().action_create()
        record = self.student.previous_curriculum_record_ids
        self.assertEqual(record.curriculum_name, 'CFPS Cicle Inventat (LOE)')
        self.assertEqual(record.centre_code, '08000777')
        self.assertTrue(record.certificate_file)
        self.assertEqual(record.line_ids.mapped('code'), ['001', '00101', '00102', '002', '00201', '014', '01401'])
        self.assertEqual((record.module_count, record.passed_module_count), (3, 2))
        self.assertFalse(record.title_obtained)
        self.assertIn('Previous curriculum record of CFPS Cicle Inventat (LOE) (2080-2082)',
                      self.student.message_ids[0].body)

    def test_title_is_proposed_when_every_module_is_passed(self):
        form = self._read(self._document(failed=False), user=self.head_of_studies)
        self.assertTrue(form.title_obtained)
        form.save().action_create()
        self.assertTrue(self.student.previous_curriculum_record_ids.title_obtained)

    def test_a_grade_corrected_in_the_grid_is_kept(self):
        form = self._read(self._document())
        with form.line_ids.edit(3) as line:
            self.assertEqual(line.code, '002')
            line.grade = '5'
        form.save().action_create()
        module = self.student.previous_curriculum_record_ids.line_ids.filtered(lambda line: line.code == '002')
        self.assertEqual(module.grade, '5')
        self.assertTrue(module.is_passed)

    def test_another_students_document_is_refused(self):
        form = self._read(self._document(identifier='TEST999999'))
        wizard = form.save()
        with self.assertRaises(UserError):
            wizard.action_create()
        self.assertFalse(self.student.previous_curriculum_record_ids)

    def test_the_same_curriculum_is_not_imported_twice(self):
        self._read(self._document()).save().action_create()
        with self.assertRaises(UserError):
            self._read(self._document()).save().action_create()

    def test_a_file_that_is_not_the_document_is_reported(self):
        form = self._read(b'not a pdf')
        self.assertTrue(form.certificate_message)
        self.assertFalse(form.line_ids)
        with self.assertRaises(UserError):
            form.save().action_create()
