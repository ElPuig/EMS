from odoo.tests.common import HttpCase, tagged


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
            'name': 'Portal Tour Student', 'contact_type': 'student',
        })
        cls.portal_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Portal Tour Student', 'login': 'test_portal_tour_student',
            'partner_id': cls.student.id,
            'groups_id': [(6, 0, [cls.env.ref('base.group_portal').id])],
        })

    def test_portal_enrollment_render_tour(self):
        self.start_tour("/my/gestion-matriculas", "ems_portal_enrollment_render",
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
        self.start_tour("/my/asistencia", "ems_portal_under_construction_render",
                         login="test_portal_tour_student")
