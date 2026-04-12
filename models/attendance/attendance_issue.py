# -*- coding: utf-8 -*-

from odoo import models, fields, api
from .attendance_session import attendance_status_selection

class ems_attendance_issue_tutor(models.Model):
	_name = "ems.attendance_issue_tutor"
	_description = "Attendance issue (tutor): contains the data about isues that can be reviewed by the student's tutor."
	_inherit = ['ems.base']
	
	attendance_issue_student_ids = fields.One2many(string="Students", comodel_name="ems.attendance_issue_student", inverse_name="attendance_issue_tutor_id")
	notification_id = fields.Many2one(string="Notification", comodel_name="queue.job")
	tutor_id = fields.Many2one(string="Tutor", comodel_name="hr.employee")
	issue_date = fields.Date(string="Date")
	schedule_date = fields.Datetime(string="Scheduled on", related="notification_id.eta")
	status = fields.Selection(string="Status", related="notification_id.state")
	exception = fields.Text(string="Exception", related="notification_id.exc_info")
	
	def _compute_display_name(self):              
		for rec in self:
			rec.display_name = "%s: %s" % (rec.issue_date, rec.tutor_id.display_name)

	def send_notification(self):		
		self.ensure_one()				
		template = self.env.ref('ems.mail_attendance_issue_tutor', raise_if_not_found=True)	
		template.sudo().send_mail(self.id, force_send=True)						
		return True

	def remove_if_empty(self):
		for issue_student in self.attendance_issue_student_ids:
			if len(issue_student.attendance_issue_status_ids) == 0: issue_student.unlink()
		
		if len(self.attendance_issue_student_ids) == 0: 
			self.notification_id.button_cancelled()
			self.unlink()

class ems_attendance_issue_student(models.Model):
	_name = "ems.attendance_issue_student"
	_description = "Attendance issue (student): groups the attendance's issues by student."
	_inherit = ['ems.base']
	
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
	_inherit = ['ems.base']
	
	attendance_issue_student_id = fields.Many2one(string="Student notification data", comodel_name="ems.attendance_issue_student", ondelete='cascade')
	attendance_session_line_id = fields.Many2one(string="Status data", comodel_name="ems.attendance_session_line", required=True, ondelete='cascade')	
	attendance_session_id = fields.Many2one(string="Session", related="attendance_session_line_id.attendance_session_id", store=False)
	
	notification_id = fields.Many2one(string="Notification", comodel_name="queue.job")
	notification_status = fields.Selection(string="Notification status", related="notification_id.state")
	exception = fields.Text(string="Exception", related="notification_id.exc_info")

	send_to = fields.Char(string="Send to", required=True)	
	schedule_date = fields.Datetime(string="Scheduled on", related="notification_id.eta")
	subject_id = fields.Many2one(string="Subject", related="attendance_session_id.subject_id")
	group_id = fields.Many2one(string="Group", related="attendance_session_id.group_id")
	space_id = fields.Many2one(string="Space", related="attendance_session_id.space_id")
	teacher_id = fields.Many2one(string="Teacher", related="attendance_session_id.session_teacher_id")
	time_range = fields.Char(string="Time range", related="attendance_session_id.time_range")
	pending = fields.Boolean(string="Pending", compute="_compute_pending", store=False)
	rectified_by = fields.Many2one(string="Rectified by", comodel_name="ems.attendance_issue_status", ondelete='cascade')
	rectification = fields.Boolean(string="Rectification", default=False)
	
	# NOTE: tutor needed for permission purposes
	tutor_id = fields.Many2one(string='Tutor (sent to)', related="attendance_issue_student_id.student_id.tutor_id") 	

	# NOTE: We want a copy of the original status, because a miss can be justified later, but we want to keep the original notification status. 	
	attendance_status = fields.Selection(string="Attendance status", selection=attendance_status_selection)	
	notes = fields.Text(string="Notes") 

	@api.depends('attendance_session_line_id')
	def _compute_display_name(self):              
		for rec in self:
			rec.display_name = "%s | %s (%s)" % (rec.attendance_session_id.display_name, rec.attendance_issue_student_id.student_id.display_name, dict(attendance_status_selection).get(rec.attendance_status))

	@api.depends('notification_status')
	def _compute_pending(self):
		for rec in self:
			rec.pending = self.notification_status is False or self.notification_status in ["pending", "enqueued"]

	def unlink(self):
		# NOTE: button_cancel source: https://github.com/OCA/queue/blob/18.0/queue_job/models/queue_job.py
		self.notification_id.button_cancelled()
		return super().unlink()
	
	def send_notification(self):
		self.ensure_one()
		separator = "; "

		template = self.env.ref('ems.mail_attendance_issue_rectification' if self.rectification else 'ems.mail_attendance_issue_status', raise_if_not_found=True)

		# Build an email -> lang map so each recipient gets the mail in their own language.
		student = self.attendance_issue_student_id.student_id
		lang_by_email = {}
		if student.student_email:
			lang_by_email[student.student_email] = student.lang
			
		for relation in student.relation_all_ids:
			partner = relation.other_partner_id
			if partner.contact_type == 'family' and partner.email:
				lang_by_email[partner.email] = partner.lang

		# NOTE: there's no BBC field within the email template, and we want to protect personal addresses
		# when sending to multiple destinations. So, it will be send one by one setting up here the address.
		for to in self.send_to.split(separator):
			to = to.strip()
			lang = lang_by_email.get(to)
			tmpl = template.with_context(lang=lang).sudo() if lang else template.sudo()
			tmpl.send_mail(self.id, force_send=True, email_values={'email_to': to})
		
		return True
	
	def open_notification_form(self):
		return {
			'type': 'ir.actions.act_window',
			'res_model': 'queue.job',
			'res_id': self.notification_id.id,						
			'view_id': self.env.ref('queue_job.view_queue_job_form').id,
			'view_mode': 'form',
			'target': 'new'
		}  
	
	def open_exception_popup(self):
		self.ensure_one()
		return {
			'type': 'ir.actions.act_window',
			'name': 'Error details',
			'res_model': self._name,
			'res_id': self.id,
			'view_mode': 'form',
			'view_id': self.env.ref('ems.view_attendance_issue_status_exception_popup').id,
			'target': 'new', 
			'flags': {'mode': 'readonly'}
		}
