# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError

class ems_attendance_prevision(models.Model):
	_name = "ems.attendance_prevision"
	_description = "Attendance prevision: contains the data about an expected abscence (auto-justified)."
	_inherit = ['ems.attendance_justification_base']

	attendance_session_line_ids = fields.Many2many(relation='ems_att_prev_att_ses_line_rel') 

	@api.constrains('start_date', 'end_date')
	def _check_future_dates(self):	
		for record in self:
			today = fields.Datetime.today()

			if (record.start_date and record.start_date <= today) or (record.end_date and record.end_date <= today):
				raise ValidationError("Absence prevission only works for future dates.")
			
	@api.model_create_multi
	def create(self, values):		
		just = super().create(values)
		is_admin = just.get_user_is_admin()
		is_tutor = just.get_user_is_tutor_of_self()							
		
		if not is_admin and not is_tutor:
			# TODO: localize the message
			raise ValidationError("Only the student's tutor can create attendance previsions.")
				
		return just
	
	def unlink(self):
		for rec in self:
			if not rec.user_is_admin and not rec.student_id.main_group_id in rec.teacher_id.tutorship_ids:
				raise UserError("Only the studen's tutor can remove its attendance previssions.")
			else:
				for status in rec.attendance_session_line_ids:	
					if status.status == "m_justified":	
						# TODO: localize text
						text = "Absence expected by: " + rec.teacher_id.display_name
						notes = False if status.notes == False else status.notes.replace(text, "")
						status.write({
							'status': 'm_miss',
							'notes': False if len(notes) == 0 else notes
						})
				rec.write({'attendance_session_line_ids' : [5]})	

		return super().unlink()		