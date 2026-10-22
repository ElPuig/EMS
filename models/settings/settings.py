# -*- coding: utf-8 -*-

import logging

import requests
from markupsafe import Markup, escape

from odoo import _, api, fields, models
from odoo.tools import config

_logger = logging.getLogger(__name__)

# Every EMS release is published as a pre-release (0.y.z), so GitHub's /releases/latest never
# finds one: the newest entry of the list is the latest release.
EMS_RELEASES_URL = "https://api.github.com/repos/ElPuig/EMS/releases?per_page=5"
# Checked every time the settings open, so it must never hold the page up for long.
LATEST_VERSION_TIMEOUT = 2
# The "Check again" button reopens the settings with 'ems_check_version_again' in the context:
# an explicit request, so a slow GitHub gets more room.
LATEST_VERSION_RETRY_TIMEOUT = 10

class ems_settings(models.TransientModel):
   _inherit = "res.config.settings"

   # NOTE: check within company why this filed has been created as a related one, and also where is the string property defined.
   attendance_issue_status_delay = fields.Integer(related="company_id.attendance_issue_status_delay", readonly=False)
   attendance_issue_tutor_default = fields.Float(related="company_id.attendance_issue_tutor_default", readonly=False)
   attendance_manual_justified = fields.Boolean(related="company_id.attendance_manual_justified", readonly=False)
   strike_escalation_threshold = fields.Integer(related="company_id.strike_escalation_threshold", readonly=False)
   strike_duplicate_window = fields.Integer(related="company_id.strike_duplicate_window", readonly=False)
   strike_family_notification_mode = fields.Selection(related="company_id.strike_family_notification_mode", readonly=False)
   auto_checkin_mode = fields.Selection(related="company_id.auto_checkin_mode", readonly=False)
   ems_hos_all_attendances = fields.Boolean(related="company_id.ems_hos_all_attendances", readonly=False)
   auto_checkout_mode = fields.Selection(related="company_id.auto_checkout_mode", readonly=False)
   auto_checkout_time = fields.Float(related="company_id.auto_checkout_time", readonly=False)
   auto_checkout_retry_until = fields.Float(related="company_id.auto_checkout_retry_until", readonly=False)
   ems_full_day_hours = fields.Float(related="company_id.ems_full_day_hours", readonly=False)
   ems_health_allowance_hours = fields.Float(related="company_id.ems_health_allowance_hours", readonly=False)
   ems_absence_document_reminder_days = fields.Integer(related="company_id.ems_absence_document_reminder_days", readonly=False)
   ems_absence_document_escalation_days = fields.Integer(related="company_id.ems_absence_document_escalation_days", readonly=False)
   ems_absence_change_late_entry = fields.Boolean(related="company_id.ems_absence_change_late_entry", readonly=False)
   ems_absence_change_early_leave = fields.Boolean(related="company_id.ems_absence_change_early_leave", readonly=False)
   ems_absence_change_long_break = fields.Boolean(related="company_id.ems_absence_change_long_break", readonly=False)
   schedule_import_first_entry_time = fields.Float(related="company_id.schedule_import_first_entry_time", readonly=False)
   schedule_import_last_entry_time  = fields.Float(related="company_id.schedule_import_last_entry_time",  readonly=False)

   convalidation_start_day = fields.Integer(related="company_id.convalidation_start_day", readonly=False)
   convalidation_start_month = fields.Selection(related="company_id.convalidation_start_month", readonly=False)
   convalidation_start_time = fields.Float(related="company_id.convalidation_start_time", readonly=False)
   convalidation_end_day = fields.Integer(related="company_id.convalidation_end_day", readonly=False)
   convalidation_end_month = fields.Selection(related="company_id.convalidation_end_month", readonly=False)
   convalidation_end_time = fields.Float(related="company_id.convalidation_end_time", readonly=False)
   convalidation_legal_prior_studies = fields.Text(related="company_id.convalidation_legal_prior_studies", readonly=False)
   convalidation_legal_certificate = fields.Text(related="company_id.convalidation_legal_certificate", readonly=False)
   convalidation_legal_other = fields.Text(related="company_id.convalidation_legal_other", readonly=False)
   convalidation_appeal_text = fields.Text(related="company_id.convalidation_appeal_text", readonly=False)
   convalidation_sign_by_delegation = fields.Boolean(related="company_id.convalidation_sign_by_delegation", readonly=False)

   current_course_id = fields.Many2one(comodel_name="ems.course", related="company_id.current_course_id", readonly=False)
   enrollment_course_id = fields.Many2one(comodel_name="ems.course", related="company_id.enrollment_course_id", readonly=False)
   # NOTE: cannot be named 'default_*' here — res.config.settings treats that prefix as a special
   # ir.default-setting field (requires a 'default_model' attribute), not a plain related field.
   schedule_framework_id = fields.Many2one(comodel_name="resource.calendar", related="company_id.default_schedule_framework_id", readonly=False, domain="[('is_framework', '=', True)]")

   director_id = fields.Many2one(comodel_name="hr.employee", related="company_id.director_id", readonly=False)

   secretariat_email = fields.Char(related="company_id.secretariat_email", readonly=False)
   center_code = fields.Char(related="company_id.center_code", readonly=False)
   notice_email_signature = fields.Html(related="company_id.notice_email_signature", readonly=False)

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

   # A default, not a compute: the settings form gets its values from onchange(), which never
   # computes a field with no dependencies. latest_version is the version the database was last
   # installed/upgraded to, i.e. the one actually running, whatever the code on disk says.
   ems_version = fields.Char(
      string="Installed version",
      readonly=True,
      default=lambda self: self.env['ir.module.module'].sudo().search([('name', '=', 'ems')], limit=1).latest_version,
   )
   # Filled by default_get() with a single GitHub request for both.
   ems_latest_version = fields.Char(string="Latest version", readonly=True)
   ems_latest_version_url = fields.Char(string="Latest version URL", readonly=True)
   ems_version_status = fields.Selection(
      selection=[
         ('latest', "Up to date"),
         ('outdated', "Newer version available"),
         ('unknown', "Not checked"),
      ],
      string="Version status",
      compute="_compute_ems_version_status",
   )
   # Built here from escaped text and fixed markup only, so it needs no sanitizing (which would
   # also wrap it in a <p> and push it out of line).
   ems_version_message = fields.Html(string="Version check", compute="_compute_ems_version_status", sanitize=False)

   @api.depends('ems_version', 'ems_latest_version', 'ems_latest_version_url')
   def _compute_ems_version_status(self):
      icons = {
         'latest': Markup('<i class="fa fa-check-circle text-success me-1"></i>'),
         'outdated': Markup('<i class="fa fa-arrow-circle-up text-warning me-1"></i>'),
         'unknown': Markup('<i class="fa fa-exclamation-circle text-muted me-1"></i>'),
      }
      for settings in self:
         if not settings.ems_latest_version:
            status = 'unknown'
            message = escape(_("The latest version could not be checked."))
         elif self._version_key(settings.ems_version) >= self._version_key(settings.ems_latest_version):
            # Installed ahead of the latest release too (a development branch with the next
            # version already in its manifest): there is nothing newer to install.
            status = 'latest'
            message = escape(_("You are on the latest version."))
         else:
            status = 'outdated'
            link = Markup('<a href="%s" target="_blank">%s</a>') % (
               settings.ems_latest_version_url, settings.ems_latest_version,
            )
            message = escape(_("A newer version is available: %(version)s")) % {'version': link}
         settings.ems_version_status = status
         settings.ems_version_message = icons[status] + message

   @api.model
   def default_get(self, fields_list):
      values = super().default_get(fields_list)
      if 'ems_latest_version' in fields_list:
         again = self.env.context.get('ems_check_version_again')
         values.update(self._get_latest_ems_release(LATEST_VERSION_RETRY_TIMEOUT if again else LATEST_VERSION_TIMEOUT))
      return values

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

   @api.model
   def _get_latest_ems_release(self, timeout):
      """Field values for the newest EMS release on GitHub, both empty when it can't be read."""
      release = self._fetch_latest_ems_release(timeout)
      return {
         'ems_latest_version': release and release['version'],
         'ems_latest_version_url': release and release['url'],
      }

   @api.model
   def _fetch_latest_ems_release(self, timeout):
      """{'version', 'url'} of the newest published EMS release, or None if GitHub can't be
      reached in time. Never called during tests (no network there): they patch this method."""
      if config['test_enable']:
         return None
      try:
         response = requests.get(EMS_RELEASES_URL, timeout=timeout, headers={'Accept': 'application/vnd.github+json'})
         response.raise_for_status()
         release = next(release for release in response.json() if not release.get('draft'))
         return {'version': release['tag_name'].lstrip('v'), 'url': release['html_url']}
      except Exception as error:
         _logger.info("Could not check the latest EMS release: %s", error)
         return None

   @staticmethod
   def _version_key(version):
      return tuple(int(part) for part in (version or '').split('.') if part.isdigit())
