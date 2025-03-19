# -*- coding: utf-8 -*-

from odoo import models, fields, api
from .attendance_status import attendance_status

overall_status = [("assistance", "Assistance"), ("absence", "Absence")]

# Reports:
#	1. Attendance by group (for tutors and above, teachers can calso use it, but only its teaching subject/students will be displayed)
#	2. Attendance by student (for tutors and above, teachers can calso use it, but only its teaching subject/students will be displayed)
#	3. Attendance by subject (for the teachers teaching that subject and above)

class ims_attendance_report_group_wizard(models.TransientModel):
	_name = "ims.attendance_report_group_wizard"
	_description = "Attendance report wizard: by group."

	level_id = fields.Many2one(string='Level', comodel_name='ims.level')    
	study_id = fields.Many2one(string='Studies', comodel_name='ims.study') 
	group_id = fields.Many2one(string='Group', comodel_name='ims.group')     
	tutor_id = fields.Many2one(string='Tutor', related="group_id.tutor_id") 
	allowed_group_ids = fields.Many2many('ims.group', compute='_compute_allowed_group_ids', store=False)
	from_date = fields.Date(string="From", default=fields.Datetime.now, required=True)
	to_date = fields.Date(string="To", default=fields.Datetime.now, required=True)	

	@api.onchange('study_id')
	def _compute_allowed_group_ids(self):
		for rec in self:
			if rec.study_id.id != False:
				# Crossing student's enrollment data with teacher's teaching data.		
				query = """SELECT tea.group_id FROM ims_teaching AS tea
						LEFT JOIN ims_group AS grp ON grp.id = tea.group_id"""
				
				# TODO: use this to set the permissions (uid = 1 means ADMIN)
				current_teacher = self.env["hr.employee"].search([("user_id", "=", self.env.uid)])
				if current_teacher.id > 1:
					query += " WHERE tea.teacher_id=%d" % (current_teacher.id)
				
				self.env.cr.execute(query)		
				group_ids = list(map(lambda x: x[0], self.env.cr.fetchall()))

				rec.allowed_group_ids = self.env["ims.group"].browse(group_ids)

	@api.onchange('level_id')
	def _onchange_level_id(self):	
		for rec in self:			
			rec.study_id = False
		
	@api.onchange('study_id')
	def _onchange_study_id(self):	
		for rec in self:			
			rec.group_id = False

	@api.onchange("group_id")
	def _onchange_group_id(self):
		for rec in self:
			if rec.group_id.id != False:
				sessions = self.env["ims.attendance_session"].search([("group_id", "=", rec.group_id.id)])
				first = sessions.search([], order="date asc", limit=1)
				last = sessions.search([], order="date desc", limit=1)
				rec.from_date = first.date
				rec.to_date = last.date

	def print(self):		
		query = """SELECT status.id FROM ims_attendance_status AS status
				LEFT JOIN ims_attendance_session AS session ON session.id = status.attendance_session_id
				WHERE session.group_id=%d AND session.date >= '%s' AND session.date <= '%s'""" % (self.group_id, self.from_date, self.to_date)
								
		self.env.cr.execute(query)		
		status_ids = self.env.cr.dictfetchall()
		data = {'doc_ids': [self.read()[0]['id']],'status_ids': list(map(lambda x:x['id'], status_ids))}

		return self.env.ref('ims.action_attendance_report_group').with_context(landscape=True).report_action(None, data=data)

