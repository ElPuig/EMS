# -*- coding: utf-8 -*-

from odoo import models, fields

class ems_settings(models.TransientModel):
   _inherit = "res.config.settings"

   # NOTE: check within company why this filed has been created as a related one, and also where is the string property defined.
   attendance_issue_status_delay = fields.Integer(related="company_id.attendance_issue_status_delay", readonly=False)
   attendance_issue_tutor_default = fields.Float(related="company_id.attendance_issue_tutor_default", readonly=False)
   current_course_id = fields.Many2one(comodel_name="ems.course", related="company_id.current_course_id", readonly=False)

   limesurvey_api = fields.Char(related="company_id.limesurvey_api", readonly=False)
   limesurvey_usr = fields.Char(related="company_id.limesurvey_usr", readonly=False)
   limesurvey_pwd = fields.Char(related="company_id.limesurvey_pwd", readonly=False)
   limesurvey_gid = fields.Integer(related="company_id.limesurvey_gid", readonly=False)