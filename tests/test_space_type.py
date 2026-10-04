from odoo.tests.common import TransactionCase


class TestSpaceType(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

    def test_create_valid(self):
        space_type = self.env['ems.space_type'].create({'name': 'Test 01'})
        self.assertTrue(space_type.id)
        self.assertEqual(space_type.name, 'Test 01')

    def test_create_missing_name(self):
        with self.assertRaises(Exception):
            self.env['ems.space_type'].create({})
