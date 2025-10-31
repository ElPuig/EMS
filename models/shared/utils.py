import math
from datetime import datetime, timezone
from zoneinfo import ZoneInfo # requires Python >= 3.9
from odoo import models, fields

class ems_utils(models.AbstractModel):   
    _name = 'ems.utils'
    _description = 'EMS utils library (mixin)'

    user_is_admin = fields.Boolean(default=lambda self: self.get_user_is_admin(), store=False)
    user_is_tutor = fields.Boolean(default=lambda self: self.get_user_is_tutor(), store=False)   

    def time_float_to_datetime(self, time_float):
        return self.time_float_to_datetime(self.get_current_datetime(), time_float)
    
    def time_float_to_datetime(self, date, time_float):
        split_time = math.modf(time_float)        
        return datetime(date.year, date.month, date.day, int(split_time[1]), round(split_time[0]*60), 0, tzinfo=None) # Odoo demands no timezone
    
    def get_current_datetime(self):
        # NOTE: uses the user tz in order to avoid conflicts (do not use UTC!)
        user_time_zone = ZoneInfo(self.env.context["tz"])    
        return datetime.now(user_time_zone)

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
    
  