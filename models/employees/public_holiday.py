# -*- coding: utf-8 -*-

from datetime import timedelta

from pytz import UTC

from odoo import api, models

# A school-day count never reaches further than this many calendar days per school day (weekends
# plus the longest break), the window the holidays are read for in one search.
SCHOOL_DAY_WINDOW_FACTOR = 2
SCHOOL_DAY_WINDOW_MARGIN = 120


class EmsPublicHoliday(models.Model):
    """Public holidays (resource.calendar.leaves with no resource) and the "absence" technical
    attendances they make obsolete. See docs/en/developers/employees/absence.md, "Public
    holidays"."""
    _inherit = 'resource.calendar.leaves'

    @api.model
    def _ems_public_holiday_on(self, day):
        """The public holiday on `day` (a date of the company's calendar), or an empty recordset:
        nothing is expected of anybody then (issue #740). One whose hours only touch the day
        counts too. sudo: whoever asks only learns whether the day is a holiday, and its name."""
        utils = self.env['ems.datetime_utils']
        day_start, day_end = (utils.datetime_to_odoo(utils.time_float_to_utc_datetime(when, 0.0))
                              for when in (day, day + timedelta(days=1)))
        return self.sudo().search([
            ('resource_id', '=', False), ('date_from', '<', day_end), ('date_to', '>', day_start)],
            order='date_from', limit=1)

    @api.model
    def _ems_holiday_dates(self, date_from, date_to):
        """Set of the company's calendar days between `date_from` and `date_to` (both included)
        covered by a public holiday or school break, in one search. A day the leave only touches
        counts, as in _ems_public_holiday_on(). sudo: same reason."""
        utils = self.env['ems.datetime_utils']
        start, end = (utils.datetime_to_odoo(utils.time_float_to_utc_datetime(when, 0.0))
                      for when in (date_from, date_to + timedelta(days=1)))
        days = set()
        for leave in self.sudo().search([
                ('resource_id', '=', False), ('date_from', '<', end), ('date_to', '>', start)]):
            day = utils.utc_datetime_to_local(UTC.localize(leave.date_from)).date()
            last = utils.utc_datetime_to_local(UTC.localize(leave.date_to) - timedelta(seconds=1)).date()
            while day <= last:
                days.add(day)
                day += timedelta(days=1)
        return days

    @api.model
    def _ems_nth_school_day(self, start, count, include_start=False):
        """The `count`-th school day from `start` (`start` itself counted when `include_start`),
        skipping weekends and the centre's holidays and breaks; `start` when `count` is 0. Used by
        the ex officio withdrawal circuit and the Erasmus+ call deadlines (issue #767)."""
        return self._ems_nth_school_days([start], count, include_start)[0]

    @api.model
    def _ems_school_days(self, date_from, date_to):
        """The school days between both dates (included): weekdays that are no public holiday nor
        school break, in one search."""
        closed = self._ems_holiday_dates(date_from, date_to)
        days, day = set(), date_from
        while day <= date_to:
            if day.weekday() < 5 and day not in closed:
                days.add(day)
            day += timedelta(days=1)
        return days

    @api.model
    def _ems_nth_school_days(self, starts, count, include_start=False):
        """`_ems_nth_school_day` for each of `starts`, reading the holidays once for all of them
        (one search, whatever the number of dates)."""
        if not count:
            return list(starts)
        window_end = max(starts) + timedelta(days=count * SCHOOL_DAY_WINDOW_FACTOR + SCHOOL_DAY_WINDOW_MARGIN)
        school = self._ems_school_days(min(starts), window_end)
        days = []
        for start in starts:
            day, seen = (start, 0) if include_start else (start + timedelta(days=1), 0)
            while True:
                if day in school:
                    seen += 1
                    if seen == count:
                        break
                day += timedelta(days=1)
            days.append(day)
        return days

    @api.model_create_multi
    def create(self, vals_list):
        """A public holiday always applies to every schedule: every teacher has a personal one,
        so tying it to a single schedule (the default the "Public Time Off" button of a
        schedule's form puts in the context) leaves everybody else out."""
        for vals in vals_list:
            if not vals.get('resource_id'):
                vals['calendar_id'] = False
        leaves = super().create(vals_list)
        leaves._unlink_technical_attendances_without_expected_hours()
        return leaves

    def write(self, vals):
        result = super().write(vals)
        tied_holidays = self.filtered(lambda leave: not leave.resource_id and leave.calendar_id)
        if tied_holidays:
            super(EmsPublicHoliday, tied_holidays).write({'calendar_id': False})
        self._unlink_technical_attendances_without_expected_hours()
        return result

    def _unlink_technical_attendances_without_expected_hours(self):
        """Delete the technical attendances hr.attendance._cron_absence_detection() created on
        the days these leaves cover, when those days are now left with no expected hours at all.
        Odoo recomputes the overtime of those days itself, but leaves the (red) attendance
        behind; it would have deleted it on creation had the leave already existed. A real
        attendance, or a day with hours still expected (a partial leave), is kept."""
        employee_dates = self._get_employee_dates()
        if not employee_dates:
            return
        attendance_model = self.env['hr.attendance'].sudo()
        technical_attendances = attendance_model._ems_technical_attendances_on({
            employee: [day_start for day_start, _day in dates] for employee, dates in employee_dates.items()})
        obsolete = attendance_model
        for attendance in technical_attendances:
            employee = attendance.employee_id
            day = attendance_model._get_day_start_and_day(employee, attendance.check_in)[1]
            if not employee._get_expected_attendances(*employee._ems_local_day_bounds(day)):
                obsolete |= attendance
        obsolete.unlink()
