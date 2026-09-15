from odoo.tests.common import HttpCase, tagged
from .common import next_student_id


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
            'name': 'Portal Tour Student', 'contact_type': 'student', 'student_id': next_student_id(),
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

    def test_portal_under_construction_render_tour(self):
        self.start_tour("/my/calificaciones", "ems_portal_under_construction_render",
                         login="test_portal_tour_student")
