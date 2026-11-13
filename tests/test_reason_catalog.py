# -*- coding: utf-8 -*-

from odoo.tests.common import TransactionCase, tagged

# Every catalog a user picks a reason from (each with its own list: reasons are never shared
# between models) and the wizard/form field that defaults to its first reason.
REASON_CATALOGS = (
    'ems.convalidation.rejection_reason',
    'ems.convalidation.info_reason',
    'ems.strike.reason',
    'ems.attendance_justification_reason',
    'ems.student_walkout.rejection_reason',
    'ems.absence_pending.discard_reason',
)


@tagged('post_install', '-at_install')
class TestReasonCatalog(TransactionCase):
    """The reason catalogs share one shape (name, sequence, active, ordered by sequence) and the
    default reason of the dialogs that pick from them (the first active one by its own order)."""

    def test_every_catalog_shares_the_shape(self):
        for name in REASON_CATALOGS:
            with self.subTest(catalog=name):
                model = self.env[name]
                self.assertEqual(model._order, 'sequence, name')
                self.assertTrue(model._fields['name'].translate)
                self.assertTrue(model._fields['name'].required)
                self.assertEqual(model._fields['sequence'].default(model), 10)
                self.assertTrue(model._fields['active'].default(model))

    def test_default_reason_is_the_first_active_one_by_its_own_order(self):
        for name in REASON_CATALOGS:
            with self.subTest(catalog=name):
                model = self.env[name]
                model.search([]).write({'active': False})
                late = model.create({'name': 'Zz late', 'sequence': 90})
                first = model.create({'name': 'Zz first', 'sequence': 1})
                archived = model.create({'name': 'Zz archived', 'sequence': 0, 'active': False})
                self.assertEqual(model.default_reason(), first)
                first.active = False
                self.assertEqual(model.default_reason(), late)
                self.assertNotEqual(model.default_reason(), archived)
