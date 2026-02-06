from odoo import models, fields

class ems_base(models.AbstractModel):   
    _name = 'ems.base'
    _description = 'EMS base model\'s code)'

    user_is_admin = fields.Boolean(default=lambda self: self.get_user_is_admin(), store=False)
    user_is_tutor = fields.Boolean(default=lambda self: self.get_user_is_tutor(), store=False)   
    active = fields.Boolean(default=True)

    # TODO: Some Odoo models define this method to archive them and also their related fields. 
    #       Implement this in all our models! Needed, for example, to avoid deleting sessions. 
    def action_archive(self):
        for rec in self:
            rec.active = False    
    
    # The current user is admin. 
    def get_user_is_admin(self):	
        return self.env.user.has_group('ems.group_admin')

    # The current user is tutor of some group. 
    def get_user_is_tutor(self):
        for e in self.env.user.employee_ids:
            if e.tutorship_ids != False and len(e.tutorship_ids) > 0:
                return True
        return False

    # The current user is the tutor of the current model's instance. 
    def get_user_is_tutor_of_self(self):
        if 'tutor_id' in self.env[self._name]._fields:
            return self.tutor_id.id != False and self.tutor_id.user_id == self.env.user        
    
  