class ims_attendance_report_student_wizard(models.TransientModel):
	_name = "ims.attendance_report_student_wizard"
	_description = "Attendance report wizard: by student."

	level_id = fields.Many2one(string='Level', comodel_name='ims.level')    
	study_id = fields.Many2one(string='Studies', comodel_name='ims.study') 
	group_id = fields.Many2one(string='Group', comodel_name='ims.group')     
	tutor_id = fields.Many2one(string='Tutor', related="group_id.tutor_id") 
	student_id = fields.Many2one(string="Student", comodel_name="res.partner", domain="[('contact_type', '=', 'student')]", required=True)
	allowed_student_ids = fields.Many2many('res.partner', compute='_compute_allowed_student_ids', store=False)
	from_date = fields.Date(string="From", default=fields.Datetime.now, required=True)
	to_date = fields.Date(string="To", default=fields.Datetime.now, required=True)	

	@api.onchange('group_id')
	def _compute_allowed_student_ids(self):
		for rec in self:
			if rec.group_id.id != False:
				# Crossing student's enrollment data with teacher's teaching data.		
				query = """SELECT en.student_id FROM ims_teaching AS tea
						LEFT JOIN ims_enrollment AS en ON en.group_id = tea.group_id AND en.subject_id = tea.subject_id AND tea.group_id=%d""" % rec.group_id.id
				
				# TODO: use this to set the permissions (uid = 1 means ADMIN)
				current_teacher = self.env["hr.employee"].search([("user_id", "=", self.env.uid)])
				if current_teacher.id > 1:
					query += " WHERE tea.teacher_id=%d" % (current_teacher.id)
				
				self.env.cr.execute(query)		
				student_ids = list(map(lambda x: x[0], self.env.cr.fetchall()))

				rec.allowed_student_ids = self.env["res.partner"].browse(student_ids)

	@api.onchange('level_id')
	def _onchange_level_id(self):	
		for rec in self:			
			rec.study_id = False
		
	@api.onchange('study_id')
	def _onchange_study_id(self):	
		for rec in self:			
			rec.group_id = False

	@api.onchange("student_id")
	def _onchange_student_id(self):
		for rec in self:
			if rec.student_id.id != False:
				sessions = self.env["ims.attendance_status"].search([("student_id", "=", rec.student_id.id)]).mapped('attendance_session_id')
				first = sessions.search([], order="date asc", limit=1)
				last = sessions.search([], order="date desc", limit=1)
				rec.from_date = first.date
				rec.to_date = last.date

	def print(self):		
		query = """SELECT status.id FROM ims_attendance_status AS status
				LEFT JOIN ims_attendance_session AS session ON session.id = status.attendance_session_id
				WHERE status.student_id=%d AND session.date >= '%s' AND session.date <= '%s'""" % (self.student_id, self.from_date, self.to_date)
								
		self.env.cr.execute(query)		
		status_ids = self.env.cr.dictfetchall()
		data = {'doc_ids': [self.read()[0]['id']],'status_ids': list(map(lambda x:x['id'], status_ids))}

		return self.env.ref('ims.action_attendance_report_student').with_context(landscape=True).report_action(None, data=data)

class ims_attendance_report_subject_wizard(models.TransientModel):
	_name = "ims.attendance_report_subject_wizard"
	_description = "Attendance report wizard: by subject."

	level_id = fields.Many2one(string='Level', comodel_name='ims.level')    
	study_id = fields.Many2one(string='Studies', comodel_name='ims.study') 
	group_id = fields.Many2one(string='Group', comodel_name='ims.group')     
	tutor_id = fields.Many2one(string='Tutor', related="group_id.tutor_id") 
	subject_id = fields.Many2one(string="Subject", comodel_name="ims.subject", required=True)
	allowed_subject_ids = fields.Many2many('ims.subject', compute='_compute_allowed_subject_ids', store=False)

	from_date = fields.Date(string="From", default=fields.Datetime.now, required=True)
	to_date = fields.Date(string="To", default=fields.Datetime.now, required=True)
	
	@api.depends('group_id')
	def _compute_allowed_subject_ids(self):		
		# TODO: use this to set the permissions (uid = 1 means ADMIN)
		current_teacher = self.env["hr.employee"].search([("user_id", "=", self.env.uid)])
		
		for rec in self:
			if rec.group_id.id == False:
				rec.allowed_subject_ids = []
			else:
				filter = [('group_id', '=', rec.group_id.id)]
				if current_teacher.id > 1: filter.append(('group_id', '=', rec.group_id.id))
				rec.allowed_subject_ids = self.env["ims.teaching"].search(filter).mapped('subject_id')

	@api.onchange('level_id')
	def _onchange_level_id(self):	
		for rec in self:			
			rec.study_id = False
		
	@api.onchange('study_id')
	def _onchange_study_id(self):	
		for rec in self:			
			rec.group_id = False


	@api.onchange("subject_id")
	def _onchange_subject_id(self):
		for rec in self:
			if rec.subject_id.id != False:
				sessions = self.env["ims.attendance_session"].search([("subject_id", "=", rec.subject_id.id), ("group_id", "=", rec.group_id.id)])
				first = sessions.search([], order="date asc", limit=1)
				last = sessions.search([], order="date desc", limit=1)
				rec.from_date = first.date
				rec.to_date = last.date

	def print(self):
		query = """SELECT status.id FROM ims_attendance_status AS status
				LEFT JOIN ims_attendance_session AS session on session.id = status.attendance_session_id
				WHERE session.group_id=%d AND session.subject_id=%d AND session.date >= '%s' AND session.date <= '%s'""" % (self.group_id, self.subject_id, self.from_date, self.to_date)
		
		self.env.cr.execute(query)		
		status_ids = self.env.cr.dictfetchall()
		data = {'doc_ids': [self.read()[0]['id']],'status_ids': list(map(lambda x:x['id'], status_ids))}

		return self.env.ref('ims.action_attendance_report_subject').with_context(landscape=True).report_action(None, data=data)

