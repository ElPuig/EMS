from odoo.tests.common import HttpCase, tagged

from .common import create_role_user, mock_outgoing_email
from .test_erasmus_group_mobility import create_group_mobility_fixtures
from .test_portal_erasmus import create_portal_erasmus_fixtures

CARD_CLASSES = ('card border-primary', 'card-body', 'card-title', 'card-text')


class ErasmusInfoCodeviewMixin:
    """Issue #774 - the Erasmus team (the Mobility technician, the least privileged role that edits
    these texts) pastes a prepared card through the code view, and its Bootstrap classes are kept."""

    def assertCardKept(self, html):
        for css_class in CARD_CLASSES:
            self.assertIn(f'class="{css_class}"', str(html))


@tagged('post_install', '-at_install')
class TestErasmusCallInfoCodeviewTour(ErasmusInfoCodeviewMixin, HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        create_portal_erasmus_fixtures(cls)
        cls.technician_user = create_role_user(cls, 'erasmus', 'test_erasmus_codeview_technician')

    def test_call_info_codeview_tour(self):
        self.start_tour('/odoo/action-ems.action_erasmus_call', 'ems_erasmus_call_info_codeview',
                        login=self.technician_user.login)
        self.assertCardKept(self.call.description)


@tagged('post_install', '-at_install')
class TestErasmusGroupInfoCodeviewTour(ErasmusInfoCodeviewMixin, HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        create_group_mobility_fixtures(cls)

    def test_group_info_codeview_tour(self):
        self.start_tour('/odoo/action-ems.action_erasmus_group_mobility', 'ems_erasmus_group_info_codeview',
                        login=self.technician_user.login)
        self.assertCardKept(self.mobility.description)
