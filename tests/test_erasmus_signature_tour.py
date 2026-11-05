from odoo.tests.common import HttpCase, tagged

from .test_erasmus_signature import ErasmusSignatureCase


@tagged('post_install', '-at_install')
class TestErasmusSignatureTour(HttpCase, ErasmusSignatureCase):
    """The Erasmus team sends the filled-in grant agreement to sign from the mobility, and the call
    document shows its signature template."""

    def test_send_to_sign_tour(self):
        _first, agreement = self._agreement()
        self.start_tour('/odoo/action-ems.action_erasmus_mobility', 'ems_erasmus_send_to_sign',
                        login='test_erasmus_technician')
        self.assertEqual(agreement.sudo().sign_request_id.state, '1_draft')
