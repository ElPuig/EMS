# -*- coding: utf-8 -*-

from odoo import models, fields

class ems_settings(models.TransientModel):
   _inherit = "res.config.settings"

   # NOTE: check within company why this filed has been created as a related one, and also where is the string property defined.
   attendance_issue_status_delay = fields.Integer(related="company_id.attendance_issue_status_delay", readonly=False)
   attendance_issue_tutor_default = fields.Float(related="company_id.attendance_issue_tutor_default", readonly=False)
   strike_escalation_threshold = fields.Integer(related="company_id.strike_escalation_threshold", readonly=False)
   strike_family_notification_mode = fields.Selection(related="company_id.strike_family_notification_mode", readonly=False)
   auto_checkin_mode = fields.Selection(related="company_id.auto_checkin_mode", readonly=False)
   auto_checkout_mode = fields.Selection(related="company_id.auto_checkout_mode", readonly=False)
   auto_checkout_time = fields.Float(related="company_id.auto_checkout_time", readonly=False)
   auto_checkout_retry_until = fields.Float(related="company_id.auto_checkout_retry_until", readonly=False)
   schedule_import_first_entry_time = fields.Float(related="company_id.schedule_import_first_entry_time", readonly=False)
   schedule_import_last_entry_time  = fields.Float(related="company_id.schedule_import_last_entry_time",  readonly=False)

   current_course_id = fields.Many2one(comodel_name="ems.course", related="company_id.current_course_id", readonly=False)
   enrollment_course_id = fields.Many2one(comodel_name="ems.course", related="company_id.enrollment_course_id", readonly=False)
   # NOTE: cannot be named 'default_*' here — res.config.settings treats that prefix as a special
   # ir.default-setting field (requires a 'default_model' attribute), not a plain related field.
   schedule_framework_id = fields.Many2one(comodel_name="resource.calendar", related="company_id.default_schedule_framework_id", readonly=False, domain="[('is_framework', '=', True)]")

   director_id = fields.Many2one(comodel_name="hr.employee", related="company_id.director_id", readonly=False)

   secretariat_email = fields.Char(related="company_id.secretariat_email", readonly=False)
   center_code = fields.Char(related="company_id.center_code", readonly=False)

   limesurvey_api = fields.Char(related="company_id.limesurvey_api", readonly=False)
   limesurvey_usr = fields.Char(related="company_id.limesurvey_usr", readonly=False)
   limesurvey_pwd = fields.Char(related="company_id.limesurvey_pwd", readonly=False)
   limesurvey_gid = fields.Integer(related="company_id.limesurvey_gid", readonly=False)

   google_ws_enabled  = fields.Boolean(related="company_id.google_ws_enabled", readonly=False)
   google_ws_domain   = fields.Char(related="company_id.google_ws_domain", readonly=False)
   google_ws_ou_minor = fields.Char(related="company_id.google_ws_ou_minor", readonly=False)
   google_ws_ou_adult = fields.Char(related="company_id.google_ws_ou_adult", readonly=False)
   google_ws_ou_suspended = fields.Char(related="company_id.google_ws_ou_suspended", readonly=False)
   google_ws_ou_teacher = fields.Char(related="company_id.google_ws_ou_teacher", readonly=False)
   google_ws_ou_asp = fields.Char(related="company_id.google_ws_ou_asp", readonly=False)
   google_ws_ou_staff_suspended = fields.Char(related="company_id.google_ws_ou_staff_suspended", readonly=False)
   google_ws_dry_run  = fields.Boolean(related="company_id.google_ws_dry_run", readonly=False)
   google_ws_sa_json  = fields.Text(related="company_id.google_ws_sa_json", readonly=False)

   def set_values(self):
      super().set_values()
      if self.auto_checkout_mode != 'ems':
         return
      cron = self.env.ref('hr_attendance.hr_attendance_check_out_cron', raise_if_not_found=False)
      if not cron:
         return
      utils = self.env['ems.datetime_utils']
      cron.sudo().write({
         'active': True,
         'interval_number': 1,
         'interval_type': 'hours',
         'nextcall': utils.next_occurrence_utc(self.auto_checkout_time),
      })