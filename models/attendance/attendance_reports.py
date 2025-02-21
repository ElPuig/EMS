# -*- coding: utf-8 -*-

from odoo import models, fields, api
from .attendance_status import status

class ims_attendance_report_student_wizard(models.TransientModel):
	_name = "ims.attendance_report_student_wizard"
	_description = "Attendance report wizard: by student."

	# level_id = fields.Many2one(string='Level', comodel_name='ims.level')    
	# study_id = fields.Many2one(string='Studies', comodel_name='ims.study') 
	# group_id = fields.Many2one(string='Group', comodel_name='ims.group')     
	# tutor_id = fields.Many2one(string='Tutor', related="group_id.tutor_id") 
	student_id = fields.Many2one(string="Student", comodel_name="res.partner", domain="[('contact_type', '=', 'student')]", required=True)
	allowed_student_ids = fields.Many2many('res.partner', compute='_compute_allowed_student_ids', store=False)
	#student_id = fields.Many2one(string="Student", comodel_name="res.partner", domain="_compute_student_id_domain", required=True)
	from_date = fields.Date(string="From", default=fields.Datetime.now, required=True)
	to_date = fields.Date(string="To", default=fields.Datetime.now, required=True)
	
	# @api.onchange('level_id')
	# def _onchange_level_id(self):	
	# 	for rec in self:			
	# 		rec.study_id = False
		
	# @api.onchange('study_id')
	# def _onchange_study_id(self):	
	# 	for rec in self:			
	# 		rec.group_id = False

	@api.depends('student_id')
	def _compute_allowed_student_ids(self):
		# Cross student's enrollment data with teacher's teaching data.		
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
		# query = """SELECT status.*, session.*  FROM ims_attendance_status AS status
		# 		LEFT JOIN res_partner AS student on student.id = status.student_id
		# 		LEFT JOIN ims_attendance_session AS session on session.id = status.attendance_session_id
		# 		WHERE student.id=%d AND session.date >= '%s' AND session.date <= '%s'""" % (self.student_id, self.from_date, self.to_date)

		query = """SELECT status.id FROM ims_attendance_status AS status
				LEFT JOIN ims_attendance_session AS session ON session.id = status.attendance_session_id
				WHERE status.student_id=%d AND session.date >= '%s' AND session.date <= '%s'""" % (self.student_id, self.from_date, self.to_date)
								
		self.env.cr.execute(query)		
		status_ids = self.env.cr.dictfetchall()
		data = {'student_id': self.read()[0]['student_id'][0],'status_ids': list(map(lambda x:x['id'], status_ids))}

		return self.env.ref('ims.action_attendance_report_student').with_context(landscape=True).report_action(None, data=data)


# TODO: template to prepare the wizard for the group report
# class ims_attendance_report_student_wizard(models.TransientModel):
# 	_name = "ims.attendance_report_student_wizard"
# 	_description = "Attendance report wizard: by student."

# 	level_id = fields.Many2one(string='Level', comodel_name='ims.level')    
# 	study_id = fields.Many2one(string='Studies', comodel_name='ims.study') 
# 	group_id = fields.Many2one(string='Group', comodel_name='ims.group')     
# 	tutor_id = fields.Many2one(string='Tutor', related="group_id.tutor_id") 
# 	student_id = fields.Many2one(string="Student", comodel_name="res.partner", domain="[('contact_type', '=', 'student')]", required=True)
# 	from_date = fields.Date(string="From", default=fields.Datetime.now, required=True)
# 	to_date = fields.Date(string="To", default=fields.Datetime.now, required=True)
	
# 	@api.onchange('level_id')
# 	def _onchange_level_id(self):	
# 		for rec in self:			
# 			rec.study_id = False
		
# 	@api.onchange('study_id')
# 	def _onchange_study_id(self):	
# 		for rec in self:			
# 			rec.group_id = False


