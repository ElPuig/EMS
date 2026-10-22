from odoo.tests.common import HttpCase, tagged

from .common import mock_outgoing_email
from .test_erasmus import upload
from .test_portal_erasmus import create_portal_erasmus_fixtures


@tagged('post_install', '-at_install')
class TestErasmusTour(HttpCase):
    """Issue #683 - each Erasmus+ screen, driven by the least-privileged user that uses it: a
    student on the portal, the Erasmus team on the backend, and the Head of Studies for the
    sanction check."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        create_portal_erasmus_fixtures(cls)
        cls.erasmus_user.name = 'Test Erasmus User'

    def _submitted_application(self):
        application = self.env['ems.erasmus.application']._ems_portal_get_or_create(self.call, self.student)
        upload(application, self.cv)
        application.action_submit()
        return application

    def test_portal_apply_tour(self):
        self.start_tour('/my/erasmus', 'ems_portal_erasmus_apply', login='test_portal_erasmus_student')
        application = self.env['ems.erasmus.application'].search([('partner_id', '=', self.student.id)])
        self.assertEqual(application.state, 'submitted')
        self.assertEqual(application.availability, 'Summer')

    def test_review_tour(self):
        application = self._submitted_application()
        self.start_tour('/odoo/action-ems.action_erasmus_application', 'ems_erasmus_review',
                        login='test_erasmus_team')
        self.assertEqual(application.requirements_check, 'met')
        self.assertEqual(application.document_ids.filtered('is_required').review_state, 'valid')

    def test_calls_tour(self):
        self.start_tour('/odoo/action-ems.action_erasmus_call', 'ems_erasmus_calls', login='test_erasmus_team')

    def test_sanction_check_tour(self):
        application = self._submitted_application()
        self.start_tour('/odoo/action-ems.action_erasmus_application', 'ems_erasmus_sanction_check',
                        login='test_erasmus_hos')
        self.assertEqual(application.sanction_check, 'met')
