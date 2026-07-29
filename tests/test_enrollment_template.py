from datetime import date

from odoo.tests.common import TransactionCase

from .common import create_level_study


class TestEnrollmentTemplate(TransactionCase):
    """sale.order.template extension (models/enrollment/enrollment_template.py):
    links an enrollment template (Pack) to a study, and feeds the auto-selection
    logic in ems.enrollment_proposal_wizard via ems_study_id/study_year — see
    docs/en/developers/enrollment/enrollment_template.md."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.level, cls.study = create_level_study(cls, 'TET', level={'name': 'Test Enrollment Template Level'}, study={
            'code': 'TET001', 'acronym': 'TETS', 'name': 'Test Enrollment Template Study',
        })
        cls.product1 = cls.env['product.template'].create({
            'name': 'Test Template Product 1', 'type': 'service',
        })
        cls.product2 = cls.env['product.template'].create({
            'name': 'Test Template Product 2', 'type': 'service',
        })

    def test_ems_level_id_derived_from_study(self):
        template = self.env['sale.order.template'].create({
            'name': 'Test Template', 'ems_study_id': self.study.id,
        })
        self.assertEqual(template.ems_level_id, self.level)

    def test_ems_level_id_follows_study_change(self):
        other_level = self.env['ems.level'].create({'acronym': 'TET2', 'name': 'Other Level'})
        other_study = self.env['ems.study'].create({
            'code': 'TET002', 'acronym': 'TETS2', 'name': 'Other Study',
            'date': date.today(), 'deprecated': False, 'level_id': other_level.id,
        })
        template = self.env['sale.order.template'].create({
            'name': 'Test Template Switch', 'ems_study_id': self.study.id,
        })
        self.assertEqual(template.ems_level_id, self.level)
        template.ems_study_id = other_study.id
        self.assertEqual(template.ems_level_id, other_level)

    def test_ems_level_id_empty_without_study(self):
        template = self.env['sale.order.template'].create({'name': 'Test Template No Study'})
        self.assertFalse(template.ems_level_id)

    def test_existing_product_ids_reflects_lines(self):
        template = self.env['sale.order.template'].create({
            'name': 'Test Template Products', 'ems_study_id': self.study.id,
            'sale_order_template_line_ids': [
                (0, 0, {'product_id': self.product1.product_variant_id.id}),
                (0, 0, {'product_id': self.product2.product_variant_id.id}),
            ],
        })
        self.assertEqual(
            template.ems_existing_product_ids,
            self.product1.product_variant_id | self.product2.product_variant_id,
        )

    def test_existing_product_ids_updates_when_line_added(self):
        template = self.env['sale.order.template'].create({
            'name': 'Test Template Incremental', 'ems_study_id': self.study.id,
            'sale_order_template_line_ids': [
                (0, 0, {'product_id': self.product1.product_variant_id.id}),
            ],
        })
        self.assertEqual(template.ems_existing_product_ids, self.product1.product_variant_id)
        template.sale_order_template_line_ids = [
            (0, 0, {'product_id': self.product2.product_variant_id.id}),
        ]
        self.assertEqual(
            template.ems_existing_product_ids,
            self.product1.product_variant_id | self.product2.product_variant_id,
        )

    def test_existing_product_ids_empty_without_lines(self):
        template = self.env['sale.order.template'].create({
            'name': 'Test Template Empty', 'ems_study_id': self.study.id,
        })
        self.assertFalse(template.ems_existing_product_ids)

    def test_study_year_stored_plain(self):
        template = self.env['sale.order.template'].create({
            'name': 'Test Template Year', 'ems_study_id': self.study.id, 'study_year': 2,
        })
        self.assertEqual(template.study_year, 2)
