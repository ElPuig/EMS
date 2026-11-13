from datetime import timedelta

from lxml import etree

from odoo.tests.common import tagged

from .test_erasmus_mobility import ErasmusMobilityCase


@tagged('post_install', '-at_install')
class TestErasmusStatusBars(ErasmusMobilityCase):
    """Issue #785 - status bars with the real phases of a call, an offer and a mobility."""

    def test_call_phases(self):
        """2.8: "Closed" only meant the applications; the bar follows the resolutions and the offers."""
        call = self.call
        self.assertEqual(call.phase, 'published')
        first, second = self._scored_call()
        self.assertEqual(call.phase, 'scoring', "Closed, nothing published yet.")
        self._publish('admission')
        self.assertEqual(call.phase, 'scoring', "The admission list is still part of the scoring.")
        self._publish('provisional')
        self.assertEqual(call.phase, 'resolution')
        self._publish('definitive')
        self.assertEqual(call.phase, 'offers', "Offers waiting for an answer.")
        (first | second).offer_ids.filtered(lambda offer: offer.state == 'pending').action_accept()
        self.assertEqual(call.phase, 'finished')

    def test_mobility_phases_from_the_dates(self):
        """5.5: the stay and the return come from the dates, and the hourly job moves them on."""
        first, _second = self._accepted()
        self.assertEqual(first.phase, 'choosing')
        self._destinations(1, 1)
        self.call.action_open_destination_choice()
        first.with_user(self.erasmus_user).write({'country_id': self.env.ref('base.ie').id, 'city': 'Cork'})
        first.with_user(self.erasmus_user).action_agree_destination()
        today = self.env['ems.datetime_utils'].get_local_today()
        first.write({'date_start': today + timedelta(days=10), 'date_end': today + timedelta(days=40)})
        self.assertEqual(first.phase, 'preparing')
        first.date_start = today
        self.assertEqual(first.phase, 'stay', "The start day is already the stay.")
        first.date_end = today
        self.assertEqual(first.phase, 'stay', "So is the last day.")
        first.date_end = today - timedelta(days=1)
        self.assertEqual(first.phase, 'return')
        # Days go by with no write: the job updates only those the dates have overtaken.
        self.env.cr.execute("UPDATE ems_erasmus_mobility SET phase = 'preparing' WHERE id = %s", [first.id])
        first.invalidate_recordset(['phase'])
        self.env['ems.erasmus.mobility']._cron_update_phase()
        first.invalidate_recordset(['phase'])
        self.assertEqual(first.phase, 'return')
        first._ems_set_state('cancelled')
        self.assertEqual(first.phase, 'cancelled')

    def _arch(self, xmlid):
        view = self.env.ref(f'ems.{xmlid}')
        return etree.fromstring(self.env[view.model].get_view(view.id)['arch'])

    def test_status_bars_show_the_phases(self):
        """2.8, 4.11, 5.5, 5.7: the bars, and the two checkboxes gone."""
        for xmlid in ('view_erasmus_call_form', 'view_erasmus_mobility_form', 'view_erasmus_mobility_staff_form'):
            self.assertTrue(self._arch(xmlid).xpath("//header/field[@name='phase'][@widget='statusbar']"), xmlid)
        mobility = self._arch('view_erasmus_mobility_form')
        self.assertEqual(mobility.xpath("//header/field[@name='phase']")[0].get('statusbar_visible'),
                         'choosing,preparing,stay,return,done')
        for xmlid in ('view_erasmus_mobility_form', 'view_erasmus_mobility_list'):
            arch = self._arch(xmlid)
            self.assertFalse(arch.xpath("//field[@name='preparation_complete' or @name='return_complete']"), xmlid)
        self.assertEqual(self._arch('view_erasmus_mobility_kanban').get('default_group_by'), 'phase')
        offer = self._arch('view_erasmus_offer_form').xpath("//header/field[@name='state']")[0]
        self.assertIn('expired', offer.get('statusbar_visible').split(','))

    def test_portal_position_for_a_phone(self):
        """A06: a phone shows only "Step N of 8"."""
        application = self._admitted()
        position = application._ems_portal_progress()['position']
        # Admitted: the document check is done, the interview is the step the applicant is on.
        self.assertEqual((position['number'], position['total'], position['label']), (3, 8, "Interview"))
