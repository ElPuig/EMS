import math, pytz
from datetime import datetime
from odoo import models, fields, api

class ems_utils(models.AbstractModel):   
    _name = 'ems.utils'
    _description = 'EMS utils library (mixin)'

    user_is_admin = fields.Boolean(default=lambda self: self.get_user_is_admin(), store=False)
    user_is_tutor = fields.Boolean(default=lambda self: self.get_user_is_tutor(), store=False)   

    def time_to_float(self, time):
        return time.hour + time.minute / 60.0

    def time_float_to_utc_time_float(self, time_float):        
        dt = self.time_float_to_utc_datetime(datetime.now(), time_float)
        return self.time_to_float(dt.time())
    
    def time_float_to_utc_datetime(self, date, time_float):
        split_time = math.modf(time_float)				
        return self.convert_to_utc_date(datetime(date.year, date.month, date.day, int(split_time[1]), round(split_time[0]*60), 0))

    def convert_to_utc_date(self, local_date):
        user_time_zone = self.env.context["tz"] # can be fetched form logged in user if it is set 
        local = pytz.timezone(user_time_zone) 
        start_date = local.localize(local_date, is_dst=None) # start_date is a naive datetime 
        start_date = start_date.astimezone(pytz.utc) 		
        return datetime(start_date.year, start_date.month, start_date.day, start_date.hour, start_date.minute, 0, tzinfo=None)	

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
    
  