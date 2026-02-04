# -*- coding: utf-8 -*-

from odoo import models, fields, api
from .attendance_schedule import ems_attendance_schedule
from datetime import datetime, timedelta

# NOTE: In order to allow customization (like adding new status types), status starting with 'a_' will be 
#		computed as an 'attendance' snd starting with 'm_' as a 'm_miss' when reporting summary data.
attendance_status_selection = [("a_attended", "Attended"), ("a_delayed", "Delayed"), ("m_miss", "Miss"), ("m_justified", "Justified Miss"), ("a_issue", "Issue")]

class ems_attendance_session_header(models.Model):
	_name = "ems.attendance_session_header"
	_description = "Attendance session header: contains the main data about an attendance session."
	_inherit = ['ems.base', 'ems.datetime_utils', 'mail.thread', 'mail.activity.mixin']	
	_sql_constraints = [
		# TODO: localize this (the same message appears in form).
        (
            'attendance_session_is_duped',
            'UNIQUE(date, attendance_schedule_id)',
            'The current session already exists. Please, edit the existing one (maybe has been created by another teacher) or choose another available session.' # El mensaje de error
        )
    ]
	
	# NOTE: This is an statistical data model, should be unaltered if master-data (template, etc.) changes, so the parent data will be copied.		
	weekday = fields.Selection(string="Weekday", compute="_compute_weekday", selection=ems_attendance_schedule.weekdays_selection, store=True)
	start_time = fields.Float("Start Time", compute="_compute_start_time", store=True)
	end_time = fields.Float("End Time", compute="_compute_end_time", store=True)	
	time_range = fields.Char("Time range", compute="_compute_time_range", store=True)

	date = fields.Date(string="Date", default=fields.Datetime.now, required=True)
	start_date = fields.Datetime(compute="_compute_start_date", store=True)	
	end_date = fields.Datetime(compute="_compute_end_date", store=True)

	# TODO: 
	# 		1. Remove unnecessary data. 
	# 		2. Related data should not be never removed, but archived. 
	# 		For example:
	# 			1. New course, so new templates.
	#			2. Removing templates, removes also the schedules.
	#			3. Sessions are linked to schedules, so cannot be removed because never should be removed by cascade (only manually).
	# 			4. The same if a student's group is removed, it should really be archived.
	level_id = fields.Many2one(string="Level", comodel_name="ems.level", compute="_compute_level_id", store=True)
	study_id = fields.Many2one(string="Study", comodel_name="ems.study", compute="_compute_study_id", store=True)
	group_id = fields.Many2one(string="Group", comodel_name="ems.group", compute="_compute_group_id", store=True)
	subject_id = fields.Many2one(string="Subject", comodel_name="ems.subject", compute="_compute_subject_id", store=True)
	space_id = fields.Many2one(string="Space", comodel_name="ems.space", compute="_compute_space_id", store=True)
	template_teacher_id = fields.Many2one(string="Template's teacher", comodel_name="hr.employee", compute="_compute_template_teacher_id", store=True)
	session_teacher_id = fields.Many2one(string="Session's teacher", comodel_name="hr.employee", domain="[('employee_type', '=', 'teacher')]", required=True, default=lambda self: self._default_teacher_id(), store=True)	
	mode = fields.Selection(string="Mode", selection=[('scheduled', 'Scheduled'), ('guard', 'Guard'), ('manual', 'Manual')], default="scheduled", required=True)
	
	attendance_session_line_ids = fields.One2many(string="Statuses", comodel_name="ems.attendance_session_line", inverse_name="attendance_session_id")			
	attendance_schedule_id = fields.Many2one(string="Session", comodel_name="ems.attendance_schedule", required=True)
	allowed_attendance_schedule_ids = fields.Many2many(comodel_name='ems.attendance_schedule', store=False)
	
	display_warning = fields.Boolean(default=lambda self: self._default_display_warning(), store=False)
	is_duped = fields.Boolean(store=False)
	is_next = fields.Boolean(store=False)	

	notes = fields.Text("Notes")	

	@api.depends("attendance_schedule_id")
	def _compute_weekday(self):
		for rec in self:
			rec.weekday = rec.attendance_schedule_id.weekday

	@api.depends("attendance_schedule_id")
	def _compute_start_time(self):
		for rec in self:
			rec.start_time = rec.attendance_schedule_id.start_time

	@api.depends("attendance_schedule_id")
	def _compute_end_time(self):
		for rec in self:
			rec.end_time = rec.attendance_schedule_id.end_time

	@api.depends("attendance_schedule_id")
	def _compute_time_range(self):
		for rec in self:
			rec.time_range = rec.attendance_schedule_id.time_range

	@api.depends("attendance_schedule_id")
	def _compute_start_date(self):			
		for rec in self:
			local = rec.time_float_to_local_datetime(rec.date, rec.start_time)
			utc = rec.local_datetime_to_utc(local)
			rec.start_date = rec.datetime_to_odoo(utc)
	
	@api.depends("attendance_schedule_id")
	def _compute_end_date(self):			
		for rec in self:
			local = rec.time_float_to_local_datetime(rec.date, rec.end_time)
			utc = rec.local_datetime_to_utc(local)
			rec.end_date = rec.datetime_to_odoo(utc)
	
	# TODO:  should be related? Can a "sudo" be used within a related or is not needed?
	@api.depends("attendance_schedule_id")
	def _compute_level_id(self):
		for rec in self:
			rec.level_id = rec.attendance_schedule_id.attendance_template_id.sudo().level_id

	@api.depends("attendance_schedule_id")
	def _compute_study_id(self):
		for rec in self:
			rec.study_id = rec.attendance_schedule_id.attendance_template_id.sudo().study_id

	@api.depends("attendance_schedule_id")
	def _compute_group_id(self):
		for rec in self:
			rec.group_id = rec.attendance_schedule_id.attendance_template_id.sudo().group_id

	@api.depends("attendance_schedule_id")
	def _compute_subject_id(self):
		for rec in self:
			rec.subject_id = rec.attendance_schedule_id.attendance_template_id.sudo().subject_id

	@api.depends("attendance_schedule_id")
	def _compute_space_id(self):
		for rec in self:
			rec.space_id = rec.attendance_schedule_id.attendance_template_id.sudo().space_id

	@api.depends("attendance_schedule_id")
	def _compute_template_teacher_id(self):
		for rec in self:
			rec.template_teacher_id = rec.attendance_schedule_id.attendance_template_id.sudo().teacher_id
	
	@api.depends('attendance_schedule_id', 'date')
	def _compute_display_name(self):              
		for rec in self:
			rec.display_name = "%s | %s | %s" % (rec.attendance_schedule_id.display_name, rec.date, rec.space_id.name)

	@api.onchange("mode")
	def _onchange_mode(self):
		for rec in self:
			ids = []		
			for allowed in self._get_allowed_attendance_schedule_ids():				
				ids.append(allowed.id)
			rec.allowed_attendance_schedule_ids = [(6, 0, ids)]
			rec.attendance_schedule_id = False if len(rec.allowed_attendance_schedule_ids) == 0 else rec.allowed_attendance_schedule_ids[0]
		
	@api.onchange("attendance_schedule_id")	
	def _onchange_attendance_schedule_id(self):		
		for rec in self:			
			lines = []
			rec.is_next = False
			rec.is_duped = False
			
			for attendance_session_line in rec.attendance_session_line_ids:
				# Unlink previous students
				lines.append([3, attendance_session_line.id])

			if rec.attendance_schedule_id.id != False:
				now = datetime.now()
				schedule_id = rec.attendance_schedule_id.id if isinstance(rec.attendance_schedule_id.id, int) else rec.attendance_schedule_id.id.origin
				rec.is_duped = self.env["ems.attendance_session_header"].search([("date", "=", now), ("attendance_schedule_id.id", "=", schedule_id)]) or False
								
				# NOTE: The first approach was to check if start_date of current == end_date of previous, but what happens if there's a coffe break between sessions?	
				#		Its better to check if the same subject has been teached previously and load the same data (maybe there's a gap between, but the student assistance 
				# 		data should be almost the same). 
				previous = self.env["ems.attendance_session_header"].search(
					[
						("date", "=", datetime.now()), 						
						("attendance_schedule_id.attendance_template_id.id", "=", rec.attendance_schedule_id.attendance_template_id.sudo().id),
						("attendance_schedule_id.weekday", "=", rec.attendance_schedule_id.weekday)
					], order="end_time DESC", limit=1)
				
				if previous:
					end = previous.end_time
					start = self.utc_datetime_to_local(datetime.now())
					rec.is_next = (end <= self.time_to_float(start.time()))	

					if rec.is_next:
						# Load new entries but with the previous session's data
						for prev in previous.attendance_session_line_ids:
							lines.append([0, 0, self._setup_next_session_line_data(prev)])
						
			if not rec.is_next:
				# Load empty entries, must check absence prevission
				previssions = self.sudo().env["ems.attendance_justification"].search([("start_date", "<=", fields.Datetime.now()), ("end_date", ">=", fields.Datetime.now())])
				for student in rec.attendance_schedule_id.attendance_template_id.sudo().student_ids:
					# Sources: 
					# 	https://stackoverflow.com/a/70843263
					#	https://www.odoo.com/ro_RO/forum/suport-1/how-to-insert-value-to-a-one2many-field-in-table-with-create-method-28714
					
					# Linking new students					
					line = None
					for p in previssions:
						if p.student_id == student:
							line = p.perform_justification(self._setup_new_line_data(student), True)

					if line is None:
						line = self._setup_new_line_data(student, "a_attended")
						
					lines.append([0, 0, line])	
			
			# NOTE: if duped, avoid next message.
			if rec.is_duped: rec.is_next = False
			rec.attendance_session_line_ids = lines

	def _default_teacher_id(self):							
		return self.env["hr.employee"].search([("user_id", "=", self.env.uid), ("employee_type", "=", "teacher")]) or False

	def _default_display_warning(self):						
		attendance_schedule_records = self._get_allowed_attendance_schedule_ids()
		return self.id == False and len(attendance_schedule_records) != 1
	
	def _get_allowed_attendance_schedule_ids(self):		
		# TODO: this method is called twice on load, one from the _default_display_warning and the other one from _onchange_guard_mode
		# 		the context (self.context) is not shared because there calls come from different instances, so I 
		# 		can't share the registers in order to avoid duped calls...
		today = datetime.now()
		where = [("start_date", "<=", today), ("end_date", ">=", today)]	
		
		if self.mode == "manual" and not self.env.user.has_group('ems.group_admin'):
			where.append(("teacher_id.user_id", "=", self.env.uid))
		elif self.mode != "manual":
			where.append(("weekday", "=", today.weekday()))
			where.append(("teacher_id.user_id", "!=" if self.mode == "guard" else "=", self.env.uid))

		# NOTE: the file security/rules.xml should define which records can be loaded depeding on the current user, 
		# BUT all records must be avaliable (read only) on guard mode, so sudo will be used. 		
		regs = self.sudo().env["ems.attendance_schedule"].search(where)
		
		if self.mode == "manual": 
			return regs
		else:					
			current = []
			for r in regs:
				# NOTE: I wasn't able to filter the search by hour-range due timezones, so ill do it manually
				# 		- Spain's summer period time: GMT+2 (UTC + 2h)
				#       - Spain's winter period time: GMT+1 (UTC + 1h)	
				# 		- Getting a winter's UTC current time won't fit when compared with a summer's UTC stored time.
				#		
				# 		SOLUTION: converting all UTC dates (the BBDD ones, as Odoo does) to local and compare. Less efficient,
				#		but the schedules entries have been filtered at maximum. 
				start = r.utc_datetime_to_local(r.start_date).time()
				end = r.utc_datetime_to_local(r.end_date).time()				
				now = r.utc_datetime_to_local(datetime.now()).time()
				if now >= start and now < end:
					current.append(r)		
			return current			
	
	def _get_notification_tutor_eta(self):
		# TODO: tutor's working schedule end-time should be loaded firts, and use the default only if not defined. 
		notification_tutor_eta = self.time_float_to_utc_datetime(fields.Datetime.now(), self.env.company.attendance_issue_tutor_default)
		return self.datetime_to_odoo(notification_tutor_eta)
	
	def _get_notification_status_eta(self):
		return fields.Datetime.now() + timedelta(seconds=self.env.company.attendance_issue_status_delay * 60) # from minutes to seconds
	
	def _get_or_create_issue_status(self, issue_student, attendance_status_id, send_to, rectification):
		data = self.get_issue_status(attendance_status_id)
		repo = data["repo"]
		issue_status = data["values"]	
		
		if not issue_status or rectification:
			as_id = self.sudo().env['ems.attendance_session_line'].sudo().search([('id', '=', attendance_status_id)])
			issue_status = repo.create({				
				'attendance_issue_student_id': issue_student.id,
				'attendance_status_id': attendance_status_id,
				'attendance_session_status': as_id.status,
				'rectification': rectification,
				'notes': as_id.notes,
				'send_to': send_to,				
			})

			if rectification:
				must_rectify = self.sudo().env['ems.attendance_issue_status'].sudo().search([('attendance_status_id', '=', attendance_status_id), ('rectified_by', '=', False), ('id', '!=', issue_status.id)])
				for rect in must_rectify:				
					rect.write({'rectified_by' : issue_status.id})

		return issue_status
	
	def _get_or_create_issue_student(self, issue_tutor, student_id):
		data = self.get_issue_student(issue_tutor, student_id)		
		repo = data["repo"]
		issue_student = data["values"]	

		if not issue_student:
			issue_student = repo.create({
				'student_id': student_id,
				'attendance_issue_tutor_id': issue_tutor.id
			})		
		return issue_student
	
	def _get_or_create_issue_tutor(self, tutor_id, date):
		data = self.get_issue_tutor(tutor_id)		
		repo = data["repo"]
		issue_tutor = data["values"]		
		
		if not issue_tutor:
			issue_tutor = repo.create({
				'tutor_id': tutor_id.id,
				'issue_date': date
			})
		return issue_tutor
	
	def _schedule_daily_assistance_notification(self, issue_tutor, eta):		
		if issue_tutor.notification_id.id != False: return

		daily = issue_tutor.with_delay(
			eta = eta,
			description=f"Tutor's assistance report: ID={issue_tutor.id}"
		).send_notification()

		job = self.sudo().env['queue.job'].search([('uuid', '=', daily.uuid)]) or False
		if job: issue_tutor.sudo().write({'notification_id': job.id})

	def _schedule_family_assistance_notification(self, issue_status, eta, rectification):		
		if issue_status.notification_id.id != False or not issue_status.send_to or issue_status.send_to == "": return				

		noti = issue_status.with_delay(
			eta = eta,
			description="Family assistance notification %s: ID=%s" % ("" if not rectification else " (rectification)", issue_status.id)
		).send_notification()

		job = self.sudo().env['queue.job'].search([('uuid', '=', noti.uuid)]) or False
		if job: issue_status.sudo().write({
			'notification_id': job.id
		})
	
	def _setup_new_line_data(self, student_id, status="a_attended", notes=None):
		return  {
			"student_id": student_id,
			"status": status,
			"notes": notes
		}
	
	def _setup_next_session_line_data(self, previous):
		return  {
			"student_id": previous.student_id,
			"status": "a_attended" if previous.status == "a_delay" else previous.status,
			"notes": previous.notes,
			"attendance_justification_id": previous.attendance_justification_id,
			"attendance_prevision_id" : previous.attendance_prevision_id 
		}

	@api.model_create_multi
	def create(self, vals_list):
		records = super().create(vals_list)		
		
		# NOTE: Optional, but computed here for optimization
		notification_status_eta = self._get_notification_status_eta()
		notification_tutor_eta = self._get_notification_tutor_eta()

		for record in records:		
			# NOTE: Collecting all status data first allow some optimizations.	
			issue_status_by_tutor = dict()			
			for attendance_session_line in record.attendance_session_line_ids:			
				record.collect_issue_status_data(attendance_session_line, issue_status_by_tutor)

			record.create_notification_entries(issue_status_by_tutor, notification_tutor_eta, notification_status_eta)
		return records
	
	def unlink(self):
		# NOTE: removing the session removes also the statuses and the related notification entries
		# TODO: should be blocked if the notifications have been sent? I guess so, but the admins should be ablte to delete those
		#		after confirming a popup. 
		date = self.date
		res = super().unlink()
		
		for issue_tutor in self.env['ems.attendance_issue_tutor'].sudo().search([('issue_date', '=', date)]):
			issue_tutor.remove_if_empty()

		return res
	
	def create_notification_entries(self, issue_status_by_tutor, notification_tutor_eta=None, notification_status_eta=None, rectification=False):				
		if notification_tutor_eta is None: notification_tutor_eta = self._get_notification_tutor_eta()
		if notification_status_eta is None: notification_status_eta = self._get_notification_status_eta()

		# NOTE: Status data is grouped by tutor and only got the ones which should be notified. 
		notis = []
		for tutor_id in issue_status_by_tutor:
			for issue_status_data in issue_status_by_tutor[tutor_id]:
				issue_tutor = self._get_or_create_issue_tutor(tutor_id, self.date)
				issue_student = self._get_or_create_issue_student(issue_tutor, issue_status_data["student_id"])
				self._get_or_create_issue_status(issue_student, issue_status_data["attendance_status_id"], issue_status_data["send_to"], rectification)
				
				if not issue_tutor in notis: notis.append(issue_tutor)
		
		for notification_tutor in notis:
			# noti internal structure: attendance_issue_tutor (1) --> (N) attendance_issue_student (1) --> (N) attendance_issue_status
			# notifications for the tutors: daily (at the end if its tourn); notifications for the family (status): after a timeout (default 15 minutes). 

			self._schedule_daily_assistance_notification(notification_tutor, notification_tutor_eta)
			for issue_student in notification_tutor.attendance_issue_student_ids:
				for issue_status in issue_student.attendance_issue_status_ids:					
					self._schedule_family_assistance_notification(issue_status, notification_status_eta, rectification)

	def collect_issue_status_data(self, status_id, status_by_tutor, rectification=False):
		separator = "; "
		if rectification or status_id.status_is_notificable():
			if status_id.student_id.tutor_id not in status_by_tutor:
				status_by_tutor[status_id.student_id.tutor_id] = []
			
			send_to = []
			if status_id.student_id.auth_share or not status_id.student_id.is_adult:
				for contact in status_id.student_id.child_ids:				
					send_to.append(contact.email)

			# NOTE: The 'send_to' field will be empty if adult or family shared not authorized.
			#		All entries must be notified to the tutor, always. This trick simplifies a bit the logic.
			status_by_tutor[status_id.student_id.tutor_id].append({
				'attendance_status_id': status_id.id,
				'student_id': status_id.student_id.id,
				'send_to': separator.join(send_to)
			})	
	
	def get_issue_tutor(self, tutor_id):
		repo = self.sudo().env['ems.attendance_issue_tutor']
		issue_tutor = repo.search([('issue_date', '=', self.date), ('tutor_id', '=', tutor_id.id)]) or False		
		return {"repo": repo, "values": issue_tutor}
	
	def get_issue_student(self, issue_tutor, student_id):
		repo = self.sudo().env['ems.attendance_issue_student']
		issue_student = repo.search([('attendance_issue_tutor_id', '=', issue_tutor.id), ('student_id', '=', student_id)]) or False
		return {"repo": repo, "values": issue_student}
	
	def get_issue_status(self, attendance_status_id):
		# NOTE: On rectification, multiple issue_status can be attanched to the same attendance_session_line, but we always
		#		whant the most recent. 
		repo = self.sudo().env['ems.attendance_issue_status']
		issue_status = repo.search([('attendance_status_id', '=', attendance_status_id)], order='id desc', limit=1) or False
		return {"repo": repo, "values": issue_status}	

