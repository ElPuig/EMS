from datetime import date

from odoo.tests.common import TransactionCase

from .common import create_level_study


class TestStudy(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.test_level, cls.test_study = create_level_study(cls, 'TSTL', level={'name': 'Test Level for Study'}, study={
            'code': 'TST_STUDY_001', 'acronym': 'TSST', 'name': 'Test Study', 'date': date(2024, 9, 1),
        })

    def test_deprecated_defaults_to_false(self):
        study = self.env['ems.study'].create({
            'code': 'T01D',
            'acronym': 'T01D',
            'name': 'Test Default Deprecated',
            'date': date(2024, 9, 1),
        })
        self.assertFalse(study.deprecated)

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
