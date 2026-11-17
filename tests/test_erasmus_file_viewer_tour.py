from odoo.tests.common import HttpCase, tagged

from .common import mock_outgoing_email
from .test_erasmus import upload
from .test_portal_erasmus import create_portal_erasmus_fixtures


@tagged('post_install', '-at_install')
class TestErasmusFileViewerTour(HttpCase):
    """Issue #845 - as the Erasmus team: a file is viewed in Odoo's file viewer, and a confidential
    document's file has neither a download button nor the viewer's Download and Print."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        create_portal_erasmus_fixtures(cls)
        cls.application = cls.env['ems.erasmus.application']._ems_portal_get_or_create(cls.call, cls.student)
        upload(cls.application, cls.cv)
        upload(cls.application, cls.evidence, 'evidence.pdf')

    def test_file_viewer_tour(self):
        self.start_tour('/odoo/action-ems.action_erasmus_application', 'ems_erasmus_file_viewer',
                        login='test_erasmus_team')
        notes = self.application.message_ids.filtered(lambda message: 'evidence.pdf' in (message.body or ''))
        self.assertTrue(notes, "Opening the confidential file is noted on the application")
