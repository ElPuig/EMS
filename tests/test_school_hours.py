from datetime import timedelta

from odoo.tests.common import TransactionCase, tagged

from .common import create_level_study_group, shift_ems_clock
from .test_student_walkout import add_holiday, clear_holidays


class SchoolHoursCase(TransactionCase):
    """A Monday at 10:00 (company time), no holidays unless a test adds one, and a group with class
    Monday to Thursday from 8:00 to 14:00 and on Friday from 9:00 to 12:00."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        clear_holidays(cls)
        cls.today = shift_ems_clock(cls, hour=10.0, weekdays=[0]).date()
        cls.utils = cls.env['ems.datetime_utils']
        _level, _study, cls.group = create_level_study_group(cls, 'SHC')
        cls.calendar = cls.env['resource.calendar'].create({'name': 'SHC schedule', 'attendance_ids': [(5, 0, 0)]})
        cls.env['resource.calendar.attendance'].create([{
            'name': f'SHC {day}', 'calendar_id': cls.calendar.id, 'dayofweek': str(day),
            'hour_from': 9.0 if day == 4 else 8.0, 'hour_to': 12.0 if day == 4 else 14.0,
            'group_ids': [(6, 0, cls.group.ids)],
        } for day in range(5)])

    def _local(self, day_offset, hour):
        """Naive UTC of `hour` (company time) `day_offset` days from Monday."""
        return self.utils.datetime_to_odoo(
            self.utils.time_float_to_utc_datetime(self.today + timedelta(days=day_offset), hour))


@tagged('post_install', '-at_install')
class TestSchoolHourCounting(SchoolHoursCase):
    """Issues #800, #828: counting hours over school days and when an email reaches a group. Only the
    API that predates issue #828, so the same tests run against the code before it (they did, before
    its refactor) and after it. See docs/en/developers/attendance/student_walkout.md."""

    def test_add_school_hours(self):
        add = self.utils.ems_add_school_hours
        cases = [
            ((0, 10.0), 5, (0, 15.0), "Within the day"),
            ((0, 10.0), 1.5, (0, 11.5), "Fractions of an hour"),
            ((0, 22.0), 5, (1, 3.0), "The night of a school day counts"),
            ((4, 13.0), 24, (7, 13.0), "The weekend counts nothing"),
            ((5, 10.0), 1, (7, 1.0), "Started on a Saturday, it counts from Monday"),
            ((4, 0.0), 24, (5, 0.0), "Exactly a whole Friday ends at Saturday's 00:00"),
            ((0, 10.0), 120, (7, 10.0), "A whole school week"),
            ((5, 10.0), 0, (7, 0.0), "No hours from a Saturday: Monday's 00:00"),
            ((0, 10.0), 0, (0, 10.0), "No hours from a school day: that moment"),
        ]
        for start, hours, end, msg in cases:
            with self.subTest(msg):
                self.assertEqual(add(self._local(*start), hours), self._local(*end), msg)
        add_holiday(self, self.today + timedelta(days=1))
        self.assertEqual(add(self._local(0, 10.0), 24), self._local(2, 10.0), "A public holiday counts nothing")

    def test_school_hours_between(self):
        between = self.utils.ems_school_hours_between
        cases = [
            ((0, 10.0), (0, 15.0), 5),
            ((4, 13.0), (7, 13.0), 24),
            ((5, 10.0), (7, 2.0), 2),
            ((0, 0.0), (7, 0.0), 120),
            ((0, 15.0), (0, 10.0), 0),
            ((0, 10.0), (0, 10.0), 0),
        ]
        for start, end, hours in cases:
            with self.subTest(start=start, end=end):
                self.assertAlmostEqual(between(self._local(*start), self._local(*end)), hours)
        add_holiday(self, self.today + timedelta(days=1))
        self.assertAlmostEqual(between(self._local(0, 10.0), self._local(2, 10.0)), 24)
        # Both functions agree: the hours between a moment and that moment plus some hours.
        start = self._local(3, 17.5)
        for hours in (1, 7.25, 24, 48, 100):
            self.assertAlmostEqual(between(start, self.utils.ems_add_school_hours(start, hours)), hours)

    def test_when_an_email_reaches_the_group(self):
        send = self.group._ems_school_send_time
        cases = [
            ((0, 10.0), False, "During its classes: at once"),
            ((0, 8.0), False, "At the start of its first class: at once"),
            ((0, 7.0), (0, 8.0), "Before its classes: at their start"),
            ((0, 14.0), (1, 8.0), "At the end of its last class: the next day"),
            ((3, 15.0), (4, 9.0), "Each weekday starts at its own first class"),
            ((4, 12.5), (7, 8.0), "After Friday's classes: Monday"),
            ((5, 10.0), (7, 8.0), "On a Saturday: Monday"),
        ]
        for moment, expected, msg in cases:
            with self.subTest(msg):
                self.assertEqual(send(self._local(*moment)), expected and self._local(*expected), msg)
        add_holiday(self, self.today + timedelta(days=1))
        self.assertEqual(send(self._local(0, 15.0)), self._local(2, 8.0), "A public holiday is skipped")

    def test_a_group_with_no_schedule_gets_it_at_once(self):
        self.calendar.attendance_ids.unlink()
        self.assertFalse(self.group._ems_school_send_time(self._local(5, 10.0)))

    def test_the_day_runs_from_the_first_class_to_the_last(self):
        """Classes from 8:00 to 10:00 and from 11:00 to 14:00: 10:30 is within the day (the break
        too). Slots of an archived schedule do not count."""
        monday = self.calendar.attendance_ids.filtered(lambda slot: slot.dayofweek == '0')
        monday.hour_to = 10.0
        self.env['resource.calendar.attendance'].create({
            'name': 'SHC Monday 2', 'calendar_id': self.calendar.id, 'dayofweek': '0', 'hour_from': 11.0,
            'hour_to': 14.0, 'group_ids': [(6, 0, self.group.ids)]})
        self.assertFalse(self.group._ems_school_send_time(self._local(0, 10.5)))
        archived = self.env['resource.calendar'].create({'name': 'SHC old', 'attendance_ids': [(5, 0, 0)]})
        self.env['resource.calendar.attendance'].create({
            'name': 'SHC old Monday', 'calendar_id': archived.id, 'dayofweek': '0', 'hour_from': 6.0,
            'hour_to': 7.5, 'group_ids': [(6, 0, self.group.ids)]})
        archived.active = False
        self.assertEqual(self.group._ems_school_send_time(self._local(0, 6.5)), self._local(0, 8.0))

    def test_by_default_it_reads_the_clock(self):
        self.assertFalse(self.group._ems_school_send_time(), "Monday 10:00, during its classes")
        now = shift_ems_clock(self, hour=16.0, weekdays=[0])
        tuesday = self.utils.datetime_to_odoo(self.utils.time_float_to_utc_datetime(now.date() + timedelta(days=1), 8.0))
        self.assertEqual(self.group._ems_school_send_time(), tuesday, "Monday 16:00: Tuesday's first class")
