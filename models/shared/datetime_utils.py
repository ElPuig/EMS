import math
from pytz import UTC
from datetime import datetime
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