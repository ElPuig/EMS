from odoo.tests.common import HttpCase, tagged

from .common import create_role_user
from .test_erasmus_mobility import ErasmusMobilityCase


@tagged('post_install', '-at_install')
class TestErasmusActionsTour(HttpCase, ErasmusMobilityCase):
    """Issue #786 - cancelling a mobility and setting its agreed destination through their dialogs, as
    the Mobility technician (the least privileged role of the Erasmus team)."""

    def test_mobility_dialogs_tour(self):
        technician = create_role_user(self, 'erasmus', 'test_actions_technician')
        technician.lang = 'en_US'
        first, second = self._accepted()
        for mobility, tour in ((first, 'cancel'), (second, 'destination')):
            with self.subTest(tour=tour):
                self.start_tour(f'/odoo/action-ems.action_erasmus_mobility/{mobility.id}',
                                f'ems_erasmus_actions_{tour}', login=technician.login)
        self.assertEqual(first.state, 'cancelled')
        self.assertEqual(second.state, 'preparing')
        self.assertEqual(second.city, 'Tour City')

