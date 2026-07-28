from datetime import date

from odoo.exceptions import ValidationError
from odoo.tests import Form
from odoo.tests.common import TransactionCase


class TestEnrollmentLine(TransactionCase):
    """models/enrollment/enrollment_line_extension.py — SaleOrderLine.

    The benefit-driven branches of _compute_price_unit/_compute_discount
    (bonification/exemption, frozen-on-confirm) are already thoroughly
    covered by tests/test_enrollment_benefit.py — not duplicated here. This
    file covers what that one doesn't: the base unit-cost/list-price fee
    calculation, the duplicate-item guards (constraint + onchange), and the
    forced quantity-of-1 onchange.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Course = cls.env['ems.course']
        cls.course = Course.search([('is_enrollment_default', '=', True)], limit=1) \
            or Course.create({'start': 2098, 'end': 2099, 'is_enrollment_default': True})
        cls.level = cls.env['ems.level'].create({'acronym': 'TEL', 'name': 'Test Enrollment Line Level'})
        cls.study = cls.env['ems.study'].create({
            'code': 'TEL001', 'acronym': 'TELS', 'name': 'Test Enrollment Line Study',
            'date': date.today(), 'deprecated': False, 'level_id': cls.level.id,
        })
        cls.subject1 = cls.env['ems.subject'].create({
            'code': 'TELSUB1', 'acronym': 'TL1', 'name': 'Test Line Subject 1',
            'study_ids': [(6, 0, [cls.study.id])],
        })
        cls.subject2 = cls.env['ems.subject'].create({
            'code': 'TELSUB2', 'acronym': 'TL2', 'name': 'Test Line Subject 2',
            'study_ids': [(6, 0, [cls.study.id])],
        })
        cls.fee_product = cls.env['product.template'].create({
            'name': 'Test Line Enrollment Fee', 'type': 'service', 'invoice_policy': 'order',
            'is_generic': True, 'ems_is_enrollment_fee': True,
            'list_price': 40.0, 'ems_subject_unit_cost': 25.0,
        })
        cls.student = cls.env['res.partner'].create({'name': 'Line Test Student', 'contact_type': 'student'})

    def _order(self):
        return self.env['sale.order'].create({
            'partner_id': self.student.id, 'ems_study_id': self.study.id, 'ems_course_id': self.course.id,
        })

    def _fee_line(self, order):
        return order.order_line.filtered(lambda l: l.product_template_id == self.fee_product)

    # --- fee price_unit: subject count x unit cost, capped at list price ------------

    def test_fee_price_below_cap(self):
        order = self._order()
        order.order_line = [
            (0, 0, {'product_id': self.subject1.product_id.id}),
            (0, 0, {'product_id': self.fee_product.product_variant_id.id}),
        ]
        # 1 subject x 25.0 = 25.0, below the 40.0 list-price cap.
        self.assertEqual(self._fee_line(order).price_unit, 25.0)

    def test_fee_price_capped_at_list_price(self):
        order = self._order()
        order.order_line = [
            (0, 0, {'product_id': self.subject1.product_id.id}),
            (0, 0, {'product_id': self.subject2.product_id.id}),
            (0, 0, {'product_id': self.fee_product.product_variant_id.id}),
        ]
        # 2 subjects x 25.0 = 50.0, above the 40.0 list-price cap.
        self.assertEqual(self._fee_line(order).price_unit, 40.0)

    def test_fee_line_name_includes_subject_count(self):
        order = self._order()
        order.order_line = [
            (0, 0, {'product_id': self.subject1.product_id.id}),
            (0, 0, {'product_id': self.fee_product.product_variant_id.id}),
        ]
        # name is set as a side effect inside _compute_price_unit, not its
        # own tracked @api.depends field — within a single transaction it can
        # read stale (from an earlier, premature pass during the batch
        # sibling-line creation) unless price_unit's own recompute has
        # already settled. flush_all() forces that settling, matching what
        # any fresh transaction/request would always see. See
        # docs/en/developers/enrollment/enrollment_line.md, "Known gap".
        self.env.flush_all()
        self.assertIn('1 Subjects', self._fee_line(order).name)

    def test_non_fee_line_price_untouched_by_fee_logic(self):
        self.subject1.product_id.product_tmpl_id.list_price = 99.0
        order = self._order()
        order.order_line = [(0, 0, {'product_id': self.subject1.product_id.id})]
        # Not an enrollment-fee product: the fee-calculation branch never
        # runs, so price_unit is whatever the native pricing logic set.
        self.assertEqual(order.order_line.price_unit, 99.0)

    # --- duplicate item guards ------------------------------------------------------

    def test_constraint_blocks_duplicate_product_on_same_order(self):
        order = self._order()
        order.order_line = [(0, 0, {'product_id': self.subject1.product_id.id})]
        with self.assertRaises(ValidationError):
            order.order_line = [(0, 0, {'product_id': self.subject1.product_id.id})]

    def test_onchange_clears_duplicate_product_selection(self):
        order = self._order()
        order.shift = 'morning'
        order.order_line = [(0, 0, {'product_id': self.subject1.product_id.id})]
        form = Form(order)
        with form.order_line.new() as line:
            line.product_id = self.subject1.product_id
            self.assertFalse(line.product_id)
            # A required field can't be left empty when the line sub-form
            # closes — complete a realistic flow: pick a different product.
            line.product_id = self.subject2.product_id
        form.save()
        self.assertIn(self.subject2.product_id, order.order_line.mapped('product_id'))

    # --- forced quantity of 1 ---------------------------------------------------------

    def test_onchange_forces_quantity_to_one(self):
        order = self._order()
        form = Form(order)
        with form.order_line.new() as line:
            line.product_id = self.subject1.product_id
            line.product_uom_qty = 3.0
            self.assertEqual(line.product_uom_qty, 1.0)

    # --- ems_is_tutoria related field --------------------------------------------------

    def test_ems_is_tutoria_mirrors_product(self):
        tutoria_subject = self.env['ems.subject'].create({
            'code': 'TELTUT', 'acronym': 'TUT', 'name': 'Tutoria Line Subject',
            'study_ids': [(6, 0, [self.study.id])],
        })
        tutoria_subject.product_id.ems_is_tutoria = True
        order = self._order()
        order.order_line = [(0, 0, {'product_id': tutoria_subject.product_id.id})]
        self.assertTrue(order.order_line.ems_is_tutoria)
