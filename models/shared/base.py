import hashlib, traceback
from markupsafe import Markup
from odoo import models, fields, _

class ems_base(models.AbstractModel):   
    _name = 'ems.base'
    _description = 'EMS base model\'s code)'
    _inherit = ['mail.thread', 'mail.activity.mixin']

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
    
    # Returns a hashcode which is persistent between execution (not like the Python's native one).
    def persistent_hash(self, data):
        bytes = str(data).encode('utf-8')
        hash = hashlib.sha256(bytes)
        return hash.hexdigest()
    
    # To send a notification (won't be sent till a BBDD commit)
    def notify(self, title, message, type, sticky=False):
        # types: success; warning; danger; info
        self.env["bus.bus"]._sendone(
            self.env.user.partner_id, "simple_notification", {
                "title": title, 
                "message": message, 
                "type": type,
                "sticky": sticky
            }
        )

    # Writes a regular log message in the chatter. 
    def chatter(self, message):
        self.message_post(
            body = message,
            message_type = 'notification',
            subtype_xmlid='mail.mt_note'
        )	

    # Writes an exception (using a red warning block) in the chatter.
    def chatter_exception(self, exception):
        self.chatter(
            Markup(f"""
                <div class="alert alert-danger mb-0" role="alert">
                    <h5 class="alert-heading mb-1">
                        <i class="fa fa-exclamation-triangle me-1"></i> 
                        {_("An error occurred during the process")}
                    </h5>
                    <p class="mb-2">{exception}</p>
                    <hr class="mt-1 mb-2">
                    
                    <details>
                        <summary class="text-muted fw-bold" style="cursor: pointer;">
                            <i class="fa fa-bug me-1"></i> {_("See technical details (Exception)")}
                        </summary>
                        
                        <pre class="mt-2 p-2 bg-light border text-dark rounded" style="font-size: 0.85em; white-space: pre-wrap; max-height: 250px; overflow-y: auto;">{traceback.format_exc()}</pre>
                    </details>
                </div>
            """)
        )