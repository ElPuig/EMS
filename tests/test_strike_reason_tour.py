from odoo.tests.common import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestStrikeReasonTour(HttpCase):

    def test_strike_reason_crud_tour(self):
        self.start_tour("/odoo", "ems_strike_reason_crud", login="admin")

        reason = self.env['ems.strike.reason'].search([('name', '=', 'Tour Strike Reason')])
        self.assertEqual(len(reason), 1)
