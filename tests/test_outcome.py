from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import TransactionCase


class TestOutcome(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.teacher_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Teacher (Outcome)',
            'login': 'test_teacher_for_outcome',
            'groups_id': [(4, cls.env.ref('ems.group_teacher').id)],
        })
        cls.secretary_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Secretary (Outcome)',
            'login': 'test_secretary_for_outcome',
            'groups_id': [(4, cls.env.ref('ems.group_secretary').id)],
        })
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

    def test_admin_can_create(self):
        outcome = self.env['ems.outcome'].create({
            'code': 'TST_OUT_SUBJ_RA4',
            'acronym': 'RA4',
            'name': 'Admin Test',
            'subject_id': self.test_subject.id,
        })
        self.assertTrue(outcome.id)

    def test_admin_can_write(self):
        outcome = self.env['ems.outcome'].create({
            'code': 'TST_OUT_SUBJ_RA5',
            'acronym': 'RA5',
            'name': 'Before Write',
            'subject_id': self.test_subject.id,
        })
        outcome.write({'name': 'After Write'})
        self.assertEqual(outcome.name, 'After Write')

    def test_admin_can_unlink(self):
        outcome = self.env['ems.outcome'].create({
            'code': 'TST_OUT_SUBJ_RA6',
            'acronym': 'RA6',
            'name': 'To Delete',
            'subject_id': self.test_subject.id,
        })
        outcome_id = outcome.id
        outcome.unlink()
        self.assertFalse(self.env['ems.outcome'].search([('id', '=', outcome_id)]))

    def test_teacher_cannot_create(self):
        with self.assertRaises(AccessError):
            self.env['ems.outcome'].with_user(self.teacher_user).create({
                'code': 'TST_OUT_SUBJ_RA7',
                'acronym': 'RA7',
                'name': 'Teacher Attempt',
                'subject_id': self.test_subject.id,
            })

    def test_teacher_cannot_write(self):
        with self.assertRaises(AccessError):
            self.test_outcome.with_user(self.teacher_user).write({'name': 'Teacher Write'})

    def test_teacher_cannot_unlink(self):
        with self.assertRaises(AccessError):
            self.test_outcome.with_user(self.teacher_user).unlink()

    def test_teacher_can_read(self):
        outcome = self.test_outcome.with_user(self.teacher_user)
        self.assertEqual(outcome.name, 'Test Outcome')

    def test_secretary_cannot_create(self):
        with self.assertRaises(AccessError):
            self.env['ems.outcome'].with_user(self.secretary_user).create({
                'code': 'TST_OUT_SUBJ_RA8',
                'acronym': 'RA8',
                'name': 'Secretary Attempt',
                'subject_id': self.test_subject.id,
            })

    def test_secretary_cannot_write(self):
        with self.assertRaises(AccessError):
            self.test_outcome.with_user(self.secretary_user).write({'name': 'Secretary Write'})

    def test_secretary_cannot_unlink(self):
        with self.assertRaises(AccessError):
            self.test_outcome.with_user(self.secretary_user).unlink()
