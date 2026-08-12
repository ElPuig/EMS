from datetime import date

from odoo.tests.common import TransactionCase

from .common import create_level_study


class TestEnrollmentProductExtension(TransactionCase):
    """models/enrollment/enrollment_product_extension.py — ProductTemplate
    (product.template extension). ems.subject's own auto-created-product
    sync (name/code) is covered by tests/test_subject.py; this file covers
    _compute_ems_study_ids' own generic-vs-subject branching, not exercised
    there."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.level, cls.study = create_level_study(cls, 'TPE', level={'name': 'Test Product Ext Level'}, study={
            'code': 'TPE001', 'acronym': 'TPES', 'name': 'Test Product Ext Study',
        })
        cls.other_study = cls.env['ems.study'].create({
            'code': 'TPE002', 'acronym': 'TPES2', 'name': 'Other Product Ext Study',
            'date': date.today(), 'deprecated': False, 'level_id': cls.level.id,
        })

    def test_subject_product_derives_studies_from_subject(self):
        subject = self.env['ems.subject'].create({
            'code': 'TPESUB', 'acronym': 'TPS', 'name': 'Product Ext Subject',
            'study_ids': [(6, 0, [self.study.id, self.other_study.id])],
        })
        self.assertEqual(
            set(subject.product_id.product_tmpl_id.ems_study_ids.ids),
            {self.study.id, self.other_study.id},
        )

    def test_subject_product_studies_update_when_subject_studies_change(self):
        subject = self.env['ems.subject'].create({
            'code': 'TPESUB2', 'acronym': 'TPS2', 'name': 'Product Ext Subject 2',
            'study_ids': [(6, 0, [self.study.id])],
        })
        subject.write({'study_ids': [(6, 0, [self.other_study.id])]})
        self.assertEqual(subject.product_id.product_tmpl_id.ems_study_ids, self.other_study)

    def test_generic_product_studies_start_empty(self):
        product = self.env['product.template'].create({
            'name': 'Generic Product', 'type': 'service', 'is_generic': True,
        })
        self.assertFalse(product.ems_study_ids)

    def test_generic_product_manual_studies_are_not_overwritten(self):
        product = self.env['product.template'].create({
            'name': 'Generic Product Manual Studies', 'type': 'service', 'is_generic': True,
            'ems_study_ids': [(6, 0, [self.study.id])],
        })
        # Force a recompute without touching ems_study_ids directly — the
        # manual selection must survive.
        product._compute_ems_study_ids()
        self.assertEqual(product.ems_study_ids, self.study)

    def test_description_override_bug_is_fixed(self):
        """Regression test: this file used to declare
        _description = "Expand the product object with a reverse link..."
        on an _inherit-only extension of product.template, which actually
        overwrote the model's real displayed name (ir_model.name) for
        en_US — a code comment mistakenly written as a real model
        attribute. Fixed by removing the override; see
        docs/en/developers/enrollment/enrollment_product_extension.md."""
        model = self.env['ir.model'].search([('model', '=', 'product.template')], limit=1)
        self.assertNotIn('reverse link', model.name)
