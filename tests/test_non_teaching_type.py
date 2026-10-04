from odoo.tests.common import TransactionCase


class TestNonTeachingType(TransactionCase):

    def test_code_must_be_unique(self):
        self.env['ems.non_teaching_type'].create({'code': 'UNIQ', 'name': 'First'})
        with self.assertRaises(Exception):
            self.env['ems.non_teaching_type'].create({'code': 'UNIQ', 'name': 'Second'})
