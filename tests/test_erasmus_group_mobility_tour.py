from odoo.tests.common import HttpCase, tagged

from .test_erasmus_group_mobility import ErasmusGroupMobilityCase


@tagged('post_install', '-at_install')
class TestErasmusGroupMobilityTour(HttpCase, ErasmusGroupMobilityCase):
    """Issues #701-#704 - the group mobility's panel as its leader and accompanying teachers (the
    least privileged roles that use it), and the coordinator's overview."""

    def test_leader_tour(self):
        self._ranked()
        self.start_tour('/odoo/action-ems.action_erasmus_my_group_mobility', 'ems_erasmus_group_leader',
                        login=self.leader_user.login)
        self.assertEqual(self.mobility.state, 'validation')
        self.assertEqual(self.mobility.proposal_user_id, self.leader_user)

    def test_companion_tour(self):
        self._approved()
        self.start_tour('/odoo/action-ems.action_erasmus_my_group_mobility', 'ems_erasmus_group_companion',
                        login=self.companion_user.login)
        self.assertEqual(self.mobility.log_ids.author_id, self.companion_user)

    def test_coordinator_tour(self):
        self._ranked()
        self.mobility.action_submit_proposal()
        self.start_tour('/odoo/action-ems.action_erasmus_group_mobility', 'ems_erasmus_group_coordinator',
                        login=self.coordinator_user.login)
        self.assertEqual(self.mobility.state, 'preparation')
