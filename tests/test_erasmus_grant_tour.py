from odoo.tests.common import HttpCase, tagged

from .test_erasmus_grant import ErasmusGrantCase


@tagged('post_install', '-at_install')
class TestErasmusGrantTour(HttpCase, ErasmusGrantCase):
    """Issue #697 - the Erasmus team's invoices and grants, and the Secretary's payments."""

    def test_grant_team_tour(self):
        first, second = self._preparing()
        self.start_tour('/odoo/action-ems.action_erasmus_invoice', 'ems_erasmus_grant_team', login='test_erasmus_team')
        self.assertEqual(first.grant_net, 950)
        self.assertEqual(first.payment_ids.amount, 760)
        self.assertEqual(second.provision_amount, 300)

    def test_grant_secretary_tour(self):
        first, _second = self._preparing()
        self.student.bank_ids = [(0, 0, {'acc_number': 'ES9121000418450200051332'})]
        first.grant_amount = 1000
        first.action_request_prefinancing()
        self.start_tour('/odoo/action-ems.action_erasmus_payment', 'ems_erasmus_grant_secretary',
                        login='test_erasmus_secretary')
        self.assertEqual(first.payment_ids.state, 'paid')
