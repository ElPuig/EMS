from datetime import date

from odoo.tests.common import HttpCase, tagged
from .common import create_level_study, mock_outgoing_email, next_student_id


@tagged('post_install', '-at_install')
class TestPortalTour(HttpCase):
    """Every page-rendering portal route (controllers/portal_*.py) had zero coverage of any
    kind - not even the plain HttpCase.url_open() pattern already used for the one POST action
    route that IS tested (test_portal_enrollment.py::TestPortalEnrollmentRenewIban). These are
    genuine browser tours (not url_open) since the point is proving the page actually renders
    in a browser for a real portal user, the same bar every other EMS tour is held to."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.student = cls.env['res.partner'].create({
            'name': 'Portal Tour Student', 'contact_type': 'student', 'student_id': next_student_id(), 'birth_date': '2000-01-01',
        })
        cls.portal_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Portal Tour Student', 'login': 'test_portal_tour_student',
            'partner_id': cls.student.id,
            'groups_id': [(6, 0, [cls.env.ref('base.group_portal').id])],
        })

    def test_portal_enrollment_render_tour(self):
        self.start_tour("/my/gestion-matriculas", "ems_portal_enrollment_render",
                         login="test_portal_tour_student")

    def test_portal_confirmed_authorizations_tour(self):
        """Issue #443: an authorization sent during the school year must be answerable from
        the portal even though the enrollment of that course is already confirmed and closed
        - the page rendered for a confirmed enrollment showed no authorizations at all
        before this."""
        course = self.env['ems.course'].search([('is_enrollment_default', '=', True)], limit=1) \
            or self.env['ems.course'].create({
                'start': 2098, 'end': 2099, 'is_enrollment_default': True})
        subject = self.env['ems.subject'].create({
            'code': 'TPTSUB', 'acronym': 'TPT', 'name': 'Portal Tour Subject',
        })
        order = self.env['sale.order'].create({
            'partner_id': self.student.id, 'ems_course_id': course.id,
            'order_line': [(0, 0, {'product_id': subject.product_id.id})],
        })
        order.action_confirm()
        self.assertEqual(order.state, 'sale')
        template = self.env['ems.authorization.template'].create({
            'name': 'Portal Tour Mid-year Authorization', 'legal_text': '<p>Mid-year text</p>',
            'is_required': False, 'apply_on_enrollment': False, 'sendable_during_course': True,
        })
        self.env['ems.authorization'].create({
            'partner_id': self.student.id, 'course_id': course.id, 'template_id': template.id,
        })
        self.start_tour("/my/gestion-matriculas", "ems_portal_confirmed_authorizations",
                        login="test_portal_tour_student")

    def test_portal_documentation_render_tour(self):
        self.start_tour("/my/documentacion", "ems_portal_documentation_render",
                         login="test_portal_tour_student")

    def test_portal_comms_render_tour(self):
        self.start_tour("/my/comunicaciones", "ems_portal_comms_render",
                         login="test_portal_tour_student")

    def test_portal_account_render_tour(self):
        self.start_tour("/my/account", "ems_portal_account_render",
                         login="test_portal_tour_student")

    def test_portal_home_loads_without_console_error(self):
        """The portal home replaces native portal's document list with EMS's own cards; native
        PortalHomeCounters still runs there and removes '.o_portal_doc_spinner' once it has
        counted - with the spinner gone too, that raised a TypeError on every visit.
        browser_js fails the test on any console error."""
        self.browser_js("/my", "console.log('test successful')",
                        ready="!!document.querySelector('.o_portal_my_home')",
                        login="test_portal_tour_student")

    def test_portal_under_construction_render_tour(self):
        self.start_tour("/my/calificaciones", "ems_portal_under_construction_render",
                         login="test_portal_tour_student")

    def _confirmed_enrollment_with_paid_installment(self, with_plan=True):
        """A confirmed enrollment with its invoice issued and a settled installment.

        With `with_plan`, it is billed in two installments and the first one is settled, the way a
        portal confirmation leaves it. Without, it carries no payment plan and no payment method
        and is paid in full, the way an enrollment confirmed from the backend does.

        Mirrors what the secretary's office does: confirm, invoice, register the payment of the
        first installment. See tests/test_portal_payment_status.py for the same flow asserted at
        the model level.
        """
        mock_outgoing_email(self)
        course = self.env['ems.course'].search([('is_enrollment_default', '=', True)], limit=1) \
            or self.env['ems.course'].create({
                'start': 2097, 'end': 2098, 'is_enrollment_default': True})
        __, study = create_level_study(self, 'PPT', level={'name': 'Payment Tour Level'}, study={
            'code': 'PPT001', 'acronym': 'PPTS', 'name': 'Payment Tour Study'})
        subject = self.env['ems.subject'].create({
            'code': 'PPTSUB', 'acronym': 'PT1', 'name': 'Payment Tour Subject',
            'study_ids': [(6, 0, [study.id])]})
        fee_product = self.env['product.template'].create({
            'name': 'Payment Tour Fee', 'type': 'service', 'invoice_policy': 'order',
            'is_generic': True, 'ems_is_enrollment_fee': True,
            'list_price': 400.0, 'ems_subject_unit_cost': 100.0})
        term = self.env['account.payment.term'].create({
            'name': 'PPT two installments', 'ems_portal_visible': True, 'ems_requires_fees': True,
            'line_ids': [
                (0, 0, {'value': 'percent', 'value_amount': 50.0, 'nb_days': 0}),
                (0, 0, {'value': 'percent', 'value_amount': 50.0, 'nb_days': 60}),
            ]})
        order = self.env['sale.order'].create({
            'partner_id': self.student.id, 'ems_course_id': course.id, 'ems_study_id': study.id,
            'payment_term_id': term.id if with_plan else False})
        # Lines added after the order exists, not inline in create(): the fee line prices itself
        # from the subject lines of its own order, which are not all there yet during create().
        order.order_line = [
            (0, 0, {'product_id': subject.product_id.id}),
            (0, 0, {'product_id': fee_product.product_variant_id.id}),
        ]
        # The fee has to price before confirmation freezes the lines (see the model tests).
        self.assertTrue(order.amount_total)
        order.action_confirm()
        invoice = order._ems_generate_enrollment_invoice()
        first = invoice._ems_installment_lines()[0]
        wizard = self.env['account.payment.register'].with_context(
            active_model='account.move', active_ids=invoice.ids,
        ).create({'payment_date': date.today()})
        if with_plan:
            wizard.amount = abs(first.amount_currency)
        wizard._create_payments()
        self.assertTrue(first.reconciled)
        return order

    def test_portal_payment_status_tour(self):
        """Issue #491: paid/pending per installment, plus the payment notification, on the
        enrollment page."""
        self._confirmed_enrollment_with_paid_installment()
        self.start_tour("/my/gestion-matriculas", "ems_portal_payment_status",
                        login="test_portal_tour_student")

    def test_portal_payment_status_comms_tour(self):
        """The same notification on the Communications page, the other list it has to reach."""
        self._confirmed_enrollment_with_paid_installment()
        self.start_tour("/my/comunicaciones", "ems_portal_payment_status_comms",
                        login="test_portal_tour_student")

    def test_portal_payment_status_without_plan_tour(self):
        """Issue #491: an enrollment confirmed from the backend has no payment plan, but its
        invoice is real - 149 of the 544 confirmed enrollments of this box's database are in that
        state and used to show no payment information at all."""
        order = self._confirmed_enrollment_with_paid_installment(with_plan=False)
        self.assertFalse(order.payment_term_id)
        self.assertFalse(order.ems_payment_method)
        self.start_tour("/my/gestion-matriculas", "ems_portal_payment_status_without_plan",
                        login="test_portal_tour_student")
