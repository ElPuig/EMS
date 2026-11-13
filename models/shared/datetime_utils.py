import math
from pytz import UTC
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo # requires Python >= 3.9

from odoo import _, api, models
from odoo.exceptions import UserError

# School days are read in stretches of this many days (a break is longer than one stretch only in
# summer) and never further than the limit from the start.
SCHOOL_WINDOW_DAYS = 60
SCHOOL_WINDOW_LIMIT_DAYS = 730

class EmsDatetimeUtils(models.AbstractModel):
    """Every EMS date/time conversion goes through here. The whole centre works in a single timezone,
    the company's own (its partner's 'tz'), never the acting user's nor the browser's - see
    docs/en/developers/shared/timezones.md."""
    _name = 'ems.datetime_utils'
    _description = 'EMS datetime utils'

    def company_tz_name(self):
        # sudo: anyone, the public user of the portal and kiosks included, works in this timezone,
        # while only some can read the company's own partner.
        return self.env.company.sudo().partner_id.tz or 'UTC'

    def current_tz(self):
        return ZoneInfo(self.company_tz_name())

    def time_float_to_local_datetime(self, date, time_float):
        split_time = math.modf(time_float)
        return datetime(date.year, date.month, date.day, int(split_time[1]), round(split_time[0]*60), 0, tzinfo = self.current_tz())

    def time_float_to_utc_datetime(self, date, time_float):
        local = self.time_float_to_local_datetime(date, time_float)
        return self.local_datetime_to_utc(local)

    def local_datetime_to_utc(self, dt):
        return dt.astimezone(UTC)

    def utc_datetime_to_local(self, dt):
        return dt.astimezone(self.current_tz())

    def datetime_to_odoo(self, dt):
        return dt.replace(tzinfo=None)

    def get_local_datetime(self):
        return datetime.now(self.current_tz())

    def get_local_today(self):
        return self.get_local_datetime().date()

    def utc_to_local_date(self, utc_naive):
        """The company's date at a naive UTC moment (how Odoo stores and returns datetimes). For
        code that must read "today" from the same `now` it compares with (fields.Datetime.now()),
        such as the daily summary and the task snooze."""
        return self.utc_datetime_to_local(UTC.localize(utc_naive)).date()

    @api.model
    def get_server_epoch_ms(self):
        """The server's clock, for the web client to measure how far off the browser's own is:
        a computer with a wrong clock must never decide what "now" or "today" is."""
        return int(datetime.now(UTC).timestamp() * 1000)

    def time_to_float(self, time):
        return time.hour + time.minute / 60.0

    def next_occurrence_utc(self, time_float):
        """Given a float time (local), return the next occurrence as a naive UTC datetime.
        Returns today at that time if it hasn't passed yet, otherwise tomorrow."""
        now_local = self.get_local_datetime()
        split_time = math.modf(time_float)
        target_local = now_local.replace(hour=int(split_time[1]), minute=round(split_time[0] * 60), second=0, microsecond=0)
        if target_local <= now_local:
            target_local += timedelta(days=1)
        return self.datetime_to_odoo(self.local_datetime_to_utc(target_local))

    def format_local_datetime(self, value):
        """A stored (naive UTC) datetime as the centre reads it, for emails and messages."""
        if not value:
            return ''
        return self.utc_datetime_to_local(UTC.localize(value)).strftime('%d/%m/%Y %H:%M')

    # School hours (issue #800): only the time of school days counts, every hour of them (the night
    # included), weekends, public holidays and school breaks never. 24 school hours from a Friday
    # 13:00 end on the Monday at 13:00. Counted on the company's wall clock, naive UTC in and out.

    def _ems_school_days(self, date_from, date_to):
        """The school days between both dates (included), in one search."""
        return self.env['resource.calendar.leaves']._ems_school_days(date_from, date_to)

    def _ems_local_wall(self, utc_naive):
        return self.utc_datetime_to_local(UTC.localize(utc_naive)).replace(tzinfo=None)

    def _ems_utc_from_wall(self, wall):
        return self.datetime_to_odoo(self.local_datetime_to_utc(wall.replace(tzinfo=self.current_tz())))

    def ems_add_school_hours(self, moment, hours):
        """`moment` (naive UTC) plus `hours` school hours, as naive UTC."""
        wall = self._ems_local_wall(moment)
        # Enough days for the hours plus any weekends and breaks in between; a longer break (the
        # summer one) reads the next stretch of days when this one runs out, up to a limit.
        first_day = wall.date()
        window_end = first_day + timedelta(days=int(hours / 24) * 3 + SCHOOL_WINDOW_DAYS)
        school_days = self._ems_school_days(first_day, window_end)
        remaining = timedelta(hours=hours)
        while True:
            if wall.date() > window_end:
                if wall.date() - first_day > timedelta(days=SCHOOL_WINDOW_LIMIT_DAYS):
                    raise UserError(_("There are no school days in the calendar after %s.", first_day))
                next_end = window_end + timedelta(days=SCHOOL_WINDOW_DAYS)
                school_days |= self._ems_school_days(window_end + timedelta(days=1), next_end)
                window_end = next_end
            day_end = datetime.combine(wall.date() + timedelta(days=1), datetime.min.time())
            if wall.date() in school_days:
                if remaining <= day_end - wall:
                    return self._ems_utc_from_wall(wall + remaining)
                remaining -= day_end - wall
            wall = day_end

    def ems_school_hours_between(self, start, end):
        """The school hours from `start` to `end` (naive UTC), 0 when `end` is not after it."""
        wall, wall_end = self._ems_local_wall(start), self._ems_local_wall(end)
        if wall_end <= wall:
            return 0.0
        school_days = self._ems_school_days(wall.date(), wall_end.date())
        total = timedelta()
        while wall < wall_end:
            day_end = min(datetime.combine(wall.date() + timedelta(days=1), datetime.min.time()), wall_end)
            if wall.date() in school_days:
                total += day_end - wall
            wall = day_end
        return total.total_seconds() / 3600

    def ranges_overlap(self, start_a, end_a, start_b, end_b):
        return start_a < end_b and end_a > start_b

    def time_string_to_float(self, value):
        # To convert from string like "17:45" to float like 17.75
        # Source: https://www.odoo.com/es_ES/forum/ayuda-1/convert-hours-and-minute-into-float-value-168236
        vals = value.split(':')
        _quotient, hours = divmod(float(vals[0]), 24)
        _quotient, minutes = divmod(float(vals[1]), 60)
        minutes = minutes / 60.0
        return hours + minutes