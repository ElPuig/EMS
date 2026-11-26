# -*- coding: utf-8 -*-

import importlib.util
import os
from datetime import datetime, time, timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase

from .common import create_role_employee, create_role_user, mock_outgoing_email


class TestSpaceReservation(TransactionCase):
    """A space is busy when a weekly schedule block, another reservation or a meeting holds it.
    Meetings (ems.minute) are reservations too, made automatically (issue #475)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        utils = cls.env['ems.datetime_utils']
        cls.tz = utils.current_tz()
        # A Monday far enough ahead, so no real data of this box lies on it.
        today = utils.get_local_today()
        cls.monday = today + timedelta(days=(7 - today.weekday()) % 7 + 70)
        cls.space = cls.env['ems.space'].create({'code': 'TSR-A', 'name': 'Test Space A (Reservation)'})
        cls.other_space = cls.env['ems.space'].create({'code': 'TSR-B', 'name': 'Test Space B (Reservation)'})
        cls.calendar = cls.env['resource.calendar'].create({'name': 'Test Calendar (Reservation)'})
        cls.block = cls.env['resource.calendar.attendance'].create({
            'calendar_id': cls.calendar.id, 'name': 'Test block', 'dayofweek': '0',
            'hour_from': 9.0, 'hour_to': 11.0, 'space_id': cls.space.id,
        })
        cls.claustre = cls.env.ref('__import__.minute_type_claustre')

    def _utc(self, hour, day=None):
        """Naive UTC datetime of the company's local `hour` (float) on `day` (a Monday by default)."""
        local = datetime.combine(day or self.monday, time(int(hour), int(round(hour % 1 * 60)))).replace(tzinfo=self.tz)
        return self.env['ems.datetime_utils'].local_datetime_to_utc(local).replace(tzinfo=None)

    def _reserve(self, hour, duration=1.0, space=None, day=None, **vals):
        return self.env['ems.space_reservation'].create({
            'space_id': (space or self.space).id, 'start_datetime': self._utc(hour, day),
            'duration': duration, 'reason': 'Test', **vals,
        })

    def _minute(self, hour, duration=1.0, **vals):
        return self.env['ems.minute'].create({
            'type_id': self.claustre.id, 'space_id': self.space.id, 'start_datetime': self._utc(hour),
            'duration': duration, **vals,
        })

    # --- Reservations ----------------------------------------------------------------------------

    def test_end_follows_start_and_duration(self):
        reservation = self._reserve(12.0, 1.5)
        self.assertEqual(reservation.end_datetime, self._utc(13.5))

    def test_overlapping_reservation_is_refused_but_adjacent_and_other_space_are_not(self):
        self._reserve(12.0, 2.0)
        with self.assertRaises(ValidationError):
            self._reserve(13.0)
        self._reserve(14.0)          # starts exactly when the first one ends
        self._reserve(11.5, 0.5, space=self.other_space)
        self._reserve(12.0, space=self.other_space)

    def test_a_schedule_block_holds_the_space(self):
        with self.assertRaises(ValidationError):
            self._reserve(10.0)       # inside the 9-11 block, read in the company's timezone
        with self.assertRaises(ValidationError):
            self._reserve(8.5, 1.0)   # starts before the block, ends inside it
        self._reserve(11.0)           # starts exactly when the block ends
        self._reserve(10.0, space=self.other_space)

    def test_a_schedule_block_only_holds_its_own_weekday_and_dates(self):
        tuesday = self.monday + timedelta(days=1)
        self._reserve(10.0, day=tuesday)
        self.block.date_to = self.monday - timedelta(days=1)
        self._reserve(10.0)           # the block ended before this Monday

    def test_a_reservation_over_several_days_is_held_by_a_block_of_any_of_them(self):
        sunday = self.monday - timedelta(days=1)
        with self.assertRaises(ValidationError):
            self._reserve(20.0, 15.0, day=sunday)          # Sunday 20:00 to Monday 11:00: the 9-11 block
        self._reserve(20.0, 12.0, day=sunday)              # until Monday 08:00: free
        self._reserve(12.0, 36.0)                          # Monday 12:00 to Wednesday 00:00: free
        self.assertFalse(self.space._get_space_busy(self._utc(13.0), self._utc(8.0, self.monday + timedelta(days=1)),
                                                    exclude_reservations=self.env['ems.space_reservation'].search(
                                                        [('space_id', '=', self.space.id)])))

    def test_an_archived_calendar_no_longer_holds_the_space(self):
        self.calendar.active = False
        self._reserve(10.0)

    def test_a_break_does_not_hold_the_space(self):
        self.block.write({'non_teaching': self.env['ems.non_teaching_type'].search([('is_break', '=', True)], limit=1).id})
        if not self.block.non_teaching_is_break:
            self.skipTest("this database has no break type")
        self._reserve(10.0)

    def test_conflict_message_names_who_holds_it_in_local_time(self):
        self._reserve(12.0, 1.0, user_id=self.env.user.id)
        with self.assertRaises(ValidationError) as error:
            self._reserve(12.0)
        self.assertIn('12:00', str(error.exception))

    def test_editing_a_reservation_does_not_clash_with_itself(self):
        reservation = self._reserve(12.0)
        reservation.duration = 2.0
        self.assertEqual(reservation.end_datetime, self._utc(14.0))

    def test_available_spaces_leave_out_the_busy_ones(self):
        reservation = self._reserve(12.0)
        probe = self.env['ems.space_reservation'].new({'start_datetime': self._utc(12.0), 'duration': 1.0})
        self.assertNotIn(self.space, probe.available_space_ids._origin)
        self.assertIn(self.other_space, probe.available_space_ids._origin)
        probe = self.env['ems.space_reservation'].new({'start_datetime': self._utc(9.0), 'duration': 1.0})
        self.assertNotIn(self.space, probe.available_space_ids._origin)    # the schedule block
        probe = self.env['ems.space_reservation'].new({'start_datetime': self._utc(15.0), 'duration': 1.0})
        self.assertIn(self.space, probe.available_space_ids._origin)
        # The record being edited does not hold the space against itself.
        self.assertIn(self.space, reservation.available_space_ids._origin)

    # --- Meetings --------------------------------------------------------------------------------

    def test_a_meeting_with_a_room_makes_its_reservation(self):
        minute = self._minute(12.0, 1.5)
        reservation = minute.space_reservation_ids
        self.assertEqual((reservation.space_id, reservation.start_datetime, reservation.end_datetime),
                         (self.space, self._utc(12.0), self._utc(13.5)))
        with self.assertRaises(ValidationError):
            self._reserve(13.0)

    def test_a_meeting_follows_its_room_and_time(self):
        minute = self._minute(12.0)
        minute.write({'space_id': self.other_space.id, 'start_datetime': self._utc(15.0)})
        self.assertEqual(len(minute.space_reservation_ids), 1)
        self.assertEqual((minute.space_reservation_ids.space_id, minute.space_reservation_ids.start_datetime),
                         (self.other_space, self._utc(15.0)))

    def test_a_meeting_without_a_room_or_online_holds_nothing(self):
        minute = self._minute(12.0)
        minute.space_id = False
        self.assertFalse(minute.space_reservation_ids)
        minute.write({'space_id': self.space.id})
        self.assertTrue(minute.space_reservation_ids)
        minute.modality = 'online'
        self.assertFalse(minute.space_reservation_ids)

    def test_deleting_a_meeting_frees_the_room(self):
        minute = self._minute(12.0)
        minute.unlink()
        self._reserve(12.0)

    def test_a_meetings_reservation_is_only_removed_through_its_meeting(self):
        minute = self._minute(12.0)
        reservation = minute.space_reservation_ids
        secretary = create_role_user(type(self), 'secretary', 'tsr.secretary.meeting@example.com', name='Reservation Secretary')
        self.assertFalse(reservation.with_user(secretary).can_edit)
        with self.assertRaisesRegex(UserError, 'follows its meeting'):
            reservation.with_user(secretary).unlink()
        minute.space_id = False                              # the meeting gives the room up
        self.assertFalse(reservation.exists())

    def test_a_meeting_cannot_take_a_busy_room(self):
        self._reserve(12.0)
        with self.assertRaises(ValidationError):
            self._minute(12.5)
        with self.assertRaises(ValidationError):
            self._minute(10.0)        # the schedule block

    def test_two_meetings_in_the_same_room_at_once_are_refused(self):
        self._minute(12.0)
        with self.assertRaises(ValidationError):
            self._minute(12.0)

    # --- Rules -----------------------------------------------------------------------------------

    def test_a_teacher_reads_all_but_changes_only_their_own(self):
        cls = type(self)
        owner = create_role_user(cls, 'teacher', 'tsr.owner@example.com', name='Reservation Owner')
        other = create_role_user(cls, 'teacher', 'tsr.other@example.com', name='Reservation Other')
        create_role_employee(cls, owner)
        create_role_employee(cls, other)
        reservation = self.env['ems.space_reservation'].with_user(owner).create({
            'space_id': self.space.id, 'start_datetime': self._utc(13.0), 'duration': 1.0, 'reason': 'Mine'})
        self.assertEqual(reservation.user_id, owner)
        as_other = reservation.with_user(other)
        self.assertEqual(as_other.reason, 'Mine')
        self.assertFalse(as_other.can_edit)                  # the form shows it read only
        self.assertTrue(reservation.with_user(owner).can_edit)
        with self.assertRaises(AccessError):
            as_other.write({'reason': 'Taken'})
        with self.assertRaisesRegex(UserError, 'only change your own'):
            as_other.unlink()
        reservation.with_user(owner).write({'reason': 'Still mine'})

    def test_the_secretary_and_the_administrator_change_any(self):
        cls = type(self)
        owner = create_role_user(cls, 'teacher', 'tsr.owner2@example.com', name='Reservation Owner Two')
        create_role_employee(cls, owner)
        reservation = self.env['ems.space_reservation'].with_user(owner).create({
            'space_id': self.space.id, 'start_datetime': self._utc(13.0), 'duration': 1.0, 'reason': 'Mine'})
        for role in ('secretary', 'academic_admin'):
            user = create_role_user(cls, role, f'tsr.{role}@example.com', name=f'Reservation {role}')
            reservation.with_user(user).write({'reason': role})
            self.assertEqual(reservation.reason, role)

    # --- Reservable and the wizard -------------------------------------------------------------------

    def test_a_space_that_is_not_reservable_is_refused_and_not_offered(self):
        self.other_space.reservable = False
        with self.assertRaises(ValidationError):
            self._reserve(15.0, space=self.other_space)
        probe = self.env['ems.space_reservation'].new({'start_datetime': self._utc(15.0), 'duration': 1.0})
        self.assertNotIn(self.other_space, probe.available_space_ids._origin)
        # A meeting may hold any room.
        self._minute(15.0, space_id=self.other_space.id)

    def _wizard(self, hour, **vals):
        wizard = self.env['ems.space_reservation_wizard'].create({
            'mode': 'date', 'date': self.monday, 'start_time': hour, 'end_time': hour + 1.0, **vals})
        return wizard

    def test_the_wizard_lists_only_the_free_reservable_spaces(self):
        self.other_space.reservable = False
        self._reserve(12.0)
        spaces = self._wizard(12.0).free_space_ids
        self.assertNotIn(self.space, spaces)           # reserved
        self.assertNotIn(self.other_space, spaces)     # not reservable
        self.assertNotIn(self.space, self._wizard(10.0).free_space_ids)   # the schedule block
        self.assertIn(self.space, self._wizard(14.0).free_space_ids)

    def test_the_wizard_filters_by_type(self):
        lab = self.env['ems.space_type'].create({'name': 'Test Lab Type (Reservation)'})
        self.other_space.space_type_id = lab
        self.assertEqual(self._wizard(14.0, space_type_id=lab.id).free_space_ids, self.other_space)

    def test_a_type_that_is_not_reservable_makes_its_spaces_not_reservable(self):
        wc = self.env['ems.space_type'].create({'name': 'Test WC Type (Reservation)', 'reservable': False})
        space = self.env['ems.space'].create({'code': 'TSR-W', 'name': 'Test WC', 'space_type_id': wc.id})
        self.assertFalse(space.reservable)
        with self.assertRaises(ValidationError):
            self._reserve(15.0, space=space)
        self.assertNotIn(space, self._wizard(15.0).free_space_ids)
        wc.reservable = True
        self.assertTrue(space.reservable)       # follows its type
        space.reservable = False                # and can still be set on the space itself
        self.assertFalse(space.reservable)

    def test_the_week_of_a_space_says_what_holds_it_and_when(self):
        self._reserve(12.0, 1.5, user_id=self.env.user.id)
        week = self.env['ems.space_reservation_wizard'].get_occupation_week(self.space.id, self.monday.isoformat())
        self.assertEqual(week['monday'], self.monday.isoformat())
        self.assertEqual(len(week['days']), 7)
        blocks = sorted(week['blocks'], key=lambda block: block['start'])
        self.assertEqual([(block['day'], block['kind'], block['start'], block['end']) for block in blocks],
                         [(0, 'schedule', 9.0, 11.0), (0, 'reservation', 12.0, 13.5)])
        self.assertIn('Weekly schedule', blocks[0]['label'])
        self.assertIn('Reserved by', blocks[1]['label'])
        # Any day of the week gives that week; another space has none of it.
        wednesday = (self.monday + timedelta(days=2)).isoformat()
        self.assertEqual(self.env['ems.space_reservation_wizard'].get_occupation_week(self.space.id, wednesday)['monday'],
                         self.monday.isoformat())
        self.assertFalse(self.env['ems.space_reservation_wizard'].get_occupation_week(self.other_space.id, wednesday)['blocks'])
        # The grid covers the school day of the default schedule framework and whatever is held outside it.
        self.assertLessEqual(week['hour_from'], 8)
        self.assertGreaterEqual(week['hour_to'], 21)

    def test_the_week_draws_a_reservation_over_several_days_on_each_of_them(self):
        # From the Sunday before to Tuesday 10:00: it holds the whole Monday and Tuesday until 10:00.
        self._reserve(20.0, 38.0, space=self.other_space, day=self.monday - timedelta(days=1))
        week = self.env['ems.space_reservation_wizard'].get_occupation_week(self.other_space.id, self.monday.isoformat())
        self.assertEqual(sorted((block['day'], block['start'], block['end']) for block in week['blocks']),
                         [(0, 0.0, 24.0), (1, 0.0, 10.0)])

    def test_the_choice_follows_the_free_spaces_when_the_slot_changes(self):
        wizard = self._wizard(14.0)
        wizard.chosen_space_id = self.space
        wizard.write({'start_time': 15.0, 'end_time': 16.0})
        self.assertEqual(wizard.chosen_space_id, self.space)     # still free: the choice stays
        wizard.write({'start_time': 10.0, 'end_time': 11.0})
        self.assertNotIn(self.space, wizard.free_space_ids)      # the schedule block holds it
        self.assertFalse(wizard.chosen_space_id)                 # so the choice goes

    def test_the_wizard_offers_nothing_until_the_end_is_after_the_start(self):
        wizard = self.env['ems.space_reservation_wizard'].create({'date': self.monday, 'start_time': 12.0, 'end_time': 11.0})
        self.assertEqual(wizard.duration, -1.0)
        self.assertFalse(wizard.free_space_ids)
        wizard.end_time = 13.5
        self.assertEqual(wizard.duration, 1.5)
        self.assertIn(self.space, wizard.free_space_ids)
        wizard.mode = 'space'
        self.assertFalse(wizard.free_space_ids)                  # by space there is no list

    def test_the_wizard_reserves_the_slot_chosen_on_the_grid_of_a_space(self):
        wizard = self.env['ems.space_reservation_wizard'].create({
            'mode': 'space', 'space_id': self.space.id, 'space_day': self.monday, 'space_start': 15.0,
            'space_end': 16.5, 'space_reason': 'Talk'})
        self.assertTrue(wizard.show_grid)
        reservation = self.env['ems.space_reservation'].browse(wizard.action_reserve()['res_id'])
        self.assertEqual((reservation.space_id, reservation.reason, reservation.start_datetime, reservation.end_datetime),
                         (self.space, 'Talk', self._utc(15.0), self._utc(16.5)))
        # The slot is now held: the same slot is refused.
        with self.assertRaises(ValidationError):
            wizard.action_reserve()

    def test_the_space_mode_shows_the_grid_by_itself_and_needs_a_day(self):
        wizard = self.env['ems.space_reservation_wizard'].create({'mode': 'space'})
        self.assertFalse(wizard.show_grid)
        wizard.space_id = self.space
        self.assertTrue(wizard.show_grid)
        with self.assertRaises(UserError):
            wizard.action_reserve()                      # no day chosen yet
        wizard.space_id = False
        self.assertFalse(wizard.show_grid)
        with self.assertRaises(UserError):
            wizard.action_reserve()                      # no space

    def test_a_slot_typed_in_the_past_is_refused_on_the_spot_in_either_mode(self):
        today = self.env['ems.datetime_utils'].get_local_today()
        for mode, day_field, start_field in (('date', 'date', 'start_time'), ('space', 'space_day', 'space_start')):
            wizard = self.env['ems.space_reservation_wizard'].new({
                'mode': mode, 'space_id': self.space.id, day_field: today - timedelta(days=1), start_field: 10.0})
            self.assertIn('past', wizard._onchange_slot_not_past()['warning']['message'])
            self.assertFalse(wizard[day_field])                  # cleared: nothing offered or drawn
            self.assertFalse(wizard.free_space_ids)
            wizard[day_field] = self.monday
            self.assertIsNone(wizard._onchange_slot_not_past())  # ahead: kept
            self.assertEqual(wizard[day_field], self.monday)

    def test_late_in_the_day_the_wizard_opens_tomorrow_at_ten(self):
        Wizard = self.env['ems.space_reservation_wizard']
        today = self.env['ems.datetime_utils'].get_local_today()
        for hour, expected in ((21, (today, 22.0)), (22, (today + timedelta(days=1), 10.0))):
            late = datetime.combine(today, time(hour, 30)).replace(tzinfo=self.tz)
            with patch.object(type(Wizard), 'get_local_datetime', return_value=late):
                self.assertEqual(Wizard._default_slot(), expected)

    def test_the_wizard_opens_on_the_next_full_hour(self):
        wizard = self.env['ems.space_reservation_wizard'].new({})
        self.assertEqual(wizard.end_time - wizard.start_time, 1.0)
        self.assertEqual(wizard.start_time % 1, 0.0)
        self.assertIsNone(wizard._onchange_slot_not_past())     # never a time gone by

    def test_the_wizard_reserves_a_free_space_and_refuses_the_past(self):
        wizard = self._wizard(16.0, reason='Line')
        with self.assertRaises(UserError):
            wizard.action_reserve()                      # nothing chosen yet
        wizard.chosen_space_id = self.space
        self.assertTrue(self.env['ems.space_reservation'].browse(wizard.action_reserve()['res_id']).exists())
        past = self.env['ems.space_reservation_wizard'].create({
            'mode': 'space', 'space_id': self.space.id, 'space_day': self.monday - timedelta(days=100),
            'space_start': 10.0, 'space_end': 11.0})
        with self.assertRaises(UserError):
            past.action_reserve()

    # --- Migration -------------------------------------------------------------------------------

    def test_migration_reserves_the_rooms_of_upcoming_meetings_and_logs_the_taken_ones(self):
        path = os.path.join(os.path.dirname(__file__), '..', 'migrations', '18.0.0.53.0', 'post-migrate.py')
        spec = importlib.util.spec_from_file_location('migration_53_0', path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)

        # Meetings as they were before the reservation existed: a room, no reservation.
        first = self._minute(12.0, space_id=self.other_space.id)
        first.space_reservation_ids.unlink()
        clashing = self._minute(12.5, space_id=self.other_space.id)
        clashing.space_reservation_ids.unlink()
        past = self.env['ems.minute'].create({
            'type_id': self.claustre.id, 'space_id': self.other_space.id, 'duration': 1.0,
            'start_datetime': fields.Datetime.now() - timedelta(days=2)})
        past.space_reservation_ids.unlink()

        migration._reserve_rooms_of_upcoming_meetings(self.env)

        self.assertEqual(first.space_reservation_ids.space_id, self.other_space)
        self.assertFalse(clashing.space_reservation_ids)     # the earlier meeting keeps the room
        self.assertFalse(past.space_reservation_ids)         # past meetings need none

    def test_migration_gives_the_catalogue_xmlid_to_a_hand_made_type_without_duplicating_it(self):
        path = os.path.join(os.path.dirname(__file__), '..', 'migrations', '18.0.0.53.0', 'pre-migrate.py')
        spec = importlib.util.spec_from_file_location('pre_migration_53_0', path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        cr = self.env.cr
        wc = self.env.ref('ems.space_type_wc')
        # As an installation that made its WC by hand: the type exists, the catalogue's xmlid does not.
        cr.execute("DELETE FROM ir_model_data WHERE module = 'ems' AND name = 'space_type_wc'")
        migration._name_catalogue_space_types(cr)
        migration._name_catalogue_space_types(cr)          # run twice: still one
        cr.execute("SELECT res_id FROM ir_model_data WHERE module = 'ems' AND name = 'space_type_wc'")
        self.assertEqual(cr.fetchall(), [(wc.id,)])

    def test_migration_leaves_the_spaces_section_without_the_action_it_had(self):
        path = os.path.join(os.path.dirname(__file__), '..', 'migrations', '18.0.0.53.0', 'pre-migrate.py')
        spec = importlib.util.spec_from_file_location('pre_migration_53_0', path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        menu = self.env.ref('ems.menu_spaces')
        menu.action = self.env.ref('ems.action_space_tree')      # as an installation from before
        menu.flush_recordset()
        migration._clear_spaces_menu_action(self.env.cr)
        menu.invalidate_recordset()
        self.assertFalse(menu.action)
        self.assertEqual(self.env.ref('ems.menu_space_list').action, self.env.ref('ems.action_space_tree'))
