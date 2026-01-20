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
		for val in values:
			is_admin = just.get_user_is_admin()
			is_tutor = just.get_user_is_tutor_of_self()							
			
			if not is_admin and not is_tutor:
				# TODO: localize the message
				raise ValidationError("Only the student's tutor can create attendance previsions.")
			
			# if 'attendance_status_ids' in val and val.get('attendance_status_ids'):
			# 	# NOTE: it would be nice to have a link to the justification entry within the status form, but this demands an 
			# 	# extra column that will be almost always empty. So, at the moment, the text "Justified by" will be added to the
			# 	# comments sections. 
				
			# 	# TODO: localize text
			# 	text = "Justified by: " + just.teacher_id.display_name
			# 	for status in just.attendance_status_ids:	
			# 		if status.status == "m_miss":			
			# 			notes = "" if status.notes == False else status.notes + "\n"
			# 			notes += text
			# 			status.write({
			# 				'status': 'm_justified',
			# 				'notes': notes
			# 			}) 		
		return just
	
	def unlink(self):
		# for rec in self:
		# 	if not rec.user_is_admin and not rec.student_id.main_group_id in rec.teacher_id.tutorship_ids:
		# 		raise UserError("Only the studen's tutor can remove its attendance justifications.")
		# 	else:
		# 		for status in rec.attendance_status_ids:	
		# 			if status.status == "m_justified":	
		# 				# TODO: localize text
		# 				text = "Justified by: " + rec.teacher_id.display_name		
		# 				notes = False if status.notes == False else status.notes.replace(text, "")
		# 				status.write({
		# 					'status': 'm_miss',
		# 					'notes': False if len(notes) == 0 else notes
		# 				})
		# 		rec.write({'attendance_status_ids' : [5]})	

		return super().unlink()
		for rec in self:
			start_date = False if rec.start_date == False else rec.utc_datetime_to_local(rec.start_date)	
			end_date = False if rec.end_date == False else rec.utc_datetime_to_local(rec.end_date)	
			
			if rec.student_id.id and start_date and end_date:
				rec.display_name = "%s (from %02d:%02d to %02d:%02d)" % (rec.student_id.display_name, start_date.hour, start_date.minute, end_date.hour, end_date.minute)
			else:
				rec.display_name = False