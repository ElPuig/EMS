from datetime import timedelta

from odoo.exceptions import UserError

from .common import make_working_day
from .test_guard_duty_board import GuardDutyBoardCase


class TestGuardBoardPublicHoliday(GuardDutyBoardCase):
    """Issue #740: on a public holiday (a resource.calendar.leaves with no resource) the guard duty
    board says so, lists no absences and nothing can be organised from it."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Leaves = cls.env['resource.calendar.leaves']
        today = cls.env['ems.datetime_utils'].get_local_today()
        # A Monday still to come (the fixtures teach on '0'), so the board stays editable on it.
        cls.day = today + timedelta(days=7 - today.weekday())

    def setUp(self):
        super().setUp()
        make_working_day(self, self.day)
        self._schedule_class(self.teacher_a, self.group_a, 'TGBPH Calendar A')
        self._absence(self.teacher_a, self.day)

    def _holiday(self, day_from, day_to=None, name='TGBPH Holiday'):
        """A public holiday from the start of `day_from` to the end of `day_to`, company time."""
        utils = self.env['ems.datetime_utils']
        start = utils.datetime_to_odoo(utils.time_float_to_utc_datetime(day_from, 0.0))
        stop = utils.datetime_to_odoo(utils.time_float_to_utc_datetime((day_to or day_from) + timedelta(days=1), 0.0))
        return self.Leaves.create({'name': name, 'date_from': start, 'date_to': stop - timedelta(seconds=1)})

    def test_public_holiday_on_a_day(self):
        holiday = self._holiday(self.day)
        holidays = self._holiday(self.day + timedelta(days=14), self.day + timedelta(days=18), name='TGBPH Holidays')

        self.assertEqual(self.Leaves._ems_public_holiday_on(self.day), holiday)
        self.assertEqual(self.Leaves._ems_public_holiday_on(self.day + timedelta(days=16)), holidays, 'a day in the middle')
        self.assertFalse(self.Leaves._ems_public_holiday_on(self.day + timedelta(days=1)), 'the next day is no holiday')
        # A teacher's own leave (with a resource) is no public holiday.
        self.Leaves.create({
            'name': 'TGBPH Own Leave', 'resource_id': self.teacher_b.resource_id.id,
            'date_from': holiday.date_from + timedelta(days=1), 'date_to': holiday.date_to + timedelta(days=1)})
        self.assertFalse(self.Leaves._ems_public_holiday_on(self.day + timedelta(days=1)))

    def test_no_absences_on_a_public_holiday(self):
        self.assertTrue(self._teaching_line(self.day)['absences'], 'control: a working day lists the absence')

        holiday = self._holiday(self.day)
        data = self.course.get_guard_duty_board_lines('0', 'morning', day=self.day)

        self.assertEqual(data['holiday'], holiday.name)
        line = self._teaching_line(self.day)
        self.assertFalse(line['absences'])
        self.assertFalse(any(cell['absences'] for cell in line['cells']), 'nobody marked away on the timetable either')
        self.assertTrue(line['cells'], 'the timetable itself is still shown')

    def test_nothing_can_be_organised_on_a_public_holiday(self):
        self._holiday(self.day)

        data = self.course.get_guard_duty_board_data('0', 'morning', day=str(self.day))
        self.assertEqual(data['holiday'], 'TGBPH Holiday')
        self.assertFalse(data['editable'])
        self.assertFalse(data['actions'])
        with self.assertRaisesRegex(UserError, 'public holiday'):
            self.env['ems.absence_cover'].board_assign(
                str(self.day), 9, 10, self.teacher_a.id, self.group_a.id, self.teacher_guard.id)

    def test_the_pdf_says_it_is_a_public_holiday(self):
        self._holiday(self.day)

        content, _content_type = self.env['ir.actions.report'].with_context(
            guard_duty_weekday='0', guard_duty_date=str(self.day), guard_duty_view='table').\
            _render_qweb_pdf('ems.report_guard_duty_board', [self.course.id])

        # The class attribute, not the stylesheet's rule.
        self.assertIn(b'class="gdb-holiday"', content)
        self.assertNotIn(self.teacher_a.name.encode(), content)
        self.assertNotIn(b'No schedule available', content)

        # The timetable tab still prints the timetable, under the same notice.
        content, _content_type = self.env['ir.actions.report'].with_context(
            guard_duty_weekday='0', guard_duty_date=str(self.day)).\
            _render_qweb_pdf('ems.report_guard_duty_board', [self.course.id])
        self.assertIn(b'class="gdb-holiday"', content)
        self.assertIn(self.teacher_a.name.encode(), content)
