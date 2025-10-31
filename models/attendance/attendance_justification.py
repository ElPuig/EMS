# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError

class ems_attendance_justification(models.Model):
	_name = "ems.attendance_justification"
	_description = "Attendance justification: contains the data about an abscence justification (proof of attendance)."
	_inherit = ['ems.utils']
	
	start_date = fields.Datetime(string="Start date", required=True)
	end_date = fields.Datetime(string="End date", required=True)
	teacher_id = fields.Many2one(string="Justified by", comodel_name="hr.employee", domain="[('employee_type', '=', 'teacher')]", required=True, default=lambda self: self._default_teacher_id(), store=True, ondelete='cascade')
	student_id = fields.Many2one(string="Student", comodel_name="res.partner", domain="[('contact_type', '=', 'student')", required=True, store=True, ondelete='cascade')		
	attendance_status_ids = fields.One2many(string="Status", comodel_name="ems.attendance_status", inverse_name="attendance_justification_id")
	attachment_ids = fields.Many2many(string="Attached files", comodel_name="ir.attachment", domain="[('res_model', '=', 'ems.attendance_justification')]")	
	session_teacher_ids = fields.Many2many(string="Session teachers", comodel_name="hr.employee", store=True)
	allowed_student_ids = fields.Many2many(comodel_name='ems.attendance_schedule', store=False)	
	notes = fields.Text("Notes")

	# NOTE: this field is used to compute permissions within utils.get_user_is_tutor_of_self()	
	tutor_id = fields.Many2one(string='Tutor', related="student_id.tutor_id") 

	def _default_teacher_id(self):							
		return self.env["hr.employee"].search([("user_id", "=", self.env.uid), ("employee_type", "=", "teacher")]) or False

	@api.model_create_multi
	def create(self, values):		
		just = super(ems_attendance_justification, self).create(values)
		for val in values:
			is_admin = False
			is_tutor = just.get_user_is_tutor_of_self()
			if 'user_is_admin' in val and val.get('user_is_admin'):
				is_admin = just.user_is_admin			
				
			if not is_admin and not is_tutor:
				# TODO: localize the message
				raise ValidationError("Only the student's tutor can justify its attendances.")
			
			if 'attendance_status_ids' in val and val.get('attendance_status_ids'):
				# NOTE: it would be nice to have a link to the justification entry within the status form, but this demands an 
				# extra column that will be almost always empty. So, at the moment, the text "Justified by" will be added to the
				# comments sections. 
				
				# TODO: localize text
				text = "Justified by: " + just.teacher_id.display_name
				for status in just.attendance_status_ids:	
					if status.status == "m_miss":			
						notes = "" if status.notes == False else status.notes + "\n"
						notes += text
						status.write({
							'status': 'm_justified',
							'notes': notes
						}) 		
		return just
	
	def unlink(self):
		for rec in self:
			if not rec.user_is_admin and not rec.student_id.main_group_id in rec.teacher_id.tutorship_ids:
				raise UserError("Only the studen's tutor can remove its attendance justifications.")
			else:
				for status in rec.attendance_status_ids:	
					if status.status == "m_justified":	
						# TODO: localize text
						text = "Justified by: " + rec.teacher_id.display_name		
						notes = False if status.notes == False else status.notes.replace(text, "")
						status.write({
							'status': 'm_miss',
							'notes': False if len(notes) == 0 else notes
						})
				rec.write({'attendance_status_ids' : [5]})	

		return super().unlink()

	@api.model
	def default_get(self, fields_list):
		# TODO: unable to hide the "NEW" button to non-tutor teachers.	
		res = super().default_get(fields_list)		
		if "user_is_admin" in fields_list and  "user_is_tutor" in fields_list:
			# This happens when opening the form, when storing fires again but field per field			
			if not (res["user_is_admin"] or res["user_is_tutor"]):
				# TODO: localize the message
				raise UserError("Only tutors can justify student's attendances.")		
		return res

	@api.onchange("teacher_id")
	def _onchange_allowed_student_ids(self):	
		for rec in self:			
			allowed = []			
			where = [('contact_type', '=', 'student')]
			
			students = self.env["res.partner"].search(where)			
			for s in students:
				if self.env.user.has_group('ems.group_admin') or s.main_group_id in rec.teacher_id.tutorship_ids:
					allowed.append(s.id)

			rec.write({'allowed_student_ids' : [(6, 0, allowed)]})	
			
	@api.onchange("student_id", "start_date", "end_date")
	def _onchange_attendance_status_ids(self):	
		for rec in self:
			if rec.student_id.id != False and rec.start_date != False and rec.end_date != False:								
				statuses = self.env["ems.attendance_status"].search([
					("status", "=", "m_miss"), 
					("student_id", "=", rec.student_id.id), 
					("attendance_session_id.date", ">=", rec.start_date), 
					("attendance_session_id.date", "<=", rec.end_date)
				]) or False

				status_ids = []
				teacher_ids = []
				if statuses != False:		
					for status in statuses:
						status_start_date = self.time_float_to_datetime(status.attendance_session_id.date, status.attendance_session_id.start_time)
						status_end_date = self.time_float_to_datetime(status.attendance_session_id.date, status.attendance_session_id.end_time)
						if (status_start_date >= rec.start_date and status_end_date <= rec.end_date) or (status_start_date <= rec.start_date and status_end_date >= rec.end_date):
							status_ids.append(status.id)
							teacher_ids.append(status.attendance_session_id.template_teacher_id.id)
							teacher_ids.append(status.attendance_session_id.session_teacher_id.id)
				
				teacher_ids = list(set(teacher_ids)) # removing dupes
				rec.write({
					'attendance_status_ids' : [(6, 0, status_ids)],
					'session_teacher_ids' : [(6, 0, teacher_ids)],
				})
			
	@api.depends('student_id', 'start_date', 'end_date')
	def _compute_display_name(self):              
		for rec in self:
			rec.display_name = "%s (from %s to %s)" % (rec.student_id.display_name, rec.start_date, rec.end_date)
	