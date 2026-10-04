from odoo.tests.common import TransactionCase


class TestNonTeachingType(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

    def test_create_valid(self):
        non_teaching_type = self.env['ems.non_teaching_type'].create({'code': 'T01', 'name': 'Test 01'})
        self.assertTrue(non_teaching_type.id)
        self.assertEqual(non_teaching_type.code, 'T01')
        self.assertEqual(non_teaching_type.name, 'Test 01')
        self.assertFalse(non_teaching_type.is_break)
        self.assertFalse(non_teaching_type.is_fixed)
        self.assertTrue(non_teaching_type.active)

    def test_create_missing_code(self):
        with self.assertRaises(Exception):
            self.env['ems.non_teaching_type'].create({'name': 'No Code'})

    def test_create_missing_name(self):
        with self.assertRaises(Exception):
            self.env['ems.non_teaching_type'].create({'code': 'T02'})

    def test_code_must_be_unique(self):
        self.env['ems.non_teaching_type'].create({'code': 'UNIQ', 'name': 'First'})
        with self.assertRaises(Exception):
            self.env['ems.non_teaching_type'].create({'code': 'UNIQ', 'name': 'Second'})

    def test_display_name(self):
        non_teaching_type = self.env['ems.non_teaching_type'].create({'code': 'T03', 'name': 'Guard'})
        self.assertEqual(non_teaching_type.display_name, 'Guard')
