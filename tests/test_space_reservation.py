# -*- coding: utf-8 -*-

import importlib.util
import os
from datetime import datetime, time, timedelta

from odoo import fields
from odoo.exceptions import AccessError, ValidationError
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
        with self.assertRaises(AccessError):
            as_other.write({'reason': 'Taken'})
        with self.assertRaises(AccessError):
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
