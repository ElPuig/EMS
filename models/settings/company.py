# -*- coding: utf-8 -*-

from odoo.tools import config
from odoo import models, fields, api
from cryptography.fernet import Fernet

class ems_company(models.Model):
    _inherit = 'res.company'

	# NOTE: If created within settings, setting up a zero value erases the entry and the default value is used. 
    #		Using this approach, the delay can be zero (useful for testing purposes on a devel environment).
    #       Also, string and help values are only defined within the settings form. 
    attendance_issue_status_delay = fields.Integer(default=15)
    attendance_issue_tutor_default = fields.Float(default=21.0)
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

    limesurvey_api = fields.Char()
    limesurvey_usr = fields.Char()    
    limesurvey_pwd = fields.Char(compute='_compute_limesurvey_pwd', inverse='_inverse_limesurvey_pwd', store=False)
    limesurvey_pwd_encrypted = fields.Char(copy=False)
    limesurvey_gid = fields.Integer(default=1)

    schedule_import_first_entry_time = fields.Float(default=8.0)
    schedule_import_last_entry_time  = fields.Float(default=21.0)

    current_course_id = fields.Many2one(comodel_name="ems.course")

    # --- Google Workspace (creación automática de cuentas de alumno) ---
    # Enfoque: rol de administrador personalizado asignado a la cuenta de servicio,
    # restringido a la OU /alumnos (NO domain-wide delegation, sin suplantación).
    google_ws_enabled       = fields.Boolean(string="Google Workspace enabled", default=False)
    google_ws_domain        = fields.Char(string="Google Workspace domain", default='elpuig.xeill.net')
    google_ws_ou_minor      = fields.Char(string="OU (minors)", default='/alumnos')
    google_ws_ou_adult      = fields.Char(string="OU (adults 18+)", default='/alumnos/+18')
    google_ws_dry_run       = fields.Boolean(
        string="Google Workspace dry-run", default=True,
        help="If enabled, the account creation is logged without calling the real Google API.")
    # Service Account JSON, stored encrypted (same Fernet pattern as limesurvey_pwd)
    google_ws_sa_json           = fields.Text(compute='_compute_google_ws_sa_json',
                                              inverse='_inverse_google_ws_sa_json', store=False)
    google_ws_sa_json_encrypted = fields.Char(copy=False)

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
        
        for record in self:
            if record.limesurvey_pwd_encrypted:
                try:
                    record.limesurvey_pwd = f.decrypt(record.limesurvey_pwd_encrypted.encode()).decode()
                except Exception:
                    record.limesurvey_pwd = False
            else:
                record.limesurvey_pwd = False

    def _inverse_limesurvey_pwd(self):
        key = self._get_fernet_key()
        f = Fernet(key)

        for record in self:
            if record.limesurvey_pwd:
                record.limesurvey_pwd_encrypted = f.encrypt(record.limesurvey_pwd.encode()).decode()
            else:
                record.limesurvey_pwd_encrypted = False

    @api.depends('google_ws_sa_json_encrypted')
    def _compute_google_ws_sa_json(self):
        key = self._get_fernet_key()
        f = Fernet(key)

        for record in self:
            if record.google_ws_sa_json_encrypted:
                try:
                    record.google_ws_sa_json = f.decrypt(record.google_ws_sa_json_encrypted.encode()).decode()
                except Exception:
                    record.google_ws_sa_json = False
            else:
                record.google_ws_sa_json = False

    def _inverse_google_ws_sa_json(self):
        key = self._get_fernet_key()
        f = Fernet(key)

        for record in self:
            if record.google_ws_sa_json:
                record.google_ws_sa_json_encrypted = f.encrypt(record.google_ws_sa_json.encode()).decode()
            else:
                record.google_ws_sa_json_encrypted = False
