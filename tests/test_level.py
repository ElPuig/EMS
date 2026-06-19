from datetime import date

from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import TransactionCase


class TestLevel(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.teacher_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Teacher (Level)',
            'login': 'test_teacher_for_level',
            'groups_id': [(4, cls.env.ref('ems.group_teacher').id)],
        })
        cls.secretary_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Test Secretary (Level)',
            'login': 'test_secretary_for_level',
            'groups_id': [(4, cls.env.ref('ems.group_secretary').id)],
        })
        cls.test_level = cls.env['ems.level'].create({
            'acronym': 'TST',
            'name': 'Test Level',
        })

    def test_create_valid(self):
        level = self.env['ems.level'].create({'acronym': 'T01', 'name': 'Test 01'})
        self.assertTrue(level.id)
        self.assertEqual(level.acronym, 'T01')
        self.assertEqual(level.name, 'Test 01')

    def test_create_missing_acronym(self):
        with self.assertRaises(Exception):
            self.env['ems.level'].create({'name': 'No Acronym'})

    def test_create_missing_name(self):
        with self.assertRaises(Exception):
            self.env['ems.level'].create({'acronym': 'T02'})

    def test_display_name_computed(self):
        level = self.env['ems.level'].create({'acronym': 'TSCX', 'name': 'Test Display'})
        self.assertEqual(level.display_name, 'TSCX: Test Display')

    def test_acronym_must_be_unique(self):
        self.env['ems.level'].create({'acronym': 'UNIQ', 'name': 'First'})
        with self.assertRaises(Exception):
            self.env['ems.level'].create({'acronym': 'UNIQ', 'name': 'Second'})

    def test_admin_can_create(self):
        level = self.env['ems.level'].create({'acronym': 'T03', 'name': 'Admin Test'})
        self.assertTrue(level.id)

    def test_admin_can_write(self):
        level = self.env['ems.level'].create({'acronym': 'T03W', 'name': 'Before Write'})
        level.write({'name': 'After Write'})
        self.assertEqual(level.name, 'After Write')

    def test_admin_can_unlink(self):
        level = self.env['ems.level'].create({'acronym': 'T04', 'name': 'To Delete'})
        level_id = level.id
        level.unlink()
        self.assertFalse(self.env['ems.level'].search([('id', '=', level_id)]))

    def test_teacher_cannot_create(self):
        with self.assertRaises(AccessError):
            self.env['ems.level'].with_user(self.teacher_user).create({
                'acronym': 'T05',
                'name': 'Teacher Attempt',
            })

    def test_teacher_cannot_write(self):
        with self.assertRaises(AccessError):
            self.test_level.with_user(self.teacher_user).write({'name': 'Teacher Write'})

    def test_teacher_cannot_unlink(self):
        with self.assertRaises(AccessError):
            self.test_level.with_user(self.teacher_user).unlink()

    def test_secretary_cannot_create(self):
        with self.assertRaises(AccessError):
            self.env['ems.level'].with_user(self.secretary_user).create({
                'acronym': 'T06',
                'name': 'Secretary Attempt',
            })

    def test_secretary_cannot_write(self):
        with self.assertRaises(AccessError):
            self.test_level.with_user(self.secretary_user).write({'name': 'Secretary Write'})

    def test_secretary_cannot_unlink(self):
        with self.assertRaises(AccessError):
            self.test_level.with_user(self.secretary_user).unlink()

    def test_study_ids_relation(self):
        level = self.env['ems.level'].create({'acronym': 'T07', 'name': 'Level With Study'})
        study = self.env['ems.study'].create({
            'code': 'TST001',
            'acronym': 'TSST',
            'name': 'Test Study for Level',
            'date': date.today(),
            'deprecated': False,
            'level_id': level.id,
        })
        self.assertIn(study, level.study_ids)
