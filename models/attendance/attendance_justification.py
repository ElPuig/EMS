# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.translate import _lt

JUSTIFICATION_CAPTION = _lt("Absence justified by: ")
PREVISION_CAPTION = _lt("Absence expected by: ")

class ems_attendance_justification(models.Model):
	_name = "ems.attendance_justification"
	_description = "Attendance justification: contains the data about an abscence justification (proof of attendance)."
	_inherit = ['ems.base', 'ems.datetime_utils']
	
	start_date = fields.Datetime(string="Start date", required=True)
	end_date = fields.Datetime(string="End date", required=True)
	teacher_id = fields.Many2one(string="Justified by", comodel_name="hr.employee", domain="[('employee_type', '=', 'teacher')]", required=True, default=lambda self: self._default_teacher_id(), store=True, ondelete='cascade')
	student_id = fields.Many2one(string="Student", comodel_name="res.partner", domain="[('contact_type', '=', 'student')", required=True, store=True, ondelete='cascade')	
	attachment_ids = fields.Many2many(string="Attached files", comodel_name="ir.attachment", domain="[('res_model', '=', 'ems.attendance_justification')]")	
	
	# NOTE: Many2many needed in order to update values (when Many2one used, removed values when changing filters removes also the status entries).
	# NOTE: relation name should be forced to <63 chars (PSQL restriction).
	attendance_session_line_ids = fields.Many2many(string="Affected sessions", comodel_name="ems.attendance_session_line") 	
	session_teacher_ids = fields.Many2many(string="Affected teachers", comodel_name="hr.employee", compute='_compute_session_teacher_ids', store=True, readonly=False)    
	allowed_student_ids = fields.Many2many(comodel_name='res.partner', store=False)	
	notes = fields.Text("Notes")

	# NOTE: this field is used to compute permissions within utils.get_user_is_tutor_of_self()	
	tutor_id = fields.Many2one(string='Tutor', related="student_id.tutor_id") 

	@api.depends('attendance_session_line_ids')
	def _compute_session_teacher_ids(self):
		for record in self:			
			tt_id = record.attendance_session_line_ids.mapped('attendance_session_id.template_teacher_id.id')
			st_id = record.attendance_session_line_ids.mapped('attendance_session_id.session_teacher_id.id')
			regs = list(set(tt_id + st_id))
			
			# Storing both sets but removing dupes
			record.session_teacher_ids = [(6, 0, regs)]			
			
	def _default_teacher_id(self):							
		return self.env["hr.employee"].search([("user_id", "=", self.env.uid), ("employee_type", "=", "teacher")]) or False

	@api.constrains('student_id', 'start_date', 'end_date')
	def _check_time_overlap(self):
		for record in self:
			if record.start_date and record.end_date and record.start_date >= record.end_date:
				raise ValidationError("The completion date must be later than the start date.")

			domain = [
				('student_id', '=', record.student_id.id),
				('id', '!=', record.id),                  
				('start_date', '<', record.end_date),     
				('end_date', '>', record.start_date),     
			]
			
			if self.search_count(domain) > 0:
				raise ValidationError(
					f"The student {record.student_id.name} has another justification which overlaps with the current one."
				)
					
	@api.model
	def default_get(self, fields_list):
		# TODO: unable to hide the "NEW" button to non-tutor teachers.	
		res = super().default_get(fields_list)		
		if "user_is_admin" in fields_list and  "user_is_tutor" in fields_list:
			# This happens when opening the form, when storing fires again but field per field			
			if not (res["user_is_admin"] or res["user_is_tutor"]):
				raise UserError(_("Only tutors can justify student's attendances."))		
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

			rec.allowed_student_ids = [(6, 0, allowed)]	

	# NOTE: only fired when adding from the form (so wont be fire), so won't be fired twice when 
	# using the regular attendance form. 
	@api.onchange("student_id", "start_date", "end_date") 
	def _onchange_attendance_session_line_ids(self):	
		for rec in self:
			if rec.student_id.id != False and rec.start_date != False and rec.end_date != False:	
				# NOTE: Because changing dates is allowed, already justified abscences must be included
				# 		(already justified will fail due overlapping check).
				statuses = self.env["ems.attendance_session_line"].search([
					'|',
					("status", "=", "m_miss"),
					("status", "=", "m_justified"), 
					("student_id", "=", rec.student_id.id), 
					("attendance_session_id.date", ">=", rec.start_date), 
					("attendance_session_id.date", "<=", rec.end_date)
				]) or False

				status_ids = []
				if statuses != False:		
					for status in statuses:
						status_start_date = rec.utc_datetime_to_local(status.attendance_session_id.start_date)
						status_end_date = rec.utc_datetime_to_local(status.attendance_session_id.end_date)										
						just_start_date = rec.utc_datetime_to_local(rec.start_date)
						just_end_date = rec.utc_datetime_to_local(rec.end_date)
												
						if not (status_end_date <= just_start_date or just_end_date < status_start_date):
							status_ids.append(status.id)							
							# NOTE: shoudl be done with write, direct attribute assignation does not work if the current
							#		item is beeing created (the ID will be something like NEW_xxxx).
							#status.attendance_justification_id = [(4, rec.id)]
							status.write({								
								"attendance_justification_id" : [(4, rec.id)]						
							})
				
				rec.attendance_session_line_ids = [(6, 0, status_ids)]
			
	@api.depends('student_id', 'start_date', 'end_date')
	def _compute_display_name(self):              
		for rec in self:
			start_date = False if rec.start_date == False else rec.utc_datetime_to_local(rec.start_date)	
			end_date = False if rec.end_date == False else rec.utc_datetime_to_local(rec.end_date)	
			
			if rec.student_id.id and start_date and end_date:
				rec.display_name = "%s (from %02d:%02d to %02d:%02d)" % (rec.student_id.display_name, start_date.hour, start_date.minute, end_date.hour, end_date.minute)
			else:
				rec.display_name = False

	def _check_permissions(self):
		is_admin = self.get_user_is_admin()
		is_tutor = self.get_user_is_tutor_of_self()							
		return is_admin or is_tutor

	def get_current_justifications(self, start_date, end_date):
		return self.sudo().env["ems.attendance_justification"].search([
			("start_date", "<", end_date),
			("end_date", ">", start_date),
		])
		
	# NOTE: Called also from attendance_session (when creating lines as absence_prevission). 
	# 		Write and create methods always want a dictionary (values) to know which fields must be updated. 
	#       WARNING: line is a dictionary when called from attendance_session, but a model when called from attendance_justification!
	def perform_justification(self, line, prevision=False):	
		if hasattr(line, '_name'):
			# Is a model (the line is beeing changed from attendance_justification, so a justification is beeing made).
			vals = line.copy_data()[0]
			vals['id'] = line.id
		else:
			# Is a dictionary (the line is beeing created from attendance_session, so a prevision is beeing made).
			vals = line.copy()

		text = PREVISION_CAPTION if prevision else JUSTIFICATION_CAPTION		
		notes = "" if vals["notes"] is None or vals["notes"] == False else vals["notes"] + "\n"
		
		# Must ensure that no field is beeing removed, just edited, otherwise line creation could fail if called from attendance_session.
		vals["status"] = "m_justified"
		vals["notes"] = notes + text + self.teacher_id.display_name
		vals["attendance_prevision_id" if prevision else "attendance_justification_id"] = self
		return vals	

	def remove_justification(self, line):
		# Given an attendance_session_line, changes the values to remove a justification (does not write).
		# NOTE: this method uses always line as a model, removing a justification always work with already existing lines.
		return {
			"status": "m_miss",
			"notes": False,
			"attendance_justification_id": None,
			"attendance_prevision_id": None
		}	
	
	@api.model_create_multi
	def create(self, values):	
		# NOTE: don't worry, wont be saved if there's an exception (wihtin transaction)
		records = super().create(values)
		for just in records:
			if not just._check_permissions():
				raise ValidationError(_("Only the student's tutor can justify its attendances."))
						
			for line in just.attendance_session_line_ids:	
				if line.status == "m_miss":	
					line.write(just.perform_justification(line))
		return records
	
	def write(self, vals):	
		old_lines_map = {}
		for rec in self:
			old_lines_map[rec.id] = set(rec.attendance_session_line_ids)

		# Must be saved after storing previous data
		updated = super(ems_attendance_justification, self).write(vals)
		if 'start_date' in vals or 'end_date' in vals:
			# This method is called when an attendance session is created (because justification is beeing linked to the session)
			# so only on trying to update dates, the permissions must be checked to avoid unauthorized changes. 
			if not self._check_permissions():
				raise UserError(_("Only the student's tutor can update its attendance justifications."))
			
			for rec in self:				
				old_lines = old_lines_map.get(rec.id, set())
				new_lines = set(rec.attendance_session_line_ids)
				
				for ol in old_lines:
					# Removing old justifications					
					if ol not in new_lines:
						ol.write(rec.remove_justification(ol))

				for nl in new_lines:
					# Adding new justifications
					if nl not in old_lines:
						nl.write(rec.perform_justification(nl))		
		return updated

	def unlink(self):
		if not self._check_permissions():
			raise UserError(_("Only the student's tutor can remove its attendance justifications."))
		
		for rec in self:
			for line in rec.attendance_session_line_ids:	
				if line.status == "m_justified":
					line.write(rec.remove_justification(line))

		return super().unlink()	