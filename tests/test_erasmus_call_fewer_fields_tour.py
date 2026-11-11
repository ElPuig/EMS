from datetime import timedelta

from odoo.tests.common import HttpCase, tagged

from .common import create_role_user, mock_outgoing_email
from .test_erasmus_staff import create_staff_call_fixtures


@tagged('post_install', '-at_install')
class TestErasmusCallFewerFieldsTour(HttpCase):
    """Issue #767 - the call form opens with fewer fields, as the Mobility technician (list and
    form, the call action's two view modes)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        create_staff_call_fixtures(cls)
        cls.technician = create_role_user(cls, 'erasmus', 'test_fewer_fields_tour_technician')

    def test_student_call_tour(self):
        self.call.write(self.call._ems_deadlines(self.call.date_close))
        self.call.claims_deadline = self.call.date_close - timedelta(days=1)
        self.start_tour('/odoo/action-ems.action_erasmus_call', 'ems_erasmus_call_fewer_fields_student',
                        login=self.technician.login)

    def test_mobility_block_after_the_definitive_resolution_tour(self):
        self.call.state = 'closed'
        self.env['ems.erasmus.resolution'].create({'call_id': self.call.id, 'kind': 'definitive', 'state': 'published'})
        self.assertTrue(self.call.has_final_resolution)
        self.start_tour('/odoo/action-ems.action_erasmus_call', 'ems_erasmus_call_fewer_fields_mobility',
                        login=self.technician.login)

    def test_staff_call_tour(self):
        self.staff_call.write(self.staff_call._ems_deadlines(self.staff_call.date_close))
        self.start_tour('/odoo/action-ems.action_erasmus_call', 'ems_erasmus_call_fewer_fields_staff',
                        login=self.technician.login)