class ims_attendance_report_student(models.AbstractModel):
	_name = 'report.ims.attendance_report_student'
	_description = "Attendance report data: by student."

	def _get_report_values(self, docids, data=None):
		if len(docids) == 0: docids = data['doc_ids'] # TODO: is there any way to got this from docids param? Always null even when setting up at report_action
		entries = list(self.env["ims.attendance_status"].browse(data['status_ids']))
		main = _report_data(entries)

		grp_by_subject = {}
		for e in entries:
			key = e.attendance_session_id.subject_id
			if not key in grp_by_subject: grp_by_subject[key] = []
			values = grp_by_subject[key]
			values.append(e)

		lines = {}
		for s in grp_by_subject:
			lines[s] = _report_data(grp_by_subject[s])
				
		return {
			'doc_ids': docids,
			'doc_model': 'ims.attendance_report_student_wizard',
			'docs': self.env["ims.attendance_report_student_wizard"].browse(data['doc_ids']),
			'main': main,
			'lines': lines,
			'attendance_status': dict(attendance_status),
			'overall_status': dict(overall_status)
		}		

class ims_attendance_report_subject(models.AbstractModel):
	_name = 'report.ims.attendance_report_subject'
	_description = "Attendance report data: by subject."
		
	def _get_report_values(self, docids, data=None):
		if len(docids) == 0: docids = data['doc_ids'] # TODO: is there any way to got this from docids param? Always null even when setting up at report_action
		entries = list(self.env["ims.attendance_status"].browse(data['status_ids']))
		main = _report_data(entries)

		grp_by_student = {}
		for e in entries:
			key = e.student_id
			if not key in grp_by_student: grp_by_student[key] = []
			values = grp_by_student[key]
			values.append(e)

		lines = {}
		for s in grp_by_student:
			lines[s] = _report_data(grp_by_student[s])
				
		return {
			'doc_ids': docids,
			'doc_model': 'ims.attendance_report_student_wizard',
			'docs': self.env["ims.attendance_report_subject_wizard"].browse(data['doc_ids']),
			'main': main,
			'lines': lines,
			'attendance_status': dict(attendance_status),
			'overall_status': dict(overall_status)
		}
	

class ims_attendance_report_group(models.AbstractModel):
	_name = 'report.ims.attendance_report_group'
	_description = "Attendance report data: by group."
		
	# TODO: this is just a copy/paste, should be properly implemented!
	def _get_report_values(self, docids, data=None):
		if len(docids) == 0: docids = data['doc_ids'] # TODO: is there any way to got this from docids param? Always null even when setting up at report_action
		entries = list(self.env["ims.attendance_status"].browse(data['status_ids']))
		main = _report_data(entries)

		grp_by_student = {}
		for e in entries:
			key = e.student_id
			if not key in grp_by_student: grp_by_student[key] = []
			values = grp_by_student[key]
			values.append(e)

		lines = {}
		for s in grp_by_student:
			lines[s] = _report_data(grp_by_student[s])
				
		return {
			'doc_ids': docids,
			'doc_model': 'ims.attendance_report_student_wizard',
			'docs': self.env["ims.attendance_report_subject_wizard"].browse(data['doc_ids']),
			'main': main,
			'lines': lines,
			'attendance_status': dict(attendance_status),
			'overall_status': dict(overall_status)
		}
		
class _report_data:
	def __init__(self, entries):
		self.entries = entries
		self.comments = []
		self.breakdown = {}

		assistance = 	self._get_status('assistance')[0]
		absence = 	self._get_status('absence')[0]		
		self.overall = {
			assistance : self._setup_counters(0, len(entries)),
			absence : self._setup_counters(0, len(entries))
		}

		for s in attendance_status:
			self.breakdown[s[0]] = self._setup_counters(0, len(entries))

		for e in entries:
			self.breakdown[e.status]['count'] += 1		
			if e.notes != False: self.comments.append(e)	
			if e.status[0] == 'a': self.overall[assistance]['count'] += 1
			else: self.overall[absence]['count'] += 1

		for s in attendance_status:
			self._compute_counters(self.breakdown[s[0]])
		
		self._compute_counters(self.overall[assistance])
		self._compute_counters(self.overall[absence])
		

	def _get_status(self, name):
		return list(filter(lambda x: x[0] == name, overall_status))[0]
	
	def _setup_counters(self, count, total):
		overall = {
			'count' : count,
			'total' : total,
			'%'		: 0
		}
		self._compute_counters(overall)
		return overall
	
	def _compute_counters(self, overall):
		if overall['total'] > 0: overall['%'] = round((overall['count'] / overall['total']) * 100, 2)
