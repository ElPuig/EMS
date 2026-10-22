from odoo.tests.common import HttpCase, tagged

from .test_erasmus_resolution import ErasmusResolutionCase


@tagged('post_install', '-at_install')
class TestErasmusResolutionTour(HttpCase, ErasmusResolutionCase):
    """Issue #685 - resolutions, place offers and claims, driven by an Erasmus team user, and the
    place accepted from the portal by the selected student."""

    def test_publish_resolution_tour(self):
        self._scored_call()
        self._publish('admission')
        resolution = self._resolution('provisional')
        self.start_tour('/odoo/action-ems.action_erasmus_resolution', 'ems_erasmus_resolution_publish',
                        login='test_erasmus_team')
        self.assertEqual(resolution.state, 'published')

    def test_offer_place_tour(self):
        first, second = self._scored_call()
        self._publish_up_to_definitive()
        first.offer_ids.action_renounce()
        self.start_tour('/odoo/action-ems.action_erasmus_call', 'ems_erasmus_offer_place', login='test_erasmus_team')
        self.assertEqual(second.offer_ids.state, 'pending')
        self.assertTrue(second.offer_ids.from_reserve)

    def test_offers_tour(self):
        self._scored_call()
        self._publish_up_to_definitive()
        self.start_tour('/odoo/action-ems.action_erasmus_offer', 'ems_erasmus_offers', login='test_erasmus_team')

    def test_claims_tour(self):
        first, _second = self._scored_call()
        self._publish('admission')
        provisional = self._publish('provisional')
        claim = self.env['ems.erasmus.claim'].create({
            'application_id': first.id, 'resolution_id': provisional.id, 'description': 'My interview score'})
        self.start_tour('/odoo/action-ems.action_erasmus_claim', 'ems_erasmus_claims', login='test_erasmus_team')
        self.assertEqual(claim.state, 'resolved')

    def test_portal_accept_tour(self):
        first, _second = self._scored_call()
        self._publish_up_to_definitive()
        self.env['res.users'].with_context(no_reset_password=True).create({
            'name': self.student.name, 'login': 'test_erasmus_tour_student', 'password': 'test_erasmus_tour_student',
            'partner_id': self.student.id, 'lang': 'en_US',
            'groups_id': [(6, 0, [self.env.ref('base.group_portal').id])]})
        self.start_tour(f'/my/erasmus/call/{self.call.id}', 'ems_erasmus_portal_accept',
                        login='test_erasmus_tour_student')
        self.assertEqual(first.state, 'accepted')
