from datetime import date

from odoo.tests.common import TransactionCase


class TestLevel(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

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
