from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestOutcome(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.test_subject = cls.env['ems.subject'].create({
            'code': 'TST_OUT_SUBJ',
            'acronym': 'TOSJ',
            'name': 'Test Subject for Outcome',
        })
        cls.test_outcome = cls.env['ems.outcome'].create({
            'code': 'TST_OUT_SUBJ_RA1',
            'acronym': 'RA1',
            'name': 'Test Outcome',
            'subject_id': cls.test_subject.id,
        })

    def test_create_valid(self):
        outcome = self.env['ems.outcome'].create({
            'code': 'TST_OUT_SUBJ_RA2',
            'acronym': 'RA2',
            'name': 'Test 02',
            'subject_id': self.test_subject.id,
        })
        self.assertTrue(outcome.id)
        self.assertEqual(outcome.subject_id, self.test_subject)

    def test_create_missing_code(self):
        with self.assertRaises(Exception):
            self.env['ems.outcome'].create({
                'acronym': 'T02',
                'name': 'No Code',
                'subject_id': self.test_subject.id,
            })

    def test_create_missing_subject(self):
        with self.assertRaises(Exception):
            self.env['ems.outcome'].create({
                'code': 'TST_NO_SUBJ',
                'acronym': 'T03',
                'name': 'No Subject',
            })

    def test_code_must_start_with_subject_code(self):
        with self.assertRaises(ValidationError):
            self.env['ems.outcome'].create({
                'code': 'WRONG_PREFIX_RA1',
                'acronym': 'RAX',
                'name': 'Bad Prefix',
                'subject_id': self.test_subject.id,
            })

    def test_display_name_computed(self):
        outcome = self.env['ems.outcome'].create({
            'code': 'TST_OUT_SUBJ_RA3',
            'acronym': 'RA3',
            'name': 'Test Display',
            'subject_id': self.test_subject.id,
        })
        self.assertEqual(outcome.display_name, 'RA3: Test Display')

    def test_subject_outcome_ids_relation(self):
        self.assertIn(self.test_outcome, self.test_subject.outcome_ids)
