from datetime import date

from psycopg2 import IntegrityError

from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase

from .common import create_level_study, mock_outgoing_email


class TestEnrollmentHeader(TransactionCase):
    """models/enrollment/enrollment.py — the sale.order extension that IS the
    enrollment header. Not to be confused with ems.enrollment (models/contacts/
    enrollment.py), the student x group x subject junction row, already DTON'd
    in Phase 5. See docs/en/developers/enrollment/enrollment.md.

    Admission/placement (_ems_admit_student, _ems_suggest_group,
    _ems_apply_destination_placement) is already covered by
    tests/test_enrollment_placement.py; billing (_ems_generate_enrollment_invoice,
    action_ems_reapply_benefits) by tests/test_enrollment_benefit.py — neither is
    duplicated here. This file covers what neither of those touch: naming,
    the unique-enrollment-per-course constraint, fee/installment computes, the
    tutor-blocking guards on every state-changing action, the required-
    authorization gate on confirm, and apply_authorizations/_get_authorization_commands.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # action_send_enrollment_proposal() sends a real email (force_send=True).
        mock_outgoing_email(cls)

        Course = cls.env['ems.course']
        cls.course = Course.search([('is_enrollment_default', '=', True)], limit=1) \
            or Course.create({'start': 2098, 'end': 2099, 'is_enrollment_default': True})
        cls.level, cls.study = create_level_study(cls, 'TEH', level={'name': 'Test Enrollment Header Level'}, study={
            'code': 'TEH001', 'acronym': 'TEHS', 'name': 'Test Enrollment Header Study',
        })
        cls.other_study = cls.env['ems.study'].create({
            'code': 'TEH002', 'acronym': 'TEHS2', 'name': 'Other Study',
            'date': date.today(), 'deprecated': False, 'level_id': cls.level.id,
        })
        cls.fee_product = cls.env['product.template'].create({
            'name': 'Test Header Enrollment Fee', 'type': 'service',
            'invoice_policy': 'order', 'is_generic': True,
            'ems_is_enrollment_fee': True, 'list_price': 400.0, 'ems_subject_unit_cost': 25.0,
        })
        cls.subject = cls.env['ems.subject'].create({
            'code': 'TEHSUB', 'acronym': 'THS', 'name': 'Test Header Subject',
            'study_ids': [(6, 0, [cls.study.id])],
        })
        cls.student = cls.env['res.partner'].create({
            'name': 'Header Test Student', 'contact_type': 'student'})
        cls.other_student = cls.env['res.partner'].create({
            'name': 'Other Header Test Student', 'contact_type': 'student'})

        cls.tutor_user = cls.env['res.users'].create({
            'name': 'Header Tutor', 'login': 'header_tutor_teh',
            'groups_id': [
                (4, cls.env.ref('base.group_user').id),
                (4, cls.env.ref('ems.group_teacher').id),
                (4, cls.env.ref('ems.group_tutor').id),
            ],
        })
        # rule_sale_order_tutor (security/rules/contacts.xml) only grants write
        # access where partner_id.tutor_id.user_id = user.id, and
        # res.partner.tutor_id is related to main_group_id.tutor_id (an
        # hr.employee) — so being in ems.group_tutor alone is not enough, the
        # tutor also needs to actually BE the student's group tutor.
        cls.tutor_employee = cls.env['hr.employee'].create({
            'name': 'Header Tutor', 'user_id': cls.tutor_user.id, 'employee_type': 'teacher',
        })
        cls.tutor_group = cls.env['ems.group'].create({
            'course': 1, 'acronym': 'THG', 'shift': 'morning',
            'level_id': cls.level.id, 'study_id': cls.study.id, 'tutor_id': cls.tutor_employee.id,
        })
        cls.plain_teacher_user = cls.env['res.users'].create({
            'name': 'Header Plain Teacher', 'login': 'header_teacher_teh',
            'groups_id': [(4, cls.env.ref('base.group_user').id), (4, cls.env.ref('ems.group_teacher').id)],
        })
        cls.secretary_user = cls.env['res.users'].create({
            'name': 'Header Secretary', 'login': 'header_secretary_teh',
            'groups_id': [(4, cls.env.ref('base.group_user').id), (4, cls.env.ref('ems.group_secretary').id)],
        })

    def _order(self, partner=None, **vals):
        base = {
            'partner_id': (partner or self.student).id,
            'ems_study_id': self.study.id,
            'ems_course_id': self.course.id,
        }
        base.update(vals)
        return self.env['sale.order'].create(base)

    # --- naming --------------------------------------------------------------

    def test_create_assigns_enrollment_number_and_dynamic_name(self):
        order = self._order()
        self.assertTrue(order.ems_enrollment_number)
        self.assertIn(order.ems_enrollment_number, order.name)
        self.assertIn(self.study.acronym, order.name)
        self.assertIn(self.level.acronym, order.name)
        self.assertTrue(order.name.startswith('M/'))

    def test_create_without_study_uses_native_sequence(self):
        # No ems_study_id: this is a plain (non-enrollment) sale order, left
        # to Odoo's own native sequence — never touched by our override.
        order = self.env['sale.order'].create({'partner_id': self.student.id})
        self.assertFalse(order.ems_enrollment_number)
        self.assertNotIn('/', order.name)

    def test_write_refreshes_name_when_study_changes_in_draft(self):
        order = self._order()
        old_name = order.name
        order.write({'ems_study_id': self.other_study.id})
        self.assertNotEqual(order.name, old_name)
        self.assertIn(self.other_study.acronym, order.name)

    def test_write_does_not_refresh_name_once_confirmed(self):
        order = self._order()
        order.order_line = [(0, 0, {'product_id': self.subject.product_id.id})]
        order.action_confirm()
        name_after_confirm = order.name
        # Bypass the tutor-blocking action override entirely: write ems_study_id
        # directly to isolate the write()-level name-refresh guard from the
        # action-level state-transition guards tested separately below.
        order.write({'ems_study_id': self.other_study.id})
        self.assertEqual(order.name, name_after_confirm)

    # --- unique enrollment per course ------------------------------------------

    def test_second_active_enrollment_same_course_raises(self):
        self._order()
        with self.assertRaises(ValidationError):
            self._order()

    def test_cancelled_enrollment_does_not_block_a_new_one(self):
        first = self._order()
        first.action_cancel()
        # The new partial unique index (see the "DB-level backstop" tests below) is
        # enforced by PostgreSQL directly, which only sees flushed writes - unlike the
        # @api.constrains check above, which always flushes before its own search().
        # Real usage never hits this (a cancel and a later create are always separate
        # requests/transactions, already fully flushed and committed by then).
        self.env.flush_all()
        second = self._order()
        self.assertTrue(second.id)

    def test_same_student_different_course_is_allowed(self):
        self._order()
        other_course = self.env['ems.course'].create({'start': 2050, 'end': 2051})
        second = self._order(ems_course_id=other_course.id)
        self.assertTrue(second.id)

    def test_different_students_same_course_is_allowed(self):
        self._order()
        second = self._order(partner=self.other_student)
        self.assertTrue(second.id)

    # --- unique enrollment per course: DB-level backstop (race condition) -------------
    # The @api.constrains above is a search()-then-raise check, not a DB constraint - two
    # concurrent transactions could each pass it before either commits (see
    # plans/enrollment_header_unique_race_condition.md, now resolved). A partial unique
    # index (created in SaleOrder.init(), since a plain _sql_constraints unique can't
    # express "unique except when cancelled") backstops it at the DB level.

    def test_unique_enrollment_index_exists(self):
        self.env.cr.execute(
            "SELECT indexdef FROM pg_indexes WHERE indexname = 'sale_order_unique_enrollment_per_course'")
        row = self.env.cr.fetchone()
        self.assertTrue(row, "partial unique index must exist on sale_order")
        self.assertIn('UNIQUE', row[0])
        self.assertIn('WHERE', row[0])

    def _raw_insert_order(self, order, name, state='draft'):
        self.env.cr.execute(
            "INSERT INTO sale_order "
            "(company_id, partner_id, partner_invoice_id, partner_shipping_id, "
            " ems_course_id, state, name, date_order) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, now())",
            (order.company_id.id, order.partner_id.id, order.partner_id.id,
             order.partner_id.id, order.ems_course_id.id, state, name))

    def test_unique_enrollment_index_rejects_raw_duplicate_at_db_level(self):
        # Raw SQL bypasses the ORM entirely (including the @api.constrains above), so this
        # proves the DB-level index itself enforces uniqueness, independent of the Python
        # check - i.e. the actual backstop the race condition needs.
        order = self._order()
        with self.assertRaises(Exception):
            self._raw_insert_order(order, 'Raw Duplicate')

    def test_unique_enrollment_index_allows_raw_duplicate_when_cancelled(self):
        order = self._order()
        order.action_cancel()
        # Raw SQL only sees flushed writes - see test_cancelled_enrollment_does_not_block_a_new_one.
        self.env.flush_all()
        # No exception: a cancelled order never counts toward the partial index's WHERE
        # clause, exactly like the Python constraint's own skip condition.
        self._raw_insert_order(order, 'Raw Non-Duplicate')

    def test_translate_enrollment_race_error_matching_index_raises_validation_error(self):
        # A genuine cross-transaction race can't be reproduced inside a single
        # TransactionCase (fixtures are never actually committed - see
        # docs/en/developers/shared/multithreading.md for the same limitation elsewhere in
        # this codebase), so this tests _translate_enrollment_race_error() directly rather
        # than mocking deep into Odoo's create()/super() chain to simulate one end-to-end.
        error = IntegrityError(
            'duplicate key value violates unique constraint '
            '"sale_order_unique_enrollment_per_course"')
        with self.assertRaises(ValidationError):
            self.env['sale.order']._translate_enrollment_race_error(error)

    def test_translate_enrollment_race_error_other_constraint_reraises_unchanged(self):
        error = IntegrityError('duplicate key value violates unique constraint "some_other_constraint"')
        with self.assertRaises(IntegrityError):
            self.env['sale.order']._translate_enrollment_race_error(error)

    # --- group/study consistency ------------------------------------------------

    def test_group_from_another_study_raises(self):
        # ems_group_id.study_id must match ems_study_id - the onchange only
        # enforces this client-side (test_onchange_study_clears_mismatched_group
        # above), so a direct write (e.g. a tutor editing the form directly
        # instead of going through ems.enrollment_proposal_wizard) must be
        # blocked server-side too. See plans/enrollment_header_tutor_guard_gap.md.
        other_group = self.env['ems.group'].create({
            'course': 1, 'acronym': 'OG', 'level_id': self.level.id,
            'study_id': self.other_study.id,
        })
        order = self._order()
        with self.assertRaises(ValidationError):
            order.write({'ems_group_id': other_group.id})

    def test_group_from_same_study_is_allowed(self):
        order = self._order()
        order.write({'ems_group_id': self.tutor_group.id})
        self.assertEqual(order.ems_group_id, self.tutor_group)

    def test_clearing_group_is_allowed(self):
        order = self._order(ems_group_id=self.tutor_group.id)
        order.write({'ems_group_id': False})
        self.assertFalse(order.ems_group_id)

    def test_group_without_study_raises(self):
        # A destination group always implies a study - every real writer of
        # ems_group_id (the enrollment proposal wizard, _ems_suggest_group) sets or
        # requires ems_study_id too, and the view marks it required="1". Confirmed via
        # a code audit (2026-07-30) that no real path leaves ems_group_id set while
        # ems_study_id is empty - only a direct ORM bypass like this test can.
        with self.assertRaises(ValidationError):
            self.env['sale.order'].create({
                'partner_id': self.student.id, 'ems_course_id': self.course.id,
                'ems_group_id': self.tutor_group.id,
            })

    # --- fee / installment computes --------------------------------------------

    def test_fee_and_installment_computes(self):
        order = self._order()
        order.order_line = [
            (0, 0, {'product_id': self.subject.product_id.id}),
            (0, 0, {'product_id': self.fee_product.product_variant_id.id}),
        ]
        fee_line = order.order_line.filtered(
            lambda l: l.product_template_id.ems_is_enrollment_fee)
        non_fee_line = order.order_line - fee_line
        self.assertTrue(order.ems_has_fees)
        self.assertEqual(order.ems_fee_amount, fee_line.price_subtotal)
        self.assertEqual(order.ems_non_fee_amount, non_fee_line.price_subtotal)
        self.assertEqual(
            order.ems_first_installment,
            order.ems_non_fee_amount + order.ems_fee_amount * 0.5)
        self.assertEqual(order.ems_second_installment, order.ems_fee_amount * 0.5)

    def test_no_fee_products_has_fees_false(self):
        order = self._order()
        order.order_line = [(0, 0, {'product_id': self.subject.product_id.id})]
        self.assertFalse(order.ems_has_fees)
        self.assertEqual(order.ems_fee_amount, 0)

    # --- tutor-blocking guards ---------------------------------------------------

    def test_plain_teacher_cannot_cancel(self):
        order = self._order()
        with self.assertRaises(ValidationError):
            order.with_user(self.plain_teacher_user).action_cancel()

    def test_plain_teacher_cannot_confirm(self):
        order = self._order()
        with self.assertRaises(ValidationError):
            order.with_user(self.plain_teacher_user).action_confirm()

    def test_plain_teacher_cannot_mark_sent(self):
        order = self._order()
        with self.assertRaises(ValidationError):
            order.with_user(self.plain_teacher_user).action_quotation_sent()

    def test_tutor_can_cancel(self):
        # rule_sale_order_tutor only grants access where the order's student
        # is actually tutored by this user (see tutor_group/tutor_employee
        # setup in setUpClass) — a plain ems.group_tutor membership is not
        # enough on its own.
        tutored_student = self.env['res.partner'].create({
            'name': 'Tutored Student', 'contact_type': 'student',
            'main_group_id': self.tutor_group.id,
        })
        order = self._order(partner=tutored_student)
        order.with_user(self.tutor_user).action_cancel()
        self.assertEqual(order.state, 'cancel')

    def test_tutor_can_confirm_own_tutored_student(self):
        tutored_student = self.env['res.partner'].create({
            'name': 'Tutored Confirm Student', 'contact_type': 'student',
            'main_group_id': self.tutor_group.id,
        })
        order = self._order(partner=tutored_student)
        order.order_line = [(0, 0, {'product_id': self.subject.product_id.id})]
        order.with_user(self.tutor_user).action_confirm()
        self.assertEqual(order.state, 'sale')

    def test_tutor_of_a_different_student_gets_friendly_error(self):
        # self.student (setUpClass) is not tutored by self.tutor_user - see
        # plans/enrollment_header_tutor_guard_gap.md. Without the has_access()
        # check, this used to fall through to a bare AccessError from
        # rule_sale_order_tutor instead of the same friendly ValidationError a
        # plain teacher gets.
        order = self._order()
        with self.assertRaises(ValidationError):
            order.with_user(self.tutor_user).action_cancel()

    def test_secretary_can_confirm(self):
        order = self._order()
        order.order_line = [(0, 0, {'product_id': self.subject.product_id.id})]
        order.with_user(self.secretary_user).action_confirm()
        self.assertEqual(order.state, 'sale')

    # --- action_confirm: required-authorization gate ----------------------------

    def test_confirm_blocked_by_pending_required_authorization(self):
        template = self.env['ems.authorization.template'].create({
            'name': 'Required Auth', 'legal_text': '<p>Text</p>', 'is_required': True,
        })
        order = self._order()
        order.order_line = [(0, 0, {'product_id': self.subject.product_id.id})]
        order.ems_authorization_ids = [(0, 0, {'template_id': template.id, 'status': 'pending'})]
        with self.assertRaises(ValidationError):
            order.action_confirm()

    def test_confirm_allowed_when_required_authorization_answered(self):
        template = self.env['ems.authorization.template'].create({
            'name': 'Required Auth Answered', 'legal_text': '<p>Text</p>', 'is_required': True,
        })
        order = self._order()
        order.order_line = [(0, 0, {'product_id': self.subject.product_id.id})]
        order.ems_authorization_ids = [(0, 0, {'template_id': template.id, 'status': 'yes'})]
        order.action_confirm()
        self.assertEqual(order.state, 'sale')

    def test_confirm_allowed_when_pending_authorization_not_required(self):
        template = self.env['ems.authorization.template'].create({
            'name': 'Optional Auth', 'legal_text': '<p>Text</p>', 'is_required': False,
        })
        order = self._order()
        order.order_line = [(0, 0, {'product_id': self.subject.product_id.id})]
        order.ems_authorization_ids = [(0, 0, {'template_id': template.id, 'status': 'pending'})]
        order.action_confirm()
        self.assertEqual(order.state, 'sale')

    # --- authorization sync ------------------------------------------------------

    def test_apply_authorizations_adds_matching_template(self):
        template = self.env['ems.authorization.template'].create({
            'name': 'Level Auth', 'legal_text': '<p>Text</p>',
            'ems_level_ids': [(6, 0, [self.level.id])],
        })
        order = self._order()
        order.apply_authorizations()
        self.assertIn(template, order.ems_authorization_ids.mapped('template_id'))

    def test_apply_authorizations_removes_stale_template(self):
        template = self.env['ems.authorization.template'].create({
            'name': 'Study Auth', 'legal_text': '<p>Text</p>',
            'ems_study_ids': [(6, 0, [self.study.id])],
        })
        order = self._order()
        order.apply_authorizations()
        self.assertIn(template, order.ems_authorization_ids.mapped('template_id'))
        order.ems_study_id = self.other_study.id
        order.apply_authorizations()
        self.assertNotIn(template, order.ems_authorization_ids.mapped('template_id'))

    def test_get_authorization_commands_empty_without_match(self):
        self.env['ems.authorization.template'].create({
            'name': 'Unrelated Auth', 'legal_text': '<p>Text</p>',
            'ems_study_ids': [(6, 0, [self.other_study.id])],
        })
        order = self._order()
        self.assertFalse(order._get_authorization_commands())

    def test_get_authorization_commands_with_both_level_and_study_requires_both(self):
        # Same AND-of-scopes rule as
        # test_authorization.py::test_create_with_both_level_and_study_requires_both_to_match
        # - both sides of the scoping must now agree (see
        # docs/en/developers/enrollment/authorization.md).
        template = self.env['ems.authorization.template'].create({
            'name': 'Level+Study Auth', 'legal_text': '<p>Text</p>',
            'ems_level_ids': [(6, 0, [self.level.id])],
            'ems_study_ids': [(6, 0, [self.study.id])],
        })
        # order's level matches (self.other_study shares self.level) but its
        # study doesn't -> AND semantics means no match.
        order = self._order(ems_study_id=self.other_study.id)
        self.assertFalse(order._get_authorization_commands())

        order.ems_study_id = self.study.id
        order.apply_authorizations()
        self.assertIn(template, order.ems_authorization_ids.mapped('template_id'))

    # --- action_send_enrollment_proposal ------------------------------------------

    def test_send_enrollment_proposal_marks_drafts_sent(self):
        order = self._order()
        order.with_user(self.secretary_user).action_send_enrollment_proposal()
        self.assertEqual(order.state, 'sent')

    def test_send_enrollment_proposal_blocks_plain_teacher(self):
        order = self._order()
        with self.assertRaises(ValidationError):
            order.with_user(self.plain_teacher_user).action_send_enrollment_proposal()

    def test_send_enrollment_proposal_empty_selection_raises(self):
        empty = self.env['sale.order']
        with self.assertRaises(UserError):
            empty.action_send_enrollment_proposal()

    # --- onchange warnings ---------------------------------------------------------

    def test_onchange_group_shift_mismatch_warns(self):
        group = self.env['ems.group'].create({
            'course': 1, 'acronym': 'A', 'shift': 'afternoon',
            'level_id': self.level.id, 'study_id': self.study.id,
        })
        order = self.env['sale.order'].new({
            'partner_id': self.student.id, 'ems_study_id': self.study.id,
            'shift': 'morning', 'ems_group_id': group.id,
        })
        result = order._onchange_ems_group_id()
        self.assertIn('warning', result)

    def test_onchange_study_clears_mismatched_group(self):
        group = self.env['ems.group'].create({
            'course': 1, 'acronym': 'B', 'level_id': self.level.id, 'study_id': self.study.id,
        })
        order = self.env['sale.order'].new({
            'partner_id': self.student.id, 'ems_study_id': self.study.id,
            'ems_group_id': group.id,
        })
        order.ems_study_id = self.other_study.id
        order._onchange_ems_study_id()
        self.assertFalse(order.ems_group_id)
