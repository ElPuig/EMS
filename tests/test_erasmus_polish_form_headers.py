from datetime import timedelta

from lxml import etree

from odoo.tests.common import tagged

from .test_erasmus_mobility import ErasmusMobilityCase
from .test_erasmus_pocket_money import ErasmusPocketMoneyCase
from .test_erasmus_staff import ErasmusStaffCase


@tagged('post_install', '-at_install')
class TestErasmusFormHeaders(ErasmusMobilityCase):
    """Issue #784 - form headers and smart buttons: what matters on top, the rest one click away."""

    def test_call_buttons_count_each_step(self):
        first, second = self._accepted()
        call = self.call
        self.assertEqual(call.mobility_count, 2)
        self.assertEqual(call.ranked_count, len(call.application_ids.filtered('rank')))
        self.assertEqual(call.resolution_count, len(call.resolution_ids))
        self.assertEqual(call.claim_count, 0)

    def test_mobility_header(self):
        first, _second = self._accepted()
        self.assertEqual(first.with_context(ems_mobility_short_name=True).display_name, first.partner_id.name,
                         "5.4: the breadcrumb says who; the call is on the form.")
        self.assertIn(self.call.name, first.display_name, "Anywhere else, the call too.")
        self.assertEqual(first.action_open_application()['res_id'], first.application_id.id)
        self.assertEqual(first.record_progress, f"{first.record_done} / {first.record_total}")
        self.assertFalse(first.record_overdue)
        line = first.document_ids.filtered('is_required')[:1]
        line.call_document_id.write({'due_basis': 'before_start', 'due_days': 0})
        first.date_start = self.env['ems.datetime_utils'].get_local_today() - timedelta(days=1)
        if line.file_state != 'complete':
            self.assertGreaterEqual(first.record_overdue, 1, "5.6: red only once a deadline has passed.")

    def test_eu_survey_once_the_stay_is_over(self):
        first, _second = self._accepted()
        today = self.env['ems.datetime_utils'].get_local_today()
        first.date_end = today + timedelta(days=5)
        self.assertFalse(first.stay_over)
        first.date_end = today - timedelta(days=1)
        self.assertTrue(first.stay_over)

    def test_commitment_letter_in_one_line(self):
        first, _second = self._accepted()
        self._destinations(2)
        self.call.action_open_destination_choice()
        first = first.with_context(lang='en_US')
        self.assertEqual(first.commitment_status, "To sign on the portal")
        first.action_sign_commitment(True, '127.0.0.1')
        self.assertTrue(first.commitment_status.startswith("Signed on "))

    def test_application_and_offer_views(self):
        Application = self.env['ems.erasmus.application']
        form = etree.fromstring(Application.get_view(self.env.ref('ems.view_erasmus_application_form').id)['arch'])
        self.assertFalse(form.xpath("//page[@name='answers']"), "3.11: the answers are in the Application tab.")
        self.assertTrue(form.xpath("//page[@name='documents']//field[@name='plan_text']"))
        offers = etree.fromstring(self.env['ems.erasmus.offer'].get_view(
            self.env.ref('ems.view_erasmus_offer_list').id)['arch'])
        self.assertTrue(offers.xpath("//field[@widget='remaining_days']"), "4.8: days left to answer.")

    def test_host_entity_counts_its_mobilities(self):
        first, second = self._accepted()
        host = self.env['res.partner'].create({'name': 'Test host entity 784', 'is_company': True,
                                               'is_erasmus_host': True})
        (first | second).write({'host_partner_id': host.id})
        self.assertEqual((host.erasmus_individual_count, host.erasmus_group_count, host.erasmus_mobility_count),
                         (2, 0, 2))
        self.assertEqual(host.action_view_erasmus_mobilities()['domain'], [('host_partner_id', '=', host.id)])


@tagged('post_install', '-at_install')
class TestErasmusStaffFormHeaders(ErasmusStaffCase):
    """Issue #784 (7.8) - the staff application opens the teacher's staff record from a button."""

    def test_staff_record_button(self):
        application = self._apply(0)
        action = application.action_open_employee()
        self.assertEqual((action['res_model'], action['res_id']), ('hr.employee', application.employee_id.id))


@tagged('post_install', '-at_install')
class TestErasmusGroupWhoPays(ErasmusPocketMoneyCase):
    """Issue #784 (9.15) - who pays the travel and accommodation, asked in positive."""

    def test_who_pays_is_the_same_choice(self):
        self.assertEqual(self.mobility.travel_paid_by, 'centre')
        self.mobility.travel_paid_by = 'participant'
        self.assertTrue(self.mobility.no_direct_costs)
        self.mobility.no_direct_costs = False
        self.assertEqual(self.mobility.travel_paid_by, 'centre')
