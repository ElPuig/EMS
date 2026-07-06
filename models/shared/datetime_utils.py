import math
from pytz import UTC
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo # requires Python >= 3.9

from odoo import models

class ems_datetime_utils(models.AbstractModel):   
    _name = 'ems.datetime_utils'
    _description = 'EMS datetime utils'

    def current_tz(self):
        try:
            return ZoneInfo(self.env.context["tz"])
        except Exception:
            if self.env.company.partner_id.tz != False:
                return ZoneInfo(self.env.company.partner_id.tz)
            else:
                return ZoneInfo("UTC")

    def time_float_to_local_datetime(self, date, time_float):
        split_time = math.modf(time_float)
        return datetime(date.year, date.month, date.day, int(split_time[1]), round(split_time[0]*60), 0, tzinfo = self.current_tz())
    
    def time_float_to_utc_datetime(self, date, time_float):
        local = self.time_float_to_local_datetime(date, time_float)
        return self.local_datetime_to_utc(local)
    
    def local_datetime_to_utc(self, datetime):
        return datetime.astimezone(UTC)
    
    def utc_datetime_to_local(self, datetime):
        return datetime.astimezone(self.current_tz())
    
    def datetime_to_odoo(self, datetime):
        return datetime.replace(tzinfo=None)
    
    def get_local_datetime(self):
        return datetime.now(self.current_tz())

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

    def ranges_overlap(self, start_a, end_a, start_b, end_b):
        return start_a < end_b and end_a > start_b

    def time_string_to_float(self, value):
        # To convert from string like "17:45" to float like 17.75
		# Source: https://www.odoo.com/es_ES/forum/ayuda-1/convert-hours-and-minute-into-float-value-168236
        vals = value.split(':')
        t, hours = divmod(float(vals[0]), 24)
        t, minutes = divmod(float(vals[1]), 60)				
        minutes = (minutes) / 60.0
        return hours + minutes