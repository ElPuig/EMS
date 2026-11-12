from odoo.tests.common import HttpCase, tagged

from .common import mock_outgoing_email
from .test_erasmus import PDF
from .test_erasmus_mobility import ErasmusStaffMobilityCase
from .test_erasmus_staff import STAFF_PLAN, create_staff_call_fixtures


@tagged('post_install', '-at_install')
class TestErasmusStaffTour(HttpCase):
    """Issue #686 - the staff call's screens, each driven by the least-privileged user that uses
    it: a teacher applying (in the backend, the 2026-11-04 review), a teacher of the panel rating,
    the Erasmus team for the rest."""

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

    def test_staff_backend_apply_tour(self):
        """The 2026-11-04 review: a teacher applies in the backend, never on the portal."""
        self.staff_users[0].lang = 'en_US'  # the date fields are typed in
        self.start_tour('/odoo/action-ems.action_erasmus_staff_calls', 'ems_erasmus_staff_backend_apply',
                        login='test_erasmus_staff_1')
        application = self.env['ems.erasmus.application'].search([('call_id', '=', self.staff_call.id)])
        self.assertEqual(application.state, 'submitted')
        self.assertEqual(str(application.declared_centre_start_date), '2015-09-01')
        self.assertEqual((application.proposal_a, application.proposal_b),
                         ('Job shadowing at the Tour host school, in April', 'An English course in Malta, in July'))
        self.assertEqual((application.declared_last_staff_mobility, application.declared_seniority), ('never', 'y5'))
        self.assertEqual(application.plan_text, 'Tour plan_text')

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


@tagged('post_install', '-at_install')
class TestErasmusStaffMobilityTour(HttpCase, ErasmusStaffMobilityCase):
    """The 2026-11-04 review: a selected teacher prepares their mobility in the backend."""

    def test_staff_backend_mobility_tour(self):
        mobility = self._accepted_staff()
        mobility.partner_id.user_ids.lang = 'en_US'  # the date fields are typed in
        self.start_tour('/odoo/action-ems.action_erasmus_my_mobilities', 'ems_erasmus_staff_backend_mobility',
                        login='test_erasmus_staff_1')
        self.assertEqual((mobility.proposal_state, mobility.proposal_activity, mobility.proposal_host),
                         ('pending', 'course', 'Tour Course Provider'))
        self.assertEqual(str(mobility.proposal_date_start), '2027-07-05')

    def test_staff_grant_tour(self):
        """Issue #810: the teacher reads their grant in their mobility, without changing it."""
        mobility = self._validated_staff()
        mobility.grant_amount = 1000
        mobility.partner_id.user_ids.lang = 'en_US'  # the amounts are read in English format
        self.start_tour(f'/odoo/action-ems.action_erasmus_my_mobilities/{mobility.id}', 'ems_erasmus_staff_grant',
                        login='test_erasmus_staff_1')

    def test_staff_resolution_tour(self):
        """Issue #810: the staff resolution shows no modality column."""
        mobility = self._accepted_staff()
        resolution = mobility.application_id.call_id.resolution_ids.filtered(lambda line: line.kind == 'definitive')
        self.start_tour(f'/odoo/action-ems.action_erasmus_resolution/{resolution.id}', 'ems_erasmus_staff_resolution',
                        login='test_erasmus_team')
