# -*- coding: utf-8 -*-

from odoo import models, fields, api
from .attendance_status import attendance_status

class ems_attendance_notification(models.Model):
	_name = "ems.attendance_notification"
	_description = "Attendance notification: contains the data about notifications to the families."
	_inherit = ['ems.utils']
	
	attendance_status_id = fields.Many2one(string="Status data", comodel_name="ems.attendance_status", required=True, store=True, ondelete='cascade')
	attendance_session_id = fields.Many2one(string="Session", related="attendance_status_id.attendance_session_id") 
	student_id = fields.Many2one(string='Student', related="attendance_status_id.student_id") 
	status = fields.Selection(string="Status", related="attendance_status_id.status")
	sent_date = fields.Datetime(string="Sent on")
	sent = fields.Boolean(string="Sent", compute="_compute_sent")
	
	notes = fields.Text("Notes")
	
	@api.depends('sent_date')
	def _compute_sent(self):              
		for rec in self:
			rec.sent = rec.sent_date != False

	@api.depends('attendance_status_id')
	def _compute_display_name(self):              
		for rec in self:
			rec.display_name = "%s | %s (%s)" % (rec.attendance_session_id.display_name, rec.student_id.display_name, dict(attendance_status).get(rec.status))
	