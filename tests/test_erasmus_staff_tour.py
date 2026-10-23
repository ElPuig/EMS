from odoo.tests.common import HttpCase, tagged

from .common import mock_outgoing_email
from .test_erasmus import PDF
from .test_erasmus_staff import STAFF_PLAN, create_staff_call_fixtures


@tagged('post_install', '-at_install')
class TestErasmusStaffTour(HttpCase):
    """Issue #686 - the staff call's screens, each driven by the least-privileged user that uses
    it: a teacher applying on the portal, a teacher of the panel rating, the Erasmus team for the
    rest."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        create_staff_call_fixtures(cls)

    def _admitted_and_closed(self):
        partner = self.staff_users[0].partner_id
        application = self.env['ems.erasmus.application']._ems_portal_get_or_create(self.staff_call, partner)
        application._ems_portal_save(
            {'declared_never_staff_mobility': True, 'declared_centre_start_date': '2015-09-01', **STAFF_PLAN},
            {self.id_document.id: [('id.pdf', PDF)]})
        application.action_submit()
        application.requirements_check = 'met'
        application.document_ids.filtered('attachment_ids').action_mark_valid()
        application.action_admit()
        self.staff_call.action_close()
        return application

    def test_portal_staff_apply_tour(self):
        self.start_tour('/my/erasmus', 'ems_portal_erasmus_staff_apply', login='test_erasmus_staff_1')
        application = self.env['ems.erasmus.application'].search([('call_id', '=', self.staff_call.id)])
        self.assertEqual(application.state, 'submitted')
        self.assertEqual((application.staff_activity, application.host_entity),
                         ('job_shadowing', 'Tour host school'))
        self.assertEqual((application.declared_last_staff_mobility, application.declared_seniority), ('never', 'y5'))
        self.assertEqual(application.plan_objectives, 'Tour plan_objectives')

    def test_my_plan_rating_tour(self):
        application = self._admitted_and_closed()
        self.staff_call.action_send_to_panel()
        self.start_tour('/odoo/action-ems.action_erasmus_my_plan_ratings', 'ems_erasmus_my_plan_rating',
                        login='test_erasmus_panel_teacher')
        rating = application.plan_rating_ids.filtered(lambda rating: rating.evaluator_id == self.panel_teacher)
        self.assertEqual((rating.state, rating.score), ('submitted', 1.5))

    def test_staff_scoring_tour(self):
        application = self._admitted_and_closed()
        self.start_tour('/odoo/action-ems.action_erasmus_application', 'ems_erasmus_staff_scoring',
                        login='test_erasmus_team')
        self.assertEqual((application.last_staff_mobility, application.language_level, application.seniority),
                         ('older', 'c1', 'y2'))
        self.assertEqual(application.score_projects, 1.0)
        self.assertTrue(application.merits_checked)

    def test_staff_call_tour(self):
        application = self._admitted_and_closed()
        self.start_tour('/odoo/action-ems.action_erasmus_call', 'ems_erasmus_staff_call', login='test_erasmus_team')
        self.assertEqual(len(application.plan_rating_ids), 3)

    def test_plan_ratings_tour(self):
        self._admitted_and_closed()
        self.staff_call.action_send_to_panel()
        self.start_tour('/odoo/action-ems.action_erasmus_plan_rating', 'ems_erasmus_plan_ratings',
                        login='test_erasmus_team')
