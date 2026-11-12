from datetime import timedelta

from lxml import etree

from odoo.exceptions import AccessError, UserError
from odoo.tests.common import tagged

from .test_erasmus_mobility import ErasmusMobilityCase, ErasmusStaffMobilityCase
from .test_erasmus_staff import ErasmusStaffCase


def _arch(env, xmlid):
    view = env.ref(f'ems.{xmlid}')
    return etree.fromstring(env[view.model].get_view(view.id)['arch'])


def _wizard(env, action, **vals):
    """The record of the dialog an `action_open_*` returns, with its defaults and what is typed in it."""
    defaults = {key[len('default_'):]: value for key, value in action['context'].items()}
    return env[action['res_model']].create({**defaults, **vals})


@tagged('post_install', '-at_install')
class TestErasmusMobilityActions(ErasmusMobilityCase):
    """Issue #786 - the mobility's actions ask for their data in a dialog instead of failing."""

    def test_cancelling_asks_for_the_reason(self):
        """5.15, 8.11: one step, the reason in the dialog; the reason shown only once cancelled."""
        first, _second = self._accepted()
        mobility = first.with_user(self.erasmus_user)
        wizard = _wizard(mobility.env, mobility.action_open_cancel_wizard(), reason='   ')
        with self.assertRaises(UserError):
            wizard.action_confirm()
        self.assertEqual(first.state, 'choosing')
        wizard.reason = 'Travel documents not handed in on time'
        wizard.action_confirm()
        self.assertEqual(first.state, 'cancelled')
        self.assertEqual(first.cancel_reason, 'Travel documents not handed in on time')
        self.assertEqual(first.application_id.state, 'renounced')
        form = _arch(self.env, 'view_erasmus_mobility_form')
        self.assertFalse(form.xpath("//page[@name='cancellation']"), "No tab with a single field any more.")
        self.assertTrue(form.xpath("//div[contains(@class, 'alert')]/field[@name='cancel_reason']"))
        self.assertTrue(form.xpath("//button[@name='action_open_cancel_wizard']"))
        self.assertFalse(form.xpath("//button[@name='action_cancel']"))

    def test_only_the_team_cancels(self):
        first, _second = self._accepted()
        with self.assertRaises(AccessError):
            first.with_user(self.teacher_user).action_open_cancel_wizard()

    def test_setting_the_agreed_destination_asks_for_it(self):
        """5.16: the country, city, host entity and dates in the dialog."""
        first, _second = self._accepted()
        mobility = first.with_user(self.erasmus_user)
        today = self.env['ems.datetime_utils'].get_local_today()
        wizard = _wizard(mobility.env, mobility.action_open_destination_wizard(),
                         country_id=self.env.ref('base.ie').id, city='Cork',
                         date_start=today + timedelta(days=60), date_end=today + timedelta(days=50))
        with self.assertRaises(UserError):
            wizard.action_confirm()  # ends before it starts
        self.assertEqual(first.state, 'choosing')
        wizard.date_end = False
        wizard.action_confirm()
        self.assertEqual(first.state, 'preparing')
        self.assertEqual((first.country_id, first.city), (self.env.ref('base.ie'), 'Cork'))
        self.assertEqual(first.date_start, wizard.date_start)


@tagged('post_install', '-at_install')
class TestErasmusStaffMobilityActions(ErasmusStaffMobilityCase):

    def test_no_agreed_destination_for_staff(self):
        """8.2: staff propose their activity and the Direction validates it."""
        mobility = self._accepted_staff()
        with self.assertRaises(UserError):
            mobility.with_user(self.erasmus_user).action_agree_destination()
        button = _arch(self.env, 'view_erasmus_mobility_form').xpath(
            "//button[@name='action_open_destination_wizard']")[0]
        self.assertIn("audience == 'staff'", button.get('invisible'))


@tagged('post_install', '-at_install')
class TestErasmusStaffCallActions(ErasmusStaffCase):

    def test_plans_go_to_the_panel_only_before_the_provisional(self):
        """6.8: the button only in the scoring phase, and the server says so afterwards."""
        application = self._admitted(0)
        self.staff_call.action_close()
        self.staff_call.action_send_to_panel()
        self._rate(application, '1', '1')
        self._complete(application)
        self._publish('admission')
        self._publish('provisional')
        with self.assertRaises(UserError):
            self.staff_call.action_send_to_panel()
        button = _arch(self.env, 'view_erasmus_call_form').xpath("//button[@name='action_send_to_panel']")[0]
        self.assertIn("phase != 'scoring'", button.get('invisible'))

    def test_print_the_published_list_from_the_actions(self):
        """4.5: this resolution's PDF from the form's Actions, not every record of the pager."""
        application = self._admitted(0)
        self.staff_call.action_close()
        self.staff_call.action_send_to_panel()
        self._rate(application, '1', '1')
        self._complete(application)
        resolution = self._publish('admission')
        action = resolution.with_user(self.erasmus_user).action_print()
        self.assertEqual(action['report_name'], 'ems.report_erasmus_resolution')
        self.assertEqual(action['context']['active_ids'], resolution.ids)
        report = self.env.ref('ems.action_report_erasmus_resolution')
        self.assertEqual(report.binding_view_types, 'list', "The form has it in Actions: not twice.")
