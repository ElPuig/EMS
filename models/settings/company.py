# -*- coding: utf-8 -*-

from odoo import models, fields

class ems_company(models.Model):
    _inherit = 'res.company'

	# NOTE: If created within settings, setting up a zero value erases the entry and the default value is used. 
    #		Using this approach, the delay can be zero (useful for testing purposes on a devel environment).
    #       Also, string and help values are only defined within the settings form. 
    attendance_issue_status_delay = fields.Integer(default=15)
    attendance_issue_tutor_default = fields.Float(default=21.0)

    limesurvey_api = fields.Char()
    limesurvey_usr = fields.Char()
    limesurvey_pwd = fields.Char()

    current_course_id = fields.Many2one(comodel_name="ems.course")
