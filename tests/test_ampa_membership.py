from datetime import date

from odoo.tests.common import TransactionCase

from .common import (
    create_head_of_studies_branch, create_level_study_group, create_role_employee, create_role_user,
    mock_outgoing_email, next_student_id,
)


class AmpaMembershipFixtures:
    """Shared by the backend tests and the tour: a tutor with a member and a non-member in their
    group, another tutor's group with a member, and the chiefs above the first tutor."""

    @classmethod
    def _setup_ampa_fixtures(cls):
        cls.mail_transport = mock_outgoing_email(cls)
        Partner = cls.env['res.partner']
        cls.course = Partner._ems_running_course()
        cls.other_course = cls.env['ems.course'].search([('start', '=', 2098)], limit=1) \
            or cls.env['ems.course'].create({'start': 2098, 'end': 2099})

        cls.tutor = create_role_user(cls, 'tutor', 'test_ampa_tutor', name='AMPA Tutor')
        cls.tutor_employee = create_role_employee(cls, cls.tutor)
        create_head_of_studies_branch(cls, 'AMPA', cls.tutor_employee)
        cls.other_tutor = create_role_user(cls, 'tutor', 'test_ampa_other_tutor', name='AMPA Other Tutor')
        other_tutor_employee = create_role_employee(cls, cls.other_tutor)
        cls.secretary = create_role_user(cls, 'secretary', 'test_ampa_secretary')
        cls.academic_admin = create_role_user(cls, 'academic_admin', 'test_ampa_admin')
        cls.teacher = create_role_user(cls, 'teacher', 'test_ampa_teacher')

        cls.level, cls.study, cls.group = create_level_study_group(
            cls, 'AMPT', group={'tutor_id': cls.tutor_employee.id})
        cls.other_group = cls.env['ems.group'].create({
            'course': 1, 'acronym': 'B', 'level_id': cls.level.id, 'study_id': cls.study.id,
            'tutor_id': other_tutor_employee.id})
        cls.subject = cls.env['ems.subject'].create({
            'code': 'AMPTSUB', 'acronym': 'AM1', 'name': 'AMPA Subject',
            'study_ids': [(6, 0, [cls.study.id])]})
        cls.fee_product = cls.env['product.template'].create({
            'name': 'AMPA Test Fee', 'type': 'service', 'invoice_policy': 'order',
            'is_generic': True, 'ems_is_enrollment_fee': True,
            'list_price': 400.0, 'ems_subject_unit_cost': 100.0,
        })
        cls.ampa_product = cls.env.ref('ems.product_generic_ampa').product_variant_id
        cls.deferred_term = cls.env['account.payment.term'].create({
            'name': 'AMPA two installments', 'ems_portal_visible': True, 'ems_requires_fees': True,
            'line_ids': [
                (0, 0, {'value': 'percent', 'value_amount': 50.0, 'nb_days': 0}),
                (0, 0, {'value': 'percent', 'value_amount': 50.0, 'nb_days': 60}),
            ],
        })
        cls.member = cls._student('Ampatest Socia', cls.group)
        cls.non_member = cls._student('Ampatest Nosocia', cls.group)
        cls.other_group_member = cls._student('Ampatest Altra', cls.other_group)
        for student in (cls.member, cls.other_group_member):
            cls._pay(cls._order(student))

    @classmethod
    def _student(cls, name, group):
        return cls.env['res.partner'].create({
            'name': name, 'contact_type': 'student', 'student_id': next_student_id(),
            'main_group_id': group.id})

    @classmethod
    def _order(cls, student, ampa=True, course=None, payment_term=None, invoice=True):
        order = cls.env['sale.order'].create({
            'partner_id': student.id,
            'ems_study_id': cls.study.id,
            'ems_course_id': (course or cls.course).id,
            'shift': 'morning',
            'payment_term_id': payment_term.id if payment_term else False,
        })
        lines = [(0, 0, {'product_id': cls.subject.product_id.id}),
                 (0, 0, {'product_id': cls.fee_product.product_variant_id.id})]
        if ampa:
            lines.append((0, 0, {'product_id': cls.ampa_product.id}))
        order.order_line = lines
        # Priced before confirming: a confirmed order freezes its lines (see #491's tests).
        cls.env.flush_all()
        order.write({'state': 'sale'})
        if invoice:
            order._ems_generate_enrollment_invoice()
        return order

    @classmethod
    def _pay(cls, order, amount=None):
        invoice = order._ems_enrollment_invoice()
        wizard = cls.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=invoice.ids,
        ).create({'payment_date': date.today()})
        if amount is not None:
            wizard.amount = amount
        return wizard._create_payments()


