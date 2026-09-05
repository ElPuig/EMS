from odoo.tests.common import HttpCase, tagged

from .common import create_level_study, force_user_language_to_english


@tagged('post_install', '-at_install')
class TestEnrollmentTour(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Course = cls.env['ems.course']
        cls.course = Course.search([('is_enrollment_default', '=', True)], limit=1) \
            or Course.create({'start': 2098, 'end': 2099, 'is_enrollment_default': True})
        cls.level, cls.study = create_level_study(
            cls, 'TENT',
            level={'name': 'Test Level (Enrollment Tour)'},
            study={'code': 'TENT001', 'name': 'Test Study (Enrollment Tour)'},
        )
        cls.fee_product = cls.env['product.template'].create({
            'name': 'Test Enrollment Tour Fee', 'type': 'service', 'invoice_policy': 'order',
            'is_generic': True, 'ems_is_enrollment_fee': True, 'list_price': 100.0,
            'ems_subject_unit_cost': 10.0, 'ems_study_ids': [(6, 0, [cls.study.id])],
        })
        cls.student = cls.env['res.partner'].create({
            'name': 'Enrollment Tour Student', 'contact_type': 'student',
        })
        cls.order = cls.env['sale.order'].create({
            'partner_id': cls.student.id, 'ems_study_id': cls.study.id,
            'ems_course_id': cls.course.id, 'shift': 'morning',
        })
        cls.order.order_line = [(0, 0, {'product_id': cls.fee_product.product_variant_id.id})]

    def test_enrollment_form_tabs_tour(self):
        force_user_language_to_english(self, self.env.ref('base.user_admin'))
        self.assertEqual(self.order.shift, 'morning')

        self.start_tour("/odoo", "ems_enrollment_form_tabs", login="admin")

        self.order.invalidate_recordset(['shift'])
        self.assertEqual(self.order.shift, 'afternoon')
