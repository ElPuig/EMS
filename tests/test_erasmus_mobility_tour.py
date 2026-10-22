from odoo.tests.common import HttpCase, tagged

from .test_erasmus import PDF
from .test_erasmus_mobility import ErasmusMobilityCase, ErasmusStaffMobilityCase


@tagged('post_install', '-at_install')
class TestErasmusMobilityTour(HttpCase, ErasmusMobilityCase):
    """Issue #687 - mobility preparation, driven by an Erasmus team user, and the destination
    chosen from the portal by the selected student."""

    def test_open_choice_tour(self):
        self._accepted()
        self._destinations(1, 1)
        self.start_tour('/odoo/action-ems.action_erasmus_call', 'ems_erasmus_open_choice', login='test_erasmus_team')
        self.assertTrue(self.call.choice_open)

    def test_mobility_team_tour(self):
        first, _second = self._accepted()
        self._destinations(2)
        self.call.action_open_destination_choice()
        line = first.document_ids.sorted('sequence')[:1]
        first._ems_portal_upload({line.call_document_id.id: [('signed.pdf', PDF)]})
        self.start_tour('/odoo/action-ems.action_erasmus_mobility', 'ems_erasmus_mobility_team',
                        login='test_erasmus_team')
        self.assertEqual(line.review_state, 'valid')
        self.assertTrue(first.task_ids.filtered('done'))

    def test_portal_choose_tour(self):
        first, _second = self._accepted()
        self._destinations(1, 1)
        self.call.action_open_destination_choice()
        self.env['res.users'].with_context(no_reset_password=True).create({
            'name': self.student.name, 'login': 'test_erasmus_tour_student', 'password': 'test_erasmus_tour_student',
            'partner_id': self.student.id, 'lang': 'en_US',
            'groups_id': [(6, 0, [self.env.ref('base.group_portal').id])]})
        self.start_tour(f'/my/erasmus/call/{self.call.id}', 'ems_erasmus_portal_choose',
                        login='test_erasmus_tour_student')
        self.assertEqual(first.state, 'preparing')


@tagged('post_install', '-at_install')
class TestErasmusStaffMobilityTour(HttpCase, ErasmusStaffMobilityCase):

    def test_director_validates_tour(self):
        mobility = self._accepted_staff()
        self.start_tour('/odoo/action-ems.action_erasmus_mobility', 'ems_erasmus_mobility_director',
                        login=self.director_user.login)
        self.assertEqual(mobility.state, 'preparing')
