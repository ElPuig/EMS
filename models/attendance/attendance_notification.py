# -*- coding: utf-8 -*-

from odoo import models, fields, api
from .attendance_status import attendance_status

class ems_attendance_notification(models.Model):
	_name = "ems.attendance_notification"
	_description = "Attendance notification (header): contains the data about notifications to the group's tutor."
	_inherit = ['ems.utils']
	
	attendance_session_id = fields.Many2one(string="Session", comodel_name="ems.attendance_session", ondelete='cascade')
	attendance_notification_line_ids = fields.One2many(string="Status", comodel_name="ems.attendance_notification_line", inverse_name="attendance_notification_id")
	tutor_id = fields.Many2one(string="Tutor", comodel_name="hr.employee")	
	sent_date = fields.Datetime(string="Sent on (to tutor)")
	sent = fields.Boolean(string="Sent", compute="_compute_sent")
	notes = fields.Text("Notes")
	
	@api.depends('sent_date')
	def _compute_sent(self):              
		for rec in self:
			rec.sent = rec.sent_date != False

	@api.depends('attendance_session_id')
	def _compute_display_name(self):              
		for rec in self:
			rec.display_name = "%s" % rec.attendance_session_id.display_name

class ems_attendance_notification_line(models.Model):
	_name = "ems.attendance_notification_line"
	_description = "Attendance notification (line): contains the data about notifications to the families."
	_inherit = ['ems.utils']
	
	attendance_notification_id = fields.Many2one(string="Header", comodel_name="ems.attendance_notification", ondelete='cascade')
	attendance_status_id = fields.Many2one(string="Status data", comodel_name="ems.attendance_status", required=True, store=True, ondelete='cascade')	
	student_id = fields.Many2one(string='Student', related="attendance_status_id.student_id") 	
		
	status = fields.Selection(string="Status", compute="_compute_status", selection=attendance_status)	
	send_to = fields.Char(string="Send to", required=True)	
	sent_date = fields.Datetime(string="Sent on")
	sent = fields.Boolean(string="Sent", compute="_compute_sent")
	notes = fields.Text("Notes", related="attendance_status_id.notes") 
	
	# NOTE: tutor needed for permission purposes
	tutor_id = fields.Many2one(string='Tutor (sent to)', related="student_id.tutor_id") 

	
	
	@api.depends("attendance_status_id")
	def _compute_status(self):
		for rec in self:
			rec.status = rec.attendance_status_id.status
			#rec.status = dict(attendance_status).get(rec.attendance_status_id.status)
	
	@api.depends('sent_date')
	def _compute_sent(self):              
		for rec in self:
			rec.sent = rec.sent_date != False

	@api.depends('attendance_status_id')
	def _compute_display_name(self):              
		for rec in self:
			rec.display_name = "%s | %s (%s)" % (rec.attendance_notification_id.attendance_session_id.display_name, rec.student_id.display_name, rec.status)