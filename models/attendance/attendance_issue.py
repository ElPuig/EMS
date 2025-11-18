# -*- coding: utf-8 -*-

from odoo import models, fields, api
from .attendance_status import attendance_status

class ems_attendance_issue_tutor(models.Model):
	_name = "ems.attendance_issue_tutor"
	_description = "Attendance issue (tutor): contains the data about isues that can be reviewed by the student's tutor."
	_inherit = ['ems.utils']
	
	attendance_issue_student_ids = fields.One2many(string="Students", comodel_name="ems.attendance_issue_student", inverse_name="attendance_issue_tutor_id")
	notification_id = fields.Many2one(string="Notification", comodel_name="queue.job")
	tutor_id = fields.Many2one(string="Tutor", comodel_name="hr.employee")
	issue_date = fields.Date(string="Date")
	schedule_date = fields.Datetime(string="Scheduled on", related="notification_id.eta")
	status = fields.Selection(string="Status", compute="_compute_status", selection=[("pending", "Pending"), ("sent", "Sent"), ("error", "Error")], store=True)
	exception = fields.Text(string="Exception", related="notification_id.exc_info")

	@api.depends("exception", "notification_id.date_started")
	def _compute_status(self):              
		for rec in self:
			if rec.notification_id.date_done:
				rec.status = "sent"
			elif rec.exception:
				rec.status = "error"
			else:
				rec.status = "pending"

	def _compute_display_name(self):              
		for rec in self:
			rec.display_name = "%s: %s" % (rec.issue_date, rec.tutor_id.display_name)

	def send_notification(self):		
		self.ensure_one()		

		try:
			template = self.env.ref('ems.mail_attendance_issue_tutor', raise_if_not_found=True)	
			template.sudo().send_mail(self.id, force_send=True)				
			#self.sudo().write({'sent_date': datetime.now()})					
		except ValueError as e:		
			return False # Silent			
		return True

class ems_attendance_issue_student(models.Model):
	_name = "ems.attendance_issue_student"
	_description = "Attendance issue (student): groups the attendance's issues by student."
	_inherit = ['ems.utils']
	
	attendance_issue_tutor_id = fields.Many2one(string="Tutor notification data", comodel_name="ems.attendance_issue_tutor", ondelete='cascade')
	attendance_issue_status_ids = fields.One2many(string="Sessions", comodel_name="ems.attendance_issue_status", inverse_name="attendance_issue_student_id")
	student_id = fields.Many2one(string="Student", comodel_name="res.partner", domain="[('contact_type', '=', 'student')]", ondelete='cascade')
	date = fields.Date(string="Date", related="attendance_issue_tutor_id.issue_date")

	@api.depends('attendance_issue_tutor_id')
	def _compute_display_name(self):              
		for rec in self:
			rec.display_name = "%s | %s" % (rec.student_id.display_name, rec.date)

class ems_attendance_issue_status(models.Model):
	_name = "ems.attendance_issue_status"
	_description = "Attendance issue (status): contains the data about an attendance issue."
	_inherit = ['ems.utils']
	
	attendance_issue_student_id = fields.Many2one(string="Student notification data", comodel_name="ems.attendance_issue_student", ondelete='cascade')
	attendance_status_id = fields.Many2one(string="Status data", comodel_name="ems.attendance_status", required=True, ondelete='cascade')	
	attendance_session_id = fields.Many2one(string="Session", comodel_name="ems.attendance_session", required=True, ondelete='cascade')
	notification_id = fields.Many2one(string="Notification", comodel_name="queue.job")

	# NOTE: We want a copy of the original status, because a miss can be justified later, but we want to keep the original notification status. 	
	status = fields.Selection(string="Status", compute="_compute_status", selection=attendance_status)	
	send_to = fields.Char(string="Send to", required=True)	
	sent_date = fields.Datetime(string="Sent on", related="notification_id.date_done")
	notes = fields.Text(string="Notes", related="attendance_status_id.notes") 
	subject_id = fields.Many2one(string="Subject", related="attendance_session_id.subject_id")
	group_id = fields.Many2one(string="Group", related="attendance_session_id.group_id")
	space_id = fields.Many2one(string="Space", related="attendance_session_id.space_id")
	teacher_id = fields.Many2one(string="Teacher", related="attendance_session_id.session_teacher_id")
	time_range = fields.Char(string="Time range", related="attendance_session_id.time_range")
	
	# NOTE: tutor needed for permission purposes
	tutor_id = fields.Many2one(string='Tutor (sent to)', related="attendance_issue_student_id.student_id.tutor_id") 
	
	@api.depends("attendance_status_id")
	def _compute_status(self):
		for rec in self:
			rec.status = rec.attendance_status_id.status	

	@api.depends('attendance_status_id')
	def _compute_display_name(self):              
		for rec in self:
			rec.display_name = "%s | %s (%s)" % (rec.attendance_session_id.display_name, rec.attendance_issue_student_id.student_id.display_name, dict(attendance_status).get(rec.status))

	def send_notification(self):		
		self.ensure_one()		
		separator = "; "

		try:
			template = self.env.ref('ems.mail_attendance_issue_status', raise_if_not_found=True)						
			# NOTE: there's no BBC field within the email template, and we want to protect personal addresses 
			# when sending to multiple destinations. So, it will be send one by one setting up here the address.
			for to in self.send_to.split(separator):
				template.sudo().send_mail(self.id, force_send=True, email_values={'email_to': to})
				
			#self.sudo().write({'sent_date': datetime.now()})					
		except ValueError as e:		
			return False # Silent			
		return True
	
	def display_notification(self):
		return {
			'type': 'ir.actions.act_window',
			'res_model': 'queue.job',
			'res_id': self.notification_id.id,						
			'view_id': self.env.ref('queue_job.view_queue_job_form').id,
			'view_mode': 'form',
			'target': 'new'
		}  
