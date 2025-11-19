# -*- coding: utf-8 -*-

from odoo import models, fields, api

class ems_settings(models.TransientModel):
   _inherit = "res.config.settings"

   # TODO: this field should be stores within company and used in the same way as attendance_issue_status_delay?
   #       this has the advantage of company specific config (and not global one, whith right now is not needed).
   course_id = fields.Many2one(string="Current course", comodel_name="ems.course", config_parameter="ems.course_id")
    
   # NOTE: check within company why this filed has been created as a related one, and also where is the string property defined.
   attendance_issue_status_delay = fields.Integer(related="company_id.attendance_issue_status_delay", readonly=False)
   attendance_issue_tutor_default = fields.Float(related="company_id.attendance_issue_tutor_default", readonly=False)