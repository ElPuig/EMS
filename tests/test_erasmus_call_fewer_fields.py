from datetime import datetime, timedelta

from odoo import fields
from odoo.tests import Form
from odoo.tests.common import TransactionCase, tagged

from .common import create_role_user, mock_outgoing_email
from .test_erasmus import create_erasmus_fixtures


@tagged('post_install', '-at_install')
class TestErasmusCallFewerFields(TransactionCase):
    """Issue #767 - fewer fields when opening a call: the deadlines filled in from the closing
    date, the dates' order warned, a students' modality's project taken from its levels."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        create_erasmus_fixtures(cls)
        cls.technician = create_role_user(cls, 'erasmus', 'test_fewer_fields_technician')
        cls.utils = cls.env['ems.datetime_utils']
        # The centre's holidays and breaks of the dev database stay out of the dates checked here.
        cls.env['resource.calendar.leaves'].search([
            ('resource_id', '=', False), ('date_from', '<', '2027-01-31'), ('date_to', '>', '2026-11-01')]).unlink()

    def _utc(self, day, hour):
        """A local day and hour of the centre, as Odoo stores it."""
        return self.utils.datetime_to_odoo(self.utils.time_float_to_utc_datetime(day, hour))

    def _call(self, close, **values):
        return self.env['ems.erasmus.call'].with_user(self.technician).create({
            'name': 'Fewer fields call', 'date_open': close - timedelta(days=10), 'date_close': close, **values})

    # --- deadlines from the closing date ------------------------------------------------------

    def test_the_four_deadlines_follow_the_rule_of_the_issue(self):
        """The 2026-27 call closes on Friday 20/11 at 23:00: corrections Fri 27/11, score correction
        Fri 04/12, claims Wed 09/12, acceptance Tue 15/12, all at 14:00."""
        call = self._call(self._utc(datetime(2026, 11, 20).date(), 23.0))
        self.assertEqual(
            [call.subsanation_deadline, call.interview_deadline, call.claims_deadline, call.acceptance_deadline],
            [self._utc(datetime(2026, 11, 27).date(), 14.0), self._utc(datetime(2026, 12, 4).date(), 14.0),
             self._utc(datetime(2026, 12, 9).date(), 14.0), self._utc(datetime(2026, 12, 15).date(), 14.0)])

    def test_a_deadline_on_a_weekend_or_a_holiday_moves_to_the_next_school_day(self):
        # Closing on Monday 23/11: claims on Saturday 12/12, so Monday 14/12.
        call = self._call(self._utc(datetime(2026, 11, 23).date(), 23.0))
        self.assertEqual(call.claims_deadline, self._utc(datetime(2026, 12, 14).date(), 14.0))
        # Corrections on Monday 30/11, a holiday of the centre here: Tuesday 01/12.
        self.env['resource.calendar.leaves'].create({
            'name': 'Test Erasmus holiday', 'date_from': self._utc(datetime(2026, 11, 30).date(), 0.0),
            'date_to': self._utc(datetime(2026, 11, 30).date(), 23.99)})
        self.assertEqual(call._ems_deadlines(call.date_close)['subsanation_deadline'],
                         self._utc(datetime(2026, 12, 1).date(), 14.0))

    def test_the_deadlines_follow_the_closing_date_unless_changed_by_hand(self):
        call = self._call(self._utc(datetime(2026, 11, 20).date(), 23.0))
        moved = call.claims_deadline + timedelta(days=1)
        call.claims_deadline = moved
        call.date_close = self._utc(datetime(2026, 11, 27).date(), 23.0)
        self.assertEqual(call.subsanation_deadline, self._utc(datetime(2026, 12, 4).date(), 14.0))
        self.assertEqual(call.acceptance_deadline, self._utc(datetime(2026, 12, 22).date(), 14.0))
        self.assertEqual(call.claims_deadline, moved, "Changed by hand: it stays.")

    def test_a_deadline_given_on_create_is_kept(self):
        given = self._utc(datetime(2026, 12, 18).date(), 10.0)
        call = self._call(self._utc(datetime(2026, 11, 20).date(), 23.0), acceptance_deadline=given)
        self.assertEqual(call.acceptance_deadline, given)
        self.assertTrue(call.claims_deadline, "The others are filled in.")

    def test_the_form_fills_the_deadlines_in_as_the_closing_date_is_set(self):
        """A new call, in the form: the deadlines follow each closing date set before saving."""
        form = Form(self.env['ems.erasmus.call'].with_user(self.technician))
        form.name = 'Fewer fields form call'
        form.date_open = self._utc(datetime(2026, 11, 9).date(), 9.0)
        form.date_close = self._utc(datetime(2026, 11, 20).date(), 23.0)
        self.assertEqual(form.subsanation_deadline, self._utc(datetime(2026, 11, 27).date(), 14.0))
        form.date_close = self._utc(datetime(2026, 11, 27).date(), 23.0)
        self.assertEqual(form.subsanation_deadline, self._utc(datetime(2026, 12, 4).date(), 14.0))
        call = form.save()
        self.assertEqual(call.reminder_days, 3, "The reminder is always 3 days before closing.")
        with Form(call.with_user(self.technician)) as saved:
            saved.date_close = self._utc(datetime(2026, 11, 20).date(), 23.0)
            self.assertEqual(saved.subsanation_deadline, self._utc(datetime(2026, 11, 27).date(), 14.0))

    def test_a_staff_call_follows_the_same_rule(self):
        call = self._call(self._utc(datetime(2026, 11, 20).date(), 23.0), audience='staff')
        self.assertEqual(call.interview_deadline, self._utc(datetime(2026, 12, 4).date(), 14.0),
                         "The panel's deadline is the score correction one.")
        self.assertEqual(call.acceptance_deadline, self._utc(datetime(2026, 12, 15).date(), 14.0))

    # --- dates out of order (note 2.4) --------------------------------------------------------

    def test_dates_out_of_the_process_order_are_warned(self):
        call = self._call(self._utc(datetime(2026, 11, 20).date(), 23.0))
        self.assertFalse(call.date_order_warning)
        call.claims_deadline = self._utc(datetime(2026, 11, 18).date(), 14.0)
        self.assertEqual(call.date_order_warning, "Claims deadline is before applications close",
                         "Against the first earlier step it comes before.")
        call.claims_deadline = False
        self.assertFalse(call.date_order_warning, "An empty deadline is not compared.")

    # --- modalities: the project from the levels ----------------------------------------------

    def test_a_students_modality_takes_its_project_from_its_levels(self):
        call = self._call(self._utc(datetime(2026, 11, 20).date(), 23.0), modality_ids=[
            (0, 0, {'name': 'GM', 'level_ids': [(6, 0, self.env.ref('ems.level_cfgm').ids)]}),
            (0, 0, {'name': 'GS', 'level_ids': [(6, 0, (self.env.ref('ems.level_cfgs')
                                                        | self.env.ref('ems.level_efps')).ids)]})])
        self.assertEqual(call.modality_ids.mapped('project'), ['ka121_vet', 'ka131_hed'])
        call.modality_ids[1].level_ids = self.env.ref('ems.level_cfgb')
        self.assertEqual(call.modality_ids[1].project, 'ka121_vet', "It follows a change of levels.")

    def test_a_staff_modality_keeps_the_project_set(self):
        call = self._call(self._utc(datetime(2026, 11, 20).date(), 23.0), audience='staff')
        self.assertEqual(call.modality_ids.mapped('project'), ['ka121_vet', 'ka131_hed'])
        call.modality_ids[0].project = 'ka131_hed'
        self.assertEqual(call.modality_ids[0].project, 'ka131_hed')

    def test_the_ex_officio_circuit_still_counts_school_days(self):
        """The school-day count moved to resource.calendar.leaves (shared with the deadlines)."""
        Leave = self.env['resource.calendar.leaves']
        friday = datetime(2026, 11, 20).date()
        self.assertEqual(Leave._ems_nth_school_day(friday, 1), datetime(2026, 11, 23).date())
        self.assertEqual(Leave._ems_nth_school_day(friday, 1, include_start=True), friday)
        self.assertEqual(Leave._ems_nth_school_day(friday, 0), friday)
        self.assertEqual(fields.Date.to_date('2026-11-27'), Leave._ems_nth_school_day(friday, 5))
