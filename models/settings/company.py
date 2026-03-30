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

    limesurvey_api = fields.Char()
    limesurvey_usr = fields.Char()    
    limesurvey_pwd = fields.Char(compute='_compute_limesurvey_pwd', inverse='_inverse_limesurvey_pwd', store=False)
    limesurvey_pwd_encrypted = fields.Char(copy=False)
    limesurvey_gid = fields.Integer(default=1)

    current_course_id = fields.Many2one(comodel_name="ems.course")

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
