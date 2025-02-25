# -*- coding: utf-8 -*-

from odoo import models, fields, api
from .attendance_status import status

# Reports:
#	1. Attendance by subject (for the teachers teaching that subject and above)
#	2. Attendance by student (for tutors and above, teachers can calso use it, but only its teaching subject/students will be displayed)
#	3. Attendance by group (for tutors and above, teachers can calso use it, but only its teaching subject/students will be displayed)

# TODO: improve the current report (by student) and prepare the new ones
# A method that, given a student, returns the attendance data (global, overall, comments and details grouped by subject) for all its subjects.
# A method that, given a subject, returns the attendance data (global, overall, comments and details grouped by student) for all its students.
# The previous methods must filter the data by requesting user. Only who teachs a subject and a student, can get the data; also,
# tutors can get the data of all its students and bosses can also get all the data (all subjects, all students).

class ims_attendance_report_student_wizard(models.TransientModel):
	_name = "ims.attendance_report_student_wizard"
	_description = "Attendance report wizard: by student."

	student_id = fields.Many2one(string="Student", comodel_name="res.partner", domain="[('contact_type', '=', 'student')]", required=True)
	allowed_student_ids = fields.Many2many('res.partner', compute='_compute_allowed_student_ids', store=False)
	from_date = fields.Date(string="From", default=fields.Datetime.now, required=True)
	to_date = fields.Date(string="To", default=fields.Datetime.now, required=True)	

	@api.depends('student_id')
	def _compute_allowed_student_ids(self):
		# Crossing student's enrollment data with teacher's teaching data.		
		query = """SELECT en.student_id FROM ims_teaching AS tea
				LEFT JOIN ims_enrollment AS en ON en.group_id = tea.group_id AND en.subject_id = tea.subject_id"""
		
		# TODO: use this to set the permissions (uid = 1 means ADMIN)
		current_teacher = self.env["hr.employee"].search([("user_id", "=", self.env.uid)])
		if current_teacher.id > 1:
			query += " WHERE tea.teacher_id=%d" % (current_teacher.id)
		
		self.env.cr.execute(query)		
		student_ids = list(map(lambda x: x[0], self.env.cr.fetchall()))

		for rec in self:
			rec.allowed_student_ids = self.env["res.partner"].browse(student_ids)


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
			'status': dict(status)
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
			'status': dict(status)
		}
		
	# def _get_report_values(self, docids, data=None):        						
		# TODO: docs beeing the wizard model instead of a student? This allows displaying the data used to filter the report.
		# This methods setups the form content data:
		#		docs: the current subject
		# 		group: the current group
		# 		summary (all the studen'ts data):
		#			overall: 
		#				attended: amount, total, %.
		#				miss: 	  amount, total, %.
		# 			breakdown:
		#				for every status -> status_key: amount, total, %.
		# 			comments:
		# 				the 'attendande_status' data containing comments (for the current subject).
		#
		#		lines: the report data for the current subject & group, one line per student
		#			overall: 
		#				attended: amount, total, %.
		#				miss: 	  amount, total, %.
		# 			breakdown:
		#				for every status -> status_key: amount, total, %.
		# 			comments:
		# 				the 'attendande_status' data containing comments (for the current subject).
		# 			entries:
		# 				all the 'attendande_status' data (for the current subject).

		# Step 1: group all the status entreis by session's subject.
	# 	grp_by_subject = {}
	# 	for sub in self.env["ims.attendance_status"].browse(data['status_ids']):
	# 		key = sub.attendance_session_id.subject_id
	# 		if not key in grp_by_subject: grp_by_subject[key] = []
	# 		values = grp_by_subject[key]			
	# 		values.append(sub)					

	# 	# Step 2: for every subject, compute the overall and its breakdown (details)
	# 	lines = {}	
	# 	for subject in grp_by_subject:
	# 		# Step 2.1: setup init data
	# 		counters = {}
	# 		comments = []
	# 		entries = []
	# 		for st in status:
	# 			counters[st[0]] = 0

	# 		for sub in grp_by_subject[subject]:
	# 			counters[sub.status] += 1				
	# 			if sub.notes != False: comments.append(sub)
	# 			entries.append(sub)
			
	# 		# Step 2.2: setup breakdown data
	# 		breakdown = {}
	# 		total = len(grp_by_subject[subject])
	# 		for entry in counters:
	# 			breakdown[entry] = self._setup_overall(counters[entry], total)

	# 		# Steup 2.3: use the breakdown data to setup the overall data
	# 		attended = 	self._get_status('a_attended')[0]
	# 		miss = 	self._get_status('m_miss')[0]
	# 		overall = {
	# 			attended : self._setup_overall(0, total),
	# 			miss : self._setup_overall(0, total),
	# 		}

	# 		for sub in status:
	# 			if sub[0][0] == 'a': item = overall[attended]
	# 			else: item = overall[miss]				
	# 			item['count'] += breakdown[sub[0]]['count']

	# 		self._compute_overall(overall[attended])
	# 		self._compute_overall(overall[miss])

	# 		# Step 3: setup all the data for this subject
	# 		lines[subject] = {'overall' : overall, 'breakdown' : breakdown, 'comments' : comments, 'entries' : entries}		
		
	# 	return {
	# 		'doc_ids': docids,
	# 		'doc_model': 'ims.subject',
	# 		'docs': self.env["res.partner"].browse(data['student_id']),
	# 		'group': g,	
	# 		'summary': s,					
	# 		'lines': lines,
	# 		'status': dict(status)
	# 	}
	
	# def _get_status(self, name):
	# 	return list(filter(lambda x: x[0] == name, status))[0]
	
	# def _setup_overall(self, count, total):
	# 	overall = {
	# 		'count' : count,
	# 		'total' : total,
	# 		'%'		: 0
	# 	}
	# 	self._compute_overall(overall)
	# 	return overall
	
	# def _compute_overall(self, overall):
	# 	if overall['total'] > 0: overall['%'] = (overall['count'] / overall['total']) * 100		


class _report_data:
	def __init__(self, entries):
		self.entries = entries
		self.comments = []
		self.breakdown = {}

		attended = 	self._get_status('a_attended')[0]
		miss = 	self._get_status('m_miss')[0]		
		self.overall = {
			attended : self._setup_counters(0, len(entries)),
			miss : self._setup_counters(0, len(entries))
		}

		for s in status:
			self.breakdown[s[0]] = self._setup_counters(0, len(entries))

		for e in entries:
			self.breakdown[e.status]['count'] += 1		
			if e.notes != False: self.comments.append(e)	
			if e.status[0] == 'a': self.overall[attended]['count'] += 1
			else: self.overall[miss]['count'] += 1

		for s in status:
			self._compute_counters(self.breakdown[s[0]])
		
		self._compute_counters(self.overall[attended])
		self._compute_counters(self.overall[miss])
		

	def _get_status(self, name):
		return list(filter(lambda x: x[0] == name, status))[0]
	
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
