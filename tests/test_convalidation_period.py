from datetime import datetime
from zoneinfo import ZoneInfo

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase

from .common import mock_outgoing_email
from .test_convalidation import (close_convalidation_period, create_convalidation_fixtures,
                                 set_convalidation_period)

MADRID = ZoneInfo('Europe/Madrid')


def utc(*local):
    """A Europe/Madrid wall-clock moment as the naive UTC datetime Odoo stores."""
    return datetime(*local, tzinfo=MADRID).astimezone(ZoneInfo('UTC')).replace(tzinfo=None)


class TestConvalidationPeriod(TransactionCase):
    """Issue #276 - the yearly period (day, month and time, no year) during which students and
    families can file convalidation requests from the portal. Staff are never limited by it."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_outgoing_email(cls)
        create_convalidation_fixtures(cls)
        cls.company = cls.env.company
        cls.company.partner_id.tz = 'Europe/Madrid'

    def _default_period(self):
        set_convalidation_period(self.env, (1, 10, 8.0), (31, 3, 23 + 59 / 60))

    def test_defaults(self):
        defaults = self.env['res.company'].default_get([
            'convalidation_start_day', 'convalidation_start_month', 'convalidation_start_time',
            'convalidation_end_day', 'convalidation_end_month', 'convalidation_end_time'])
        self.assertEqual(defaults['convalidation_start_day'], 1)
        self.assertEqual(defaults['convalidation_start_month'], '10')
        self.assertEqual(defaults['convalidation_start_time'], 8.0)
        self.assertEqual(defaults['convalidation_end_day'], 31)
        self.assertEqual(defaults['convalidation_end_month'], '3')
        self.assertEqual(round(defaults['convalidation_end_time'] * 60), 23 * 60 + 59)

    def test_period_across_the_new_year(self):
        self._default_period()
        for local, expected in (
            ((2026, 9, 30, 23, 59), False),
            ((2026, 10, 1, 7, 59), False),
            ((2026, 10, 1, 8, 0), True),
            ((2026, 12, 31, 23, 0), True),
            ((2027, 1, 15, 12, 0), True),
            ((2027, 3, 31, 23, 59, 30), True),
            ((2027, 4, 1, 0, 0), False),
            ((2027, 6, 15, 12, 0), False),
        ):
            with self.subTest(local=local):
                self.assertEqual(self.company._ems_convalidation_period_open(utc(*local)), expected)

    def test_period_within_the_year(self):
        set_convalidation_period(self.env, (1, 2, 9.0), (15, 2, 14.0))
        for local, expected in (
            ((2027, 1, 31, 12, 0), False),
            ((2027, 2, 1, 9, 0), True),
            ((2027, 2, 15, 14, 0), True),
            ((2027, 2, 15, 14, 1), False),
            ((2027, 10, 1, 12, 0), False),
        ):
            with self.subTest(local=local):
                self.assertEqual(self.company._ems_convalidation_period_open(utc(*local)), expected)

    def test_the_year_does_not_matter(self):
        self._default_period()
        for year in (2026, 2031, 2040):
            self.assertTrue(self.company._ems_convalidation_period_open(utc(year, 11, 3, 10, 0)))
            self.assertFalse(self.company._ems_convalidation_period_open(utc(year, 7, 3, 10, 0)))

    def test_next_change(self):
        """While closed, the next opening; while open, the coming closing - both in local time,
        returned in UTC."""
        self._default_period()
        next_change = self.company._ems_convalidation_period_next_change
        self.assertEqual(next_change(utc(2026, 9, 24, 12, 0)), utc(2026, 10, 1, 8, 0))
        self.assertEqual(next_change(utc(2026, 11, 2, 12, 0)), utc(2027, 3, 31, 23, 59))
        self.assertEqual(next_change(utc(2027, 2, 2, 12, 0)), utc(2027, 3, 31, 23, 59))
        self.assertEqual(next_change(utc(2027, 4, 1, 0, 0)), utc(2027, 10, 1, 8, 0))

    def test_days_must_exist(self):
        for start in ((31, 4, 8.0), (29, 2, 8.0), (0, 10, 8.0), (32, 1, 8.0)):
            with self.subTest(start=start), self.assertRaises(ValidationError):
                set_convalidation_period(self.env, start, (31, 3, 23.5))

    def test_times_must_be_within_the_day(self):
        for time in (-1.0, 24.0):
            with self.subTest(time=time), self.assertRaises(ValidationError):
                set_convalidation_period(self.env, (1, 10, time), (31, 3, 23.5))

    def test_opening_and_closing_must_differ(self):
        with self.assertRaises(ValidationError):
            set_convalidation_period(self.env, (1, 10, 8.0), (1, 10, 8.0))

    def test_staff_create_requests_while_closed(self):
        close_convalidation_period(self.env)
        self.assertFalse(self.company._ems_convalidation_period_open())
        for user in (self.head_of_studies, self.secretary):
            request = self.env['ems.convalidation'].with_user(user).create({
                'student_id': self.student.id, 'study_id': self.study.id, 'course_id': self.course.id,
                'line_ids': [(0, 0, {'subject_id': self.subject.id})],
            })
            self.assertTrue(request)
            request.sudo().unlink()