# 	@api.onchange("student_id")
# 	def _onchange_student_id(self):
# 		for rec in self:
# 			if rec.student_id.id != False:
# 				sessions = self.env["ims.attendance_status"].search([("student_id", "=", rec.student_id.id)]).mapped('attendance_session_id')
# 				first = sessions.search([], order="date asc", limit=1)
# 				last = sessions.search([], order="date desc", limit=1)
# 				rec.from_date = first.date
# 				rec.to_date = last.date

# 	def print(self):
# 		# query = """SELECT status.*, session.*  FROM ims_attendance_status AS status
# 		# 		LEFT JOIN res_partner AS student on student.id = status.student_id
# 		# 		LEFT JOIN ims_attendance_session AS session on session.id = status.attendance_session_id
# 		# 		WHERE student.id=%d AND session.date >= '%s' AND session.date <= '%s'""" % (self.student_id, self.from_date, self.to_date)

# 		query = """SELECT status.id FROM ims_attendance_status AS status
# 				LEFT JOIN ims_attendance_session AS session on session.id = status.attendance_session_id
# 				WHERE status.student_id=%d AND session.date >= '%s' AND session.date <= '%s'""" % (self.student_id, self.from_date, self.to_date)
								
# 		self.env.cr.execute(query)		
# 		status_ids = self.env.cr.dictfetchall()
# 		data = {'student_id': self.read()[0]['student_id'][0],'status_ids': list(map(lambda x:x['id'], status_ids))}

# 		return self.env.ref('ims.action_attendance_report_student').with_context(landscape=True).report_action(None, data=data)

class ims_attendance_report_student(models.AbstractModel):
	_name = 'report.ims.attendance_report_student'
	_description = "Attendance report data: by student."

	def _get_report_values(self, docids, data=None):        						
		#	Form content:
		#		docs: the current student
		#		lines: the report data for the current student, one line per subject
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
		grp_by_subject = {}
		for sub in self.env["ims.attendance_status"].browse(data['status_ids']):
			key = sub.attendance_session_id.subject_id
			if not key in grp_by_subject: grp_by_subject[key] = []
			values = grp_by_subject[key]			
			values.append(sub)					

		# Step 2: for every subject, compute the overall and its breakdown (details)
		lines = {}	
		for subject in grp_by_subject:
			# Step 2.1: setup init data
			counters = {}
			comments = []
			entries = []
			for st in status:
				counters[st[0]] = 0

			for sub in grp_by_subject[subject]:
				counters[sub.status] += 1				
				if sub.notes != False: comments.append(sub)
				entries.append(sub)
			
			# Step 2.2: setup breakdown data
			breakdown = {}
			total = len(grp_by_subject[subject])
			for entry in counters:
				breakdown[entry] = self._setup_overall(counters[entry], total)

			# Steup 2.3: use the breakdown data to setup the overall data
			attended = 	self._get_status('a_attended')[0]
			miss = 	self._get_status('m_miss')[0]
			overall = {
				attended : self._setup_overall(0, total),
				miss : self._setup_overall(0, total),
			}

			for sub in status:
				if sub[0][0] == 'a': item = overall[attended]
				else: item = overall[miss]				
				item['count'] += breakdown[sub[0]]['count']

			self._compute_overall(overall[attended])
			self._compute_overall(overall[miss])

			# Step 3: setup all the data for this subject
			lines[subject] = {'overall' : overall, 'breakdown' : breakdown, 'comments' : comments, 'entries' : entries}		
		
		return {
			'doc_ids': docids,
			'doc_model': 'res.partner',
			'docs': self.env["res.partner"].browse(data['student_id']),
			'lines': lines,
			'status': dict(status)
		}
	
	def _get_status(self, name):
		return list(filter(lambda x: x[0] == name, status))[0]
	
	def _setup_overall(self, count, total):
		overall = {
			'count' : count,
			'total' : total,
			'%'		: 0
		}
		self._compute_overall(overall)
		return overall
	
	def _compute_overall(self, overall):
		if overall['total'] > 0: overall['%'] = (overall['count'] / overall['total']) * 100		