# NOTE: moved here because the status is strongly related to the session, it has no own list or form (as happens with the
#		attendance issues).
class ems_attendance_session_line(models.Model):	
	_name = "ems.attendance_session_line"
	_description = "Attendance status line: information about a status per student within an attendance session."
	
	# TODO: should status be renamed to value? 
	status = fields.Selection(string="Status", default="a_attended", required=True, selection=attendance_status_selection)
	student_id = fields.Many2one(string="Student", comodel_name="res.partner", domain="[('contact_type', '=', 'student')]")
	image_1920 = fields.Binary(string="Image", related='student_id.image_1920')
	attendance_session_id = fields.Many2one(string="Session", comodel_name="ems.attendance_session_header", ondelete="cascade")
	attendance_justification_id = fields.Many2one(string="Justification", comodel_name="ems.attendance_justification")
	attendance_prevision_id = fields.Many2one(string="Prevision", comodel_name="ems.attendance_justification")

	# This field is used to filter the availabe students within the view (avoiding the selection of repeated students on attendance session form).
	inuse_student_ids = fields.Many2many('res.partner', compute='_compute_inuse_student_ids', store=False) 

	# The teacher_id is used just for permission filtering pruposes.
	template_teacher_id = fields.Many2one(string="Template's teacher", related="attendance_session_id.template_teacher_id", store=False)    
	session_teacher_id = fields.Many2one(string="Session's teacher", related="attendance_session_id.session_teacher_id", store=False)    

	notes = fields.Text("Notes")

	def status_is_notificable(self):
		# TODO: load from EMS settings.
		return self.status in ['m_miss', 'a_issue']    
	
	@api.model_create_multi
	def create(self, vals_list):
		records = super().create(vals_list)		

		for r in records:		
			if r.attendance_prevision_id.id != False:
				r.attendance_prevision_id.attendance_session_line_ids = [(4, r.id)]
				# r.attendance_prevision_id.write({
				# 	"attendance_session_line_ids" : [(4, r.id)],
				# 	"session_teacher_ids" : [(4, r.attendance_session_id.session_teacher_id.id)]
				# })
			
		return records

	def write(self, vals):
		super(ems_attendance_session_line, self).write(vals)
		self._update_notification()   

	def _update_notification(self):
		session = self.attendance_session_id

		# NOTE: Original data must be compared with the current one in order to update properly.            
		previous_issue_status = False
		issue_tutor = (session.get_issue_tutor(self.student_id.tutor_id))["values"]
		if issue_tutor: 
			issue_student = session.get_issue_student(issue_tutor, self.student_id.id)
			if issue_student:
				previous_issue_status = (session.get_issue_status(self.id))["values"]

		# NOTE: Possible scenarios when updating an attendance status:
				#       1. From issue to non-issue:
				#           1.1. If not notified yet, just remove.
				#           1.2. If notified, a rectification should be send to the family.
				#       2. From issue to issue:
				#           2.1. If not notified yet, update the notification data.
				#           2.2. If notified, a rectification should be send to the family.
				#       3. From non-issue to issue:
				#           3.1. Add the notification with the regular timeout. 
				#       4. From non-issue to non-issue:
				#           4.1. Do nothing.
		create = 0
		if previous_issue_status:            
			if not previous_issue_status.pending:
				# 1.2 & 2.2. If notified, a rectification should be send to the family.                 
				create = 1
			else:
				if not self.status_is_notificable():
					# 1.1. If not notified yet, just remove.
					# NOTE: also removes the notification.                    
					issue_tutor = previous_issue_status.attendance_issue_student_id.attendance_issue_tutor_id
					previous_issue_status.unlink()
					issue_tutor.remove_if_empty()                  
				else:
					# 2.1. If not notified yet, update the notification data.
					previous_issue_status.write({
						"attendance_session_line": self.status,
						"notes": self.notes
					})
		elif self.status_is_notificable():
			# 3.1. Add the notification with the regular timeout. 
			# TODO: do not notify to the families after certain timeout (eg: is from a few days ago).
			create = 2
		
		if create != 0:
			status_by_tutor = dict()
			session.collect_issue_status_data(self, status_by_tutor, create == 1)
			session.create_notification_entries(status_by_tutor, rectification=(create == 1))

	@api.depends('attendance_session_id')
	def _compute_attendance_session_display_name(self):
		for rec in self:
			rec.attendance_session_display_name = rec.attendance_session_id.display_name

	@api.depends('attendance_session_id')
	def _compute_inuse_student_ids(self):
		for rec in self:
			rec.inuse_student_ids = False
			if rec.attendance_session_id:
				rec.inuse_student_ids = rec.mapped('attendance_session_id.attendance_session_line_ids.student_id')   

	@api.depends('attendance_session_id', 'student_id')
	def _compute_display_name(self):              
		for rec in self:
			rec.display_name = "%s | %s" % (rec.attendance_session_id.display_name, rec.student_id.display_name)

	def report_eval(self, field):
		# NOTE: this is used within the 'details_table' template in order to render custom fields.		
		return eval(field)	