from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import TransactionCase


class TestCriteria(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.teacher_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Teacher (Criteria)',
            'login': 'test_teacher_for_criteria',
            'groups_id': [(4, cls.env.ref('ems.group_teacher').id)],
        })
        cls.secretary_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Secretary (Criteria)',
            'login': 'test_secretary_for_criteria',
            'groups_id': [(4, cls.env.ref('ems.group_secretary').id)],
        })
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

    def test_create_valid(self):
        criteria = self.env['ems.criteria'].create({
            'code': 'TST_CRIT_SUBJ_RA1_B',
            'acronym': 'CB1',
            'name': 'Test 01',
            'outcome_id': self.test_outcome.id,
        })
        self.assertTrue(criteria.id)
        self.assertEqual(criteria.outcome_id, self.test_outcome)

    def test_create_missing_code(self):
        with self.assertRaises(Exception):
            self.env['ems.criteria'].create({
                'acronym': 'T02',
                'name': 'No Code',
                'outcome_id': self.test_outcome.id,
            })

    def test_create_missing_outcome(self):
        with self.assertRaises(Exception):
            self.env['ems.criteria'].create({
                'code': 'TST_NO_OUTCOME',
                'acronym': 'T03',
                'name': 'No Outcome',
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

    def test_admin_can_create(self):
        criteria = self.env['ems.criteria'].create({
            'code': 'TST_CRIT_SUBJ_RA1_D',
            'acronym': 'CD1',
            'name': 'Admin Test',
            'outcome_id': self.test_outcome.id,
        })
        self.assertTrue(criteria.id)

    def test_admin_can_write(self):
        criteria = self.env['ems.criteria'].create({
            'code': 'TST_CRIT_SUBJ_RA1_E',
            'acronym': 'CE1',
            'name': 'Before Write',
            'outcome_id': self.test_outcome.id,
        })
        criteria.write({'name': 'After Write'})
        self.assertEqual(criteria.name, 'After Write')

    def test_admin_can_unlink(self):
        criteria = self.env['ems.criteria'].create({
            'code': 'TST_CRIT_SUBJ_RA1_F',
            'acronym': 'CF1',
            'name': 'To Delete',
            'outcome_id': self.test_outcome.id,
        })
        criteria_id = criteria.id
        criteria.unlink()
        self.assertFalse(self.env['ems.criteria'].search([('id', '=', criteria_id)]))

    def test_teacher_cannot_create(self):
        with self.assertRaises(AccessError):
            self.env['ems.criteria'].with_user(self.teacher_user).create({
                'code': 'TST_CRIT_SUBJ_RA1_G',
                'acronym': 'CG1',
                'name': 'Teacher Attempt',
                'outcome_id': self.test_outcome.id,
            })

    def test_teacher_cannot_write(self):
        with self.assertRaises(AccessError):
            self.test_criteria.with_user(self.teacher_user).write({'name': 'Teacher Write'})

    def test_teacher_cannot_unlink(self):
        with self.assertRaises(AccessError):
            self.test_criteria.with_user(self.teacher_user).unlink()

    def test_teacher_can_read(self):
        criteria = self.test_criteria.with_user(self.teacher_user)
        self.assertEqual(criteria.name, 'Test Criteria')

    def test_secretary_cannot_create(self):
        with self.assertRaises(AccessError):
            self.env['ems.criteria'].with_user(self.secretary_user).create({
                'code': 'TST_CRIT_SUBJ_RA1_H',
                'acronym': 'CH1',
                'name': 'Secretary Attempt',
                'outcome_id': self.test_outcome.id,
            })

    def test_secretary_cannot_write(self):
        with self.assertRaises(AccessError):
            self.test_criteria.with_user(self.secretary_user).write({'name': 'Secretary Write'})

    def test_secretary_cannot_unlink(self):
        with self.assertRaises(AccessError):
            self.test_criteria.with_user(self.secretary_user).unlink()
