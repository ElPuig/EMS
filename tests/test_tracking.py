from odoo.tests.common import TransactionCase


class TestTracking(TransactionCase):

    def test_create_with_no_fields_at_all(self):
        # Every field is optional at the model level.
        tracking = self.env['ems.tracking'].create({})
        self.assertTrue(tracking.id)

    def test_most_recent_first(self):
        first = self.env['ems.tracking'].create({'notes': 'First'})
        second = self.env['ems.tracking'].create({'notes': 'Second'})
        records = self.env['ems.tracking'].search([('id', 'in', [first.id, second.id])])
        self.assertEqual(records[0], second)
