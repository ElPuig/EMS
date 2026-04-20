# -*- coding: utf-8 -*-

from odoo import models, fields

class ems_settings(models.TransientModel):
   _inherit = "res.config.settings"

   # NOTE: check within company why this filed has been created as a related one, and also where is the string property defined.
   attendance_issue_status_delay = fields.Integer(related="company_id.attendance_issue_status_delay", readonly=False)
   attendance_issue_tutor_default = fields.Float(related="company_id.attendance_issue_tutor_default", readonly=False)
   auto_checkin_mode = fields.Selection(related="company_id.auto_checkin_mode", readonly=False)
   auto_checkout_mode = fields.Selection(related="company_id.auto_checkout_mode", readonly=False)
   auto_checkout_time = fields.Float(related="company_id.auto_checkout_time", readonly=False)
   schedule_import_first_entry_time = fields.Float(related="company_id.schedule_import_first_entry_time", readonly=False)
   schedule_import_last_entry_time  = fields.Float(related="company_id.schedule_import_last_entry_time",  readonly=False)

   current_course_id = fields.Many2one(comodel_name="ems.course", related="company_id.current_course_id", readonly=False)

   limesurvey_api = fields.Char(related="company_id.limesurvey_api", readonly=False)
   limesurvey_usr = fields.Char(related="company_id.limesurvey_usr", readonly=False)
   limesurvey_pwd = fields.Char(related="company_id.limesurvey_pwd", readonly=False)
   limesurvey_gid = fields.Integer(related="company_id.limesurvey_gid", readonly=False)

   def set_values(self):
      super().set_values()
      if self.auto_checkout_mode != 'ems':
         return
      cron = self.env.ref('hr_attendance.hr_attendance_check_out_cron', raise_if_not_found=False)
      if not cron:
         return
      utils = self.env['ems.datetime_utils']
      cron.sudo().write({'nextcall': utils.next_occurrence_utc(self.auto_checkout_time)})