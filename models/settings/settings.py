# -*- coding: utf-8 -*-

from odoo import models, fields, api

class ems_settings(models.TransientModel):
   _inherit = "res.config.settings"

   course_id = fields.Many2one(string="Current course", comodel_name="ems.course", config_parameter="ems.course_id", help="Use this field to select the current course, which will be used for volatile data assignation (like the student's enrollments or the teacher's schedules).")