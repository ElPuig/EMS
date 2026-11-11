from odoo.tests.common import HttpCase, tagged

from .common import create_role_user, mock_outgoing_email
from .test_erasmus_staff import create_staff_call_fixtures


@tagged('post_install', '-at_install')
class TestErasmusStaffPlacesPerProjectTour(HttpCase):
    """Issue #772, as the Mobility technician: the staff call's places per project, the warning of
    an accepted place without a project (note 7.1) and the places left on the mobility."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        create_staff_call_fixtures(cls)
        cls.technician = create_role_user(cls, 'erasmus', 'test_places_staff_technician')
        Application = cls.env['ems.erasmus.application']
        mobilities = cls.env['ems.erasmus.mobility']
        for user in cls.staff_users[:2]:
            application = Application._ems_portal_get_or_create(cls.staff_call, user.partner_id)
            application.write({'state': 'accepted'})
            mobilities |= cls.env['ems.erasmus.mobility'].create({'application_id': application.id})
        mobilities[0].project_id = cls.staff_vet_project
        cls.env['ems.erasmus.resolution'].create({'call_id': cls.staff_call.id, 'kind': 'definitive',
                                                  'state': 'published'})

    def test_staff_places_per_project_tour(self):
        self.assertEqual(self.staff_call.places_without_project, 1)
        self.start_tour(f'/odoo/action-ems.action_erasmus_call/{self.staff_call.id}',
                        'ems_erasmus_staff_places_per_project', login=self.technician.login)
