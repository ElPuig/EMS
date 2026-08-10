# -*- coding: utf-8 -*-

import logging

from odoo.tools import config
from odoo import models, fields, api
from cryptography.fernet import Fernet

_logger = logging.getLogger(__name__)

class ems_company(models.Model):
    _inherit = 'res.company'

	# NOTE: If created within settings, setting up a zero value erases the entry and the default value is used. 
    #		Using this approach, the delay can be zero (useful for testing purposes on a devel environment).
    #       Also, string and help values are only defined within the settings form. 
    attendance_issue_status_delay = fields.Integer(default=15)
    attendance_issue_tutor_default = fields.Float(default=21.0)
    strike_escalation_threshold = fields.Integer(default=3)
    auto_checkin_mode = fields.Selection(
        selection=[
            ('disabled', 'Disabled'),
            ('first',    'First (first scheduled working hour)'),
            ('start',    'Start (start of the current attendance scheduled session)'),
            ('current',  'Current (current time)'),
        ],
        default='disabled',
    )
    auto_checkout_mode = fields.Selection(
        selection=[('native', 'Native (after maximum hours)'), ('ems', 'EMS (at last scheduled hour)')],
        default='native',
    )
    auto_checkout_time = fields.Float(default=1.0)
    auto_checkout_retry_until = fields.Float(default=6.0)

    limesurvey_api = fields.Char()
    limesurvey_usr = fields.Char()    
    limesurvey_pwd = fields.Char(compute='_compute_limesurvey_pwd', inverse='_inverse_limesurvey_pwd', store=False)
    limesurvey_pwd_encrypted = fields.Char(copy=False)
    limesurvey_gid = fields.Integer(default=1)

    schedule_import_first_entry_time = fields.Float(default=8.0)
    schedule_import_last_entry_time  = fields.Float(default=21.0)

    current_course_id = fields.Many2one(comodel_name="ems.course")
    default_schedule_framework_id = fields.Many2one(
        comodel_name="resource.calendar", domain="[('is_framework', '=', True)]", required=True,
        default=lambda self: self.env.ref('ems.schedule_framework_default', raise_if_not_found=False))

    director_id = fields.Many2one(
        comodel_name="hr.employee", string="Director",
        help="The person acting as the center's Director. Every top-level department's Manager "
             "(Head of Studies/Deputy) will have their own Manager set to this employee automatically.")

    secretariat_email = fields.Char()

    # Official Departament d'Educació center code (e.g. '8028047'). Used by the GEDAC
    # applicant import to keep only the rows assigned to this center.
    center_code = fields.Char(string="Center code")

    # --- Google Workspace (creación automática de cuentas de alumno) ---
    # Enfoque: rol de administrador personalizado asignado a la cuenta de servicio,
    # restringido a la OU /alumnos (NO domain-wide delegation, sin suplantación).
    google_ws_enabled       = fields.Boolean(string="Google Workspace enabled", default=False)
    google_ws_domain        = fields.Char(string="Google Workspace domain", default='elpuig.xeill.net')
    google_ws_ou_minor      = fields.Char(string="OU (minors)", default='/alumnos')
    google_ws_ou_adult      = fields.Char(string="OU (adults 18+)", default='/alumnos/+18')
    google_ws_ou_suspended  = fields.Char(string="OU (suspended)", default='/alumnos/bajas',
        help="OU where suspended (former) students are moved.")
    # --- Staff accounts (teachers and ASP) ---
    google_ws_ou_teacher    = fields.Char(string="OU (teachers)", default='/claustro/doble-factor-autenticación',
        help="OU where teacher accounts are created.")
    google_ws_ou_asp        = fields.Char(string="OU (ASP)", default='/pas',
        help="OU where Administrative and Services Personnel accounts are created.")
    google_ws_ou_staff_suspended = fields.Char(string="OU (staff suspended)", default='/claustro/bajas',
        help="OU where suspended (former) staff accounts are moved.")
    google_ws_dry_run       = fields.Boolean(
        string="Google Workspace dry-run", default=True,
        help="If enabled, the account creation is logged without calling the real Google API.")
    # Service Account JSON, stored encrypted (same Fernet pattern as limesurvey_pwd)
    google_ws_sa_json           = fields.Text(compute='_compute_google_ws_sa_json',
                                              inverse='_inverse_google_ws_sa_json', store=False)
    google_ws_sa_json_encrypted = fields.Char(copy=False)

    def _sync_current_course_flag(self):
        """Keep ems.course.is_current in sync with the configured current course
        (the "Current course" setting, current_course_id). Selecting the course in the
        settings marks it as the operational one and clears the flag on any other course,
        so all the code that relies on is_current stays consistent with the setting."""
        Course = self.env['ems.course']
        for company in self:
            course = company.current_course_id
            (Course.search([('is_current', '=', True)]) - course).write({'is_current': False})
            if course and not course.is_current:
                course.is_current = True

    @api.model_create_multi
    def create(self, vals_list):
        companies = super().create(vals_list)
        companies._sync_current_course_flag()
        return companies

    def write(self, vals):
        old_directors = {company: company.director_id for company in self}
        res = super().write(vals)
        if 'current_course_id' in vals:
            self._sync_current_course_flag()
        if 'director_id' in vals:
            for company in self:
                old_director = old_directors[company]
                self.env['hr.department'].search([
                    ('is_top_level', '=', True), ('company_id', '=', company.id),
                ]).manager_id._compute_parent_id()
                (old_director | company.director_id).update_director_role()
        return res

    def _register_hook(self):
        """Warns once per server start if this database has never declared whether it's a
        development or a production environment (see 'ems.environment_type', set by
        install.sh/devel.sh/deploy.sh - CLAUDE.md's own 'Development vs. production environment
        declaration' section has the full picture). Skipped during automated test runs
        (config['test_enable']) - a throwaway test database never runs any of those scripts and
        never needs to."""
        super()._register_hook()
        if config['test_enable']:
            return
        if not self.env['ir.config_parameter'].sudo().get_param('ems.environment_type'):
            _logger.warning(
                "EMS: 'ems.environment_type' is not set on this database - neither install.sh, "
                "devel.sh nor deploy.sh has declared this environment yet. If this is a local "
                "development box, run devel.sh before interacting with any real data restored "
                "onto it (it redirects every stored email to your own inbox, avoiding accidental "
                "sends to real people); if this is a real deployment, run deploy.sh, or set "
                "ir.config_parameter 'ems.environment_type' to 'production' directly."
            )

    @api.model
    def _get_fernet_key(self):
        key = config.get('secret') 
        if not key:
            raise ValueError("Unable to locate a 'secret' value within odoo.conf")
        return key

    @api.depends('limesurvey_pwd_encrypted')
    def _compute_limesurvey_pwd(self):        
        key = self._get_fernet_key()
        f = Fernet(key)
        
        for company in self:
            if company.limesurvey_pwd_encrypted:
                try:
                    company.limesurvey_pwd = f.decrypt(company.limesurvey_pwd_encrypted.encode()).decode()
                except Exception:
                    company.limesurvey_pwd = False
            else:
                company.limesurvey_pwd = False

    def _inverse_limesurvey_pwd(self):
        key = self._get_fernet_key()
        f = Fernet(key)

        for company in self:
            if company.limesurvey_pwd:
                company.limesurvey_pwd_encrypted = f.encrypt(company.limesurvey_pwd.encode()).decode()
            else:
                company.limesurvey_pwd_encrypted = False

    @api.depends('google_ws_sa_json_encrypted')
    def _compute_google_ws_sa_json(self):
        key = self._get_fernet_key()
        f = Fernet(key)

        for company in self:
            if company.google_ws_sa_json_encrypted:
                try:
                    company.google_ws_sa_json = f.decrypt(company.google_ws_sa_json_encrypted.encode()).decode()
                except Exception:
                    company.google_ws_sa_json = False
            else:
                company.google_ws_sa_json = False

    def _inverse_google_ws_sa_json(self):
        key = self._get_fernet_key()
        f = Fernet(key)

        for company in self:
            if company.google_ws_sa_json:
                company.google_ws_sa_json_encrypted = f.encrypt(company.google_ws_sa_json.encode()).decode()
            else:
                company.google_ws_sa_json_encrypted = False