class TestAmpaMembership(AmpaMembershipFixtures, TransactionCase):
    """Issue #820: tutors and the chiefs above them see which of their students are AMPA members.

    A student is a member when their confirmed enrollment of the running course carries the
    "Quota AMPA" line and the first installment of its invoice (the one the fee is billed in) is
    collected; a sibling (a student sharing a family contact) of a member is a member too.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_ampa_fixtures()

    def _status(self, student, user=None):
        student.invalidate_recordset(['ems_ampa_member'])
        return student.with_user(user or self.secretary).ems_ampa_member

    def _search(self, user, value):
        return self.env['res.partner'].with_user(user).search(
            [('ems_ampa_member', '=', value), ('main_group_id', 'in', (self.group | self.other_group).ids)])

    # --- what makes a student a member ---------------------------------------------

    def test_member_once_the_invoice_is_collected(self):
        student = self._student('AMPA Pending', self.group)
        order = self._order(student)
        self.assertEqual(self._status(student), 'no', "an unpaid AMPA fee is not a membership")
        self._pay(order)
        self.assertTrue(order.ems_ampa_paid)
        self.assertEqual(self._status(student), 'yes')
        self.assertEqual(self._status(self.member), 'yes')

    def test_first_installment_is_enough(self):
        # The AMPA fee is billed in the first installment, with the non-fee items.
        student = self._student('AMPA Deferred', self.group)
        order = self._order(student, payment_term=self.deferred_term)
        invoice = order._ems_enrollment_invoice()
        first = invoice._ems_installment_lines()[0]
        self._pay(order, amount=abs(first.amount_currency))
        self.assertEqual(invoice.payment_state, 'partial')
        self.assertEqual(self._status(student), 'yes')

    def test_unreconciling_the_payment_withdraws_the_membership(self):
        student = self._student('AMPA Reverted', self.group)
        order = self._order(student)
        payment = self._pay(order)
        self.assertEqual(self._status(student), 'yes')
        payment.move_id.line_ids.remove_move_reconcile()
        self.assertFalse(order.ems_ampa_paid)
        self.assertEqual(self._status(student), 'no')

    def test_paid_enrollment_without_the_ampa_line_is_not_a_membership(self):
        student = self._student('AMPA Not Joined', self.group)
        self._pay(self._order(student, ampa=False))
        self.assertEqual(self._status(student), 'no')

    def test_enrollment_without_invoice_is_not_a_membership(self):
        student = self._student('AMPA No Invoice', self.group)
        self._order(student, invoice=False)
        self.assertEqual(self._status(student), 'no')

    def test_another_course_does_not_count(self):
        student = self._student('AMPA Other Course', self.group)
        self._pay(self._order(student, course=self.other_course))
        self.assertEqual(self._status(student), 'no')

    def test_a_member_sibling_makes_the_student_a_member(self):
        family = self.env['res.partner'].create({'name': 'AMPA Family', 'contact_type': 'family'})
        sibling = self._student('AMPA Sibling', self.group)
        father = self.env.ref('ems.relation_type_father')
        self.member._ems_link_family(family, father)
        self.assertEqual(self._status(sibling), 'no')
        sibling._ems_link_family(family, father)
        self.assertEqual(self._status(sibling), 'yes')
        self.assertIn(sibling, self._search(self.tutor, 'yes'))

    # --- who sees it ---------------------------------------------------------------

    def test_tutor_and_the_hierarchy_above_see_it(self):
        director = create_role_user(self, 'director', 'test_ampa_director')
        self.env.company.director_id = create_role_employee(self, director)
        for user in (self.tutor, self.department_chief, self.head_of_studies, director,
                     self.secretary, self.academic_admin):
            self.assertEqual(self._status(self.member, user), 'yes', user.name)
            self.assertEqual(self._status(self.non_member, user), 'no', user.name)

    def test_outside_the_hierarchy_it_stays_empty(self):
        for user in (self.other_tutor, self.other_department_chief, self.other_head_of_studies):
            self.assertFalse(self._status(self.member, user), user.name)
            self.assertFalse(self._status(self.non_member, user), user.name)

    def test_a_plain_teacher_does_not_get_the_field(self):
        self.assertNotIn('ems_ampa_member', self.env['res.partner'].with_user(self.teacher).fields_get())

    # --- filters ---------------------------------------------------------------------

    def test_filters_list_members_and_non_members_within_the_scope(self):
        self.assertEqual(self._search(self.tutor, 'yes'), self.member)
        self.assertEqual(self._search(self.tutor, 'no'), self.non_member)
        self.assertEqual(self._search(self.secretary, 'yes'), self.member | self.other_group_member)
        self.assertEqual(self._search(self.other_tutor, 'no'), self.env['res.partner'])
