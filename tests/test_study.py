from datetime import date

from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase

from .common import create_level_study


class TestStudy(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.teacher_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Teacher (Study)',
            'login': 'test_teacher_for_study',
            'groups_id': [(4, cls.env.ref('ems.group_teacher').id)],
        })
        cls.secretary_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Secretary (Study)',
            'login': 'test_secretary_for_study',
            'groups_id': [(4, cls.env.ref('ems.group_secretary').id)],
        })
        cls.test_level, cls.test_study = create_level_study(cls, 'TSTL', level={'name': 'Test Level for Study'}, study={
            'code': 'TST_STUDY_001', 'acronym': 'TSST', 'name': 'Test Study', 'date': date(2024, 9, 1),
        })

    def test_create_valid(self):
        study = self.env['ems.study'].create({
            'code': 'T01',
            'acronym': 'T01A',
            'name': 'Test 01',
            'date': date(2024, 9, 1),
        })
        self.assertTrue(study.id)
        self.assertEqual(study.code, 'T01')
        self.assertEqual(study.acronym, 'T01A')
        self.assertEqual(study.name, 'Test 01')

    def test_deprecated_defaults_to_false(self):
        study = self.env['ems.study'].create({
            'code': 'T01D',
            'acronym': 'T01D',
            'name': 'Test Default Deprecated',
            'date': date(2024, 9, 1),
        })
        self.assertFalse(study.deprecated)

    def test_create_missing_code(self):
        with self.assertRaises(Exception):
            self.env['ems.study'].create({
                'acronym': 'T02',
                'name': 'No Code',
                'date': date(2024, 9, 1),
            })

    def test_create_missing_acronym(self):
        with self.assertRaises(Exception):
            self.env['ems.study'].create({
                'code': 'T03',
                'name': 'No Acronym',
                'date': date(2024, 9, 1),
            })

    def test_create_missing_name(self):
        with self.assertRaises(Exception):
            self.env['ems.study'].create({
                'code': 'T04',
                'acronym': 'T04A',
                'date': date(2024, 9, 1),
            })

    def test_create_missing_date(self):
        with self.assertRaises(Exception):
            self.env['ems.study'].create({
                'code': 'T05',
                'acronym': 'T05A',
                'name': 'No Date',
            })

    def test_code_must_be_unique(self):
        self.env['ems.study'].create({
            'code': 'UNIQ001',
            'acronym': 'UQA',
            'name': 'First',
            'date': date(2024, 9, 1),
        })
        with self.assertRaises(Exception):
            self.env['ems.study'].create({
                'code': 'UNIQ001',
                'acronym': 'UQB',
                'name': 'Second',
                'date': date(2024, 9, 1),
            })

    def test_display_name_computed(self):
        study = self.env['ems.study'].create({
            'code': 'T06',
            'acronym': 'T06A',
            'name': 'Test Display',
            'date': date(2024, 9, 1),
        })
        self.assertEqual(study.display_name, 'T06A (2024): Test Display')

    def test_level_relation(self):
        self.assertIn(self.test_study, self.test_level.study_ids)

    def test_uses_enrollment_flow_false_by_default(self):
        self.assertFalse(self.test_study.uses_enrollment_flow)

    def test_uses_enrollment_flow_true_with_active_template(self):
        self.env['sale.order.template'].create({
            'name': 'Test Template for Study',
            'ems_study_id': self.test_study.id,
        })
        self.assertTrue(self.test_study.uses_enrollment_flow)

    def test_uses_enrollment_flow_search(self):
        study_without_flow = self.env['ems.study'].create({
            'code': 'T07',
            'acronym': 'T07A',
            'name': 'Without Flow',
            'date': date(2024, 9, 1),
        })
        self.env['sale.order.template'].create({
            'name': 'Test Template for Search',
            'ems_study_id': self.test_study.id,
        })
        with_flow = self.env['ems.study'].search([('uses_enrollment_flow', '=', True)])
        without_flow = self.env['ems.study'].search([('uses_enrollment_flow', '=', False)])
        self.assertIn(self.test_study, with_flow)
        self.assertNotIn(study_without_flow, with_flow)
        self.assertIn(study_without_flow, without_flow)
        self.assertNotIn(self.test_study, without_flow)

    def test_admin_can_create(self):
        study = self.env['ems.study'].create({
            'code': 'T08',
            'acronym': 'T08A',
            'name': 'Admin Test',
            'date': date(2024, 9, 1),
        })
        self.assertTrue(study.id)

    def test_admin_can_write(self):
        study = self.env['ems.study'].create({
            'code': 'T09',
            'acronym': 'T09A',
            'name': 'Before Write',
            'date': date(2024, 9, 1),
        })
        study.write({'name': 'After Write'})
        self.assertEqual(study.name, 'After Write')

    def test_admin_can_unlink(self):
        study = self.env['ems.study'].create({
            'code': 'T10',
            'acronym': 'T10A',
            'name': 'To Delete',
            'date': date(2024, 9, 1),
        })
        study_id = study.id
        study.unlink()
        self.assertFalse(self.env['ems.study'].search([('id', '=', study_id)]))

    def test_teacher_cannot_create(self):
        with self.assertRaises(AccessError):
            self.env['ems.study'].with_user(self.teacher_user).create({
                'code': 'T11',
                'acronym': 'T11A',
                'name': 'Teacher Attempt',
                'date': date(2024, 9, 1),
            })

    def test_teacher_cannot_write(self):
        with self.assertRaises(AccessError):
            self.test_study.with_user(self.teacher_user).write({'name': 'Teacher Write'})

    def test_teacher_cannot_unlink(self):
        with self.assertRaises(AccessError):
            self.test_study.with_user(self.teacher_user).unlink()

    def test_teacher_can_read(self):
        study = self.test_study.with_user(self.teacher_user)
        self.assertEqual(study.name, 'Test Study')

    def test_secretary_cannot_create(self):
        with self.assertRaises(AccessError):
            self.env['ems.study'].with_user(self.secretary_user).create({
                'code': 'T12',
                'acronym': 'T12A',
                'name': 'Secretary Attempt',
                'date': date(2024, 9, 1),
            })

    def test_secretary_cannot_write(self):
        with self.assertRaises(AccessError):
            self.test_study.with_user(self.secretary_user).write({'name': 'Secretary Write'})

    def test_secretary_cannot_unlink(self):
        with self.assertRaises(AccessError):
            self.test_study.with_user(self.secretary_user).unlink()
