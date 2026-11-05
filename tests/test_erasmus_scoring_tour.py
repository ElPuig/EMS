from odoo.tests.common import HttpCase, tagged

from .common import create_role_user, mock_outgoing_email
from .test_erasmus import upload
from .test_portal_erasmus import create_portal_erasmus_fixtures


@tagged('post_install', '-at_install')
class TestErasmusScoringTour(HttpCase):
    """Issue #684 - the scoring and interview screens, each driven by the least-privileged user
    that uses it: a plain teacher as evaluator, the Erasmus team for the rest. The application is admitted and the call closed (its data frozen)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        create_portal_erasmus_fixtures(cls)
        cls.evaluator = create_role_user(cls, 'teacher', 'test_erasmus_tour_evaluator')
        application = cls.env['ems.erasmus.application']._ems_portal_get_or_create(cls.call, cls.student)
        upload(application, cls.cv)
        application.action_submit()
        application.write({'requirements_check': 'met'})
        application.document_ids.filtered('attachment_ids').action_mark_valid()
        application.action_admit()
        cls.call.action_close()
        cls.application = application
        cls.interview = cls.env['ems.erasmus.interview'].create({
            'application_id': application.id, 'evaluator_id': cls.evaluator.id})

    def test_my_evaluation_tour(self):
        self.start_tour('/odoo/action-ems.action_erasmus_my_interviews', 'ems_erasmus_my_evaluation',
                        login='test_erasmus_tour_evaluator')
        self.assertEqual(self.interview.state, 'submitted')
        self.assertEqual((self.interview.general_score, self.interview.english_score), (16, 12))

    def test_scoring_tour(self):
        self.start_tour('/odoo/action-ems.action_erasmus_application', 'ems_erasmus_scoring',
                        login='test_erasmus_team')
        self.assertEqual(self.application.language_level, 'b2')
        self.assertEqual(self.application.first_mobility, 'yes')

    def test_ranking_tour(self):
        self.start_tour('/odoo/action-ems.action_erasmus_ranking', 'ems_erasmus_ranking',
                        login='test_erasmus_team')

    def test_interviews_list_tour(self):
        """The team's Interviews screen opens, list and form."""
        self.start_tour('/odoo/action-ems.action_erasmus_interview', 'ems_erasmus_ranking_interviews',
                        login='test_erasmus_team')
