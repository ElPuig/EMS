import math
from pytz import UTC
from datetime import datetime
from zoneinfo import ZoneInfo # requires Python >= 3.9

from odoo import models, fields

class ems_utils(models.AbstractModel):   
    _name = 'ems.utils'
    _description = 'EMS utils library (mixin)'

    user_is_admin = fields.Boolean(default=lambda self: self.get_user_is_admin(), store=False)
    user_is_tutor = fields.Boolean(default=lambda self: self.get_user_is_tutor(), store=False)   
    active = fields.Boolean(default=True)

    # TODO: Some Odoo models define this method to archive them and also their related fields. 
    #       Implement this in all our models! Needed, for example, to avoid deleting sessions. 
    def action_archive(self):
        for rec in self:
            rec.active = False    

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
    
    def get_user_is_admin(self):	
        return self.env.user.has_group('ems.group_admin')

    def get_user_is_tutor(self):
        for e in self.env.user.employee_ids:
            if e.tutorship_ids != False and len(e.tutorship_ids) > 0:
                return True
        return False

    def get_user_is_tutor_of_self(self):
        if 'tutor_id' in self.env[self._name]._fields:
            return self.tutor_id.id != False and self.tutor_id.user_id == self.env.user        
    
  