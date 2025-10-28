# -*- coding: utf-8 -*-

from odoo import models, fields, api

class ems_settings(models.TransientModel):
   _inherit = "res.config.settings"

   # TODO: this field should be stores within company and used in the same way as attendance_notification_delay?
   #       this has the advantage of company specific config (and not global one, whith right now is not needed).
   course_id = fields.Many2one(string="Current course", comodel_name="ems.course", config_parameter="ems.course_id")
    
   # NOTE: check within company why this filed has been created as a related one
   attendance_notification_delay = fields.Integer(string="Attendance notification delay (in minutes)", related="company_id.attendance_notification_delay", readonly=False)