from unittest.mock import patch

from odoo.tests.common import HttpCase, tagged

from .common import mock_outgoing_email
from .test_erasmus_group_mobility import create_group_mobility_fixtures


@tagged('post_install', '-at_install')
class TestErasmusGroupRankingScoreTour(HttpCase):
    """Issue #773, as the leader teacher: the score in the selection, never the conduct warnings."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        create_group_mobility_fixtures(cls)
        Registration = cls.env['ems.erasmus.group.registration']
        first = Registration._ems_portal_enrol(cls.mobility, cls.students[0], fewer_opportunities=True)
        Registration._ems_portal_enrol(cls.mobility, cls.students[1])
        averages = {cls.students[0]: 7.0, cls.students[1]: 7.5}
        with patch.object(type(cls.env['ems.erasmus.application']), '_ems_partner_grade_values',
                          side_effect=lambda partner, _course: [{'grade': averages[partner], 'hours': 100}]):
            cls.mobility.with_user(cls.coordinator_user).action_close_enrolment()
        first.fewer_opportunities_check = 'yes'

    def test_group_ranking_score_tour(self):
        self.start_tour('/odoo/action-ems.action_erasmus_my_group_mobility', 'ems_erasmus_group_ranking_score',
                        login=self.leader_user.login)
