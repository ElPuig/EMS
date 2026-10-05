from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestCriteria(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.test_subject = cls.env['ems.subject'].create({
            'code': 'TST_CRIT_SUBJ',
            'acronym': 'TCSJ',
            'name': 'Test Subject for Criteria',
        })
        cls.test_outcome = cls.env['ems.outcome'].create({
            'code': 'TST_CRIT_SUBJ_RA1',
            'acronym': 'RA1',
            'name': 'Test Outcome for Criteria',
            'subject_id': cls.test_subject.id,
        })
        cls.test_criteria = cls.env['ems.criteria'].create({
            'code': 'TST_CRIT_SUBJ_RA1_A',
            'acronym': 'CA1',
            'name': 'Test Criteria',
            'outcome_id': cls.test_outcome.id,
        })

    def test_code_must_start_with_outcome_code(self):
        with self.assertRaises(ValidationError):
            self.env['ems.criteria'].create({
                'code': 'WRONG_PREFIX_CA1',
                'acronym': 'CAX',
                'name': 'Bad Prefix',
                'outcome_id': self.test_outcome.id,
            })

    def test_code_must_be_unique(self):
        with self.assertRaises(Exception):
            self.env['ems.criteria'].create({
                'code': 'TST_CRIT_SUBJ_RA1_A',
                'acronym': 'DUP',
                'name': 'Duplicate Code',
                'outcome_id': self.test_outcome.id,
            })

    def test_display_name_computed(self):
        criteria = self.env['ems.criteria'].create({
            'code': 'TST_CRIT_SUBJ_RA1_C',
            'acronym': 'CC1',
            'name': 'Test Display',
            'outcome_id': self.test_outcome.id,
        })
        self.assertEqual(criteria.display_name, 'CC1: Test Display')

    def test_outcome_criteria_ids_relation(self):
        self.assertIn(self.test_criteria, self.test_outcome.criteria_ids)